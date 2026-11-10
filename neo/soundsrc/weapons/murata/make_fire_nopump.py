"""Make murata_fire_nopump.wav, the Supa-7 shell shot without its pump clicks.

Usage: python3 make_fire_nopump.py murata_fire.wav murata_fire_nopump.wav
  input   classic NEOTOKYO's sound/weapons/murata/murata_fire.wav (44.1 kHz s16; not part of neoAssets)
  output  44.1 kHz mono s16 wav, deterministic (fixed seed)

Why: the shipped shot has the pump's back and forward clicks baked in (found as bursts above 4 kHz at
0.535-0.595 s and 0.765-0.875 s). The last shell shot plays the pump as an animation, so this file must not.

Method:
 1. Keep the shot as is up to 0.52 s (before the first click).
 2. Take the short-time spectrum (STFT, 1024 samples, 75 % overlap) of the whole shot and smooth its magnitude
    within 1/3-octave bands, frame by frame.
 3. Bridge each click window in the log-magnitude by linear interpolation between the clean frames around it.
 4. Give every bin a random phase (numpy default_rng, seed 7) and invert the STFT: a noise tail with the shot's
    own color and decay, without the clicks.
 5. Match the noise tail's RMS to the shot's on 0.60-0.75 s.
 6. Crossfade shot to noise tail over 40 ms from 0.52 s.
 The RT60 printed is from the shot's clean decay (0.9-2.0 s); it is a check, not an input.

Runtime: under 1 s.
Verified with the input sha256 8363387ca0cbc6fbed42c9c00d6c8fe27b6fa8f15f172049171c36624a541078, giving output
sha256 df56877859a534f1236a6b03f21bce36215af943cbccd094abc400722720b2ec (byte-identical) with Python 3.12.3 and
numpy 1.26.4 + scipy 1.11.4, and with Python 3.12.3 and numpy 2.5.4 + scipy 1.18.1."""
import sys
import wave

import numpy as np
from scipy.signal import istft, resample_poly, stft

RATE = 44100
SEED = 7
JOIN_S = 0.52  # crossfade start, before the first click
XFADE_S = 0.040
CLICK_WINDOWS_S = ((0.525, 0.605), (0.755, 0.885))  # the clicks plus a margin, bridged in the spectrum
LEVEL_MATCH_S = (0.60, 0.75)  # clean stretch between the two clicks
STFT_LEN = 1024
STFT_OVERLAP = STFT_LEN * 3 // 4
BAND_LO_HZ = 25.0
BAND_COUNT = 30  # 1/3-octave bands from 25 Hz upward
BAND_EDGES = BAND_LO_HZ * 2 ** (np.arange(0, BAND_COUNT + 1) / 3)
LOG_FLOOR = 1e-3
RT60_FIT_S = (0.9, 2.0)
RT60_WINDOW_S = 0.02


def read_mono(path):
	with wave.open(path) as w:
		channels, rate = w.getnchannels(), w.getframerate()
		data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)
	data = data.reshape(-1, channels).mean(axis=1)
	if rate != RATE:
		data = resample_poly(data, RATE, rate)
	return data


def write_mono(path, samples):
	with wave.open(path, 'wb') as w:
		w.setnchannels(1)
		w.setsampwidth(2)
		w.setframerate(RATE)
		w.writeframes(np.clip(np.round(samples), -32768, 32767).astype(np.int16).tobytes())


def at(seconds):
	return int(round(seconds * RATE))


def rms(x):
	return float(np.sqrt(np.mean(x ** 2)))


def band_smoothed(mag, freqs):
	smooth = np.empty_like(mag)
	for lo, hi in zip(BAND_EDGES[:-1], BAND_EDGES[1:]):
		sel = (freqs >= lo) & (freqs < hi)
		if sel.any():
			smooth[sel] = np.sqrt(np.mean(mag[sel] ** 2, axis=0))
	below = freqs < BAND_EDGES[0]
	smooth[below] = mag[below]
	above = freqs >= BAND_EDGES[-1]
	if above.any():
		smooth[above] = np.sqrt(np.mean(mag[above] ** 2, axis=0))
	return smooth


def bridge_clicks(log_mag, times):
	for start, end in CLICK_WINDOWS_S:
		inside = (times >= start) & (times <= end)
		before = np.where(times < start)[0][-1]
		after = np.where(times > end)[0][0]
		w = ((times[inside] - times[before]) / (times[after] - times[before]))[None, :]
		log_mag[:, inside] = log_mag[:, [before]] * (1 - w) + log_mag[:, [after]] * w


def noise_tail(shot):
	freqs, times, spec = stft(shot, RATE, nperseg=STFT_LEN, noverlap=STFT_OVERLAP)
	log_mag = np.log(band_smoothed(np.abs(spec), freqs) + LOG_FLOOR)
	bridge_clicks(log_mag, times)
	phase = np.exp(2j * np.pi * np.random.default_rng(SEED).random(log_mag.shape))
	_, tail = istft(np.exp(log_mag) * phase, RATE, nperseg=STFT_LEN, noverlap=STFT_OVERLAP)
	tail = np.pad(tail, (0, max(0, len(shot) - len(tail))))[:len(shot)]
	lo, hi = at(LEVEL_MATCH_S[0]), at(LEVEL_MATCH_S[1])
	return tail * (rms(shot[lo:hi]) / max(rms(tail[lo:hi]), 1))


def crossfade(head, tail):
	out = head.copy()
	i, k = at(JOIN_S), at(XFADE_S)
	w = np.linspace(0, 1, k)
	out[i:i + k] = head[i:i + k] * (1 - w) + tail[i:i + k] * w
	out[i + k:] = tail[i + k:]
	return out


def rt60(shot):
	win = at(RT60_WINDOW_S)
	centers = np.arange(win // 2, len(shot) - win, win) / RATE
	level_db = np.array([20 * np.log10(max(rms(shot[int(c * RATE) - win // 2:int(c * RATE) + win // 2]), 1))
		for c in centers])
	fit = (centers >= RT60_FIT_S[0]) & (centers <= RT60_FIT_S[1])
	return -60 / np.polyfit(centers[fit], level_db[fit], 1)[0]


def main():
	if len(sys.argv) != 3:
		sys.exit(__doc__)
	shot = read_mono(sys.argv[1])
	write_mono(sys.argv[2], crossfade(shot, noise_tail(shot)))
	print('RT60 of the clean decay: %.2f s' % rt60(shot))


if __name__ == '__main__':
	main()
