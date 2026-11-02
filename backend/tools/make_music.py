"""Generate the calming instrumental tracks used by the music player.

The dashboard plays music when the camera reports a sad or distressed mood, so
the library has to be royalty free. These pieces are synthesised here instead of
downloaded: slow pentatonic notes, soft sine harmonics, and a long reverb tail.
Run this once; the WAV files land in ``public/music`` and are served by Vite.

    backend\venv\Scripts\python.exe backend\tools\make_music.py
"""

import struct
import wave
from pathlib import Path

import numpy as np

PUBLIC_MUSIC_DIR = Path(__file__).resolve().parents[2] / "public" / "music"
SAMPLE_RATE = 22050

# Pentatonic scales never produce a harsh interval, which keeps the pieces calm
# even when the note order is random.
SCALES = {
    "C_major_pentatonic": [261.63, 293.66, 329.63, 392.00, 440.00],
    "A_minor_pentatonic": [220.00, 261.63, 293.66, 329.63, 392.00],
    "F_major_pentatonic": [174.61, 196.00, 220.00, 261.63, 293.66],
    "G_major_pentatonic": [196.00, 220.00, 246.94, 293.66, 329.63],
}


def note(frequency, duration, sample_rate=SAMPLE_RATE, harmonics=(1.0, 0.35, 0.16, 0.07)):
    """One soft bell-like note with a slow attack and a long decay."""
    time_axis = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    wave_data = np.zeros_like(time_axis)
    for index, level in enumerate(harmonics, start=1):
        detune = 1 + 0.0008 * index
        wave_data += level * np.sin(2 * np.pi * frequency * detune * time_axis)

    attack = max(int(sample_rate * 0.08), 1)
    envelope = np.exp(-2.6 * time_axis / max(duration, 0.001))
    envelope[:attack] *= np.linspace(0, 1, attack)
    return wave_data * envelope


def pad(frequency, duration, sample_rate=SAMPLE_RATE):
    """A slow drone that fills the space between the melody notes."""
    time_axis = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    voices = (
        np.sin(2 * np.pi * frequency * time_axis)
        + 0.6 * np.sin(2 * np.pi * frequency * 1.002 * time_axis)
        + 0.4 * np.sin(2 * np.pi * frequency * 0.5 * time_axis)
    )
    breathing = 0.55 + 0.45 * np.sin(2 * np.pi * 0.06 * time_axis)
    return voices * breathing


def reverb(signal, sample_rate=SAMPLE_RATE):
    """Cheap multi-tap reverb so the notes bloom instead of stopping dead."""
    output = signal.copy()
    for delay_seconds, level in ((0.13, 0.42), (0.21, 0.3), (0.37, 0.2), (0.53, 0.12)):
        delay = int(sample_rate * delay_seconds)
        tail = np.zeros_like(signal)
        tail[delay:] = signal[:-delay] * level
        output += tail
    return output


def build_track(scale_name, seconds, note_gap, seed, pad_octave=0.5, brightness=1.0):
    scale = SCALES[scale_name]
    total_samples = int(SAMPLE_RATE * seconds)
    track = np.zeros(total_samples)
    random = np.random.default_rng(seed)

    position = 0.0
    previous_index = 0
    while position < seconds - note_gap:
        # Step by one or two scale degrees so the melody wanders slowly.
        step = int(random.choice([-2, -1, -1, 1, 1, 2]))
        previous_index = int(np.clip(previous_index + step, 0, len(scale) - 1))
        frequency = scale[previous_index] * float(random.choice([1.0, 1.0, 2.0]))
        duration = float(min(note_gap * 3.2, seconds - position))
        voice = note(frequency * brightness, duration) * float(random.uniform(0.45, 0.8))

        start = int(position * SAMPLE_RATE)
        end = min(start + voice.size, total_samples)
        track[start:end] += voice[: end - start]
        position += note_gap * float(random.uniform(0.75, 1.4))

    track += 0.18 * pad(scale[0] * pad_octave, seconds)
    track = reverb(track)

    # Loop cleanly: the player repeats these tracks for as long as it is needed.
    fade = int(SAMPLE_RATE * 2.5)
    track[:fade] *= np.linspace(0, 1, fade)
    track[-fade:] *= np.linspace(1, 0, fade)

    peak = float(np.max(np.abs(track))) or 1.0
    return track / peak * 0.72


def write_wav(path, samples, sample_rate=SAMPLE_RATE):
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(struct.pack(f"<{pcm.size}h", *pcm.tolist()))


TRACKS = [
    ("calm-waves.wav", "C_major_pentatonic", 72, 1.6, 11, 0.5, 1.0),
    ("memory-lullaby.wav", "A_minor_pentatonic", 78, 2.1, 23, 0.5, 1.0),
    ("warm-evening.wav", "F_major_pentatonic", 74, 1.9, 37, 1.0, 1.0),
    ("garden-morning.wav", "G_major_pentatonic", 70, 1.4, 51, 1.0, 1.5),
]


def main():
    PUBLIC_MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    for name, scale, seconds, gap, seed, pad_octave, brightness in TRACKS:
        samples = build_track(scale, seconds, gap, seed, pad_octave, brightness)
        target = PUBLIC_MUSIC_DIR / name
        write_wav(target, samples)
        print(f"{target}  {target.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
