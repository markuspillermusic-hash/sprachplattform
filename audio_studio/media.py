"""Local, bounded audio processing. Never use a client-supplied path or URL."""
import json
import math
import struct
import subprocess
from pathlib import Path

from django.conf import settings
from .mixing import mix_settings


class StudioError(ValueError):
    pass


INPUT_FORMATS = {".mp3": "mp3", ".wav": "wav", ".ogg": "ogg", ".flac": "flac", ".m4a": "mov"}


def stored_path(raw):
    path = Path(raw).resolve()
    if not path.is_relative_to(Path(settings.AUDIO_STORAGE_ROOT).resolve()) or not path.is_file():
        raise StudioError("Die Audiodatei ist nicht mehr verfügbar. Bitte erneut hinzufügen.")
    return path


def run(command, timeout=120):
    try:
        return subprocess.run(command, check=True, capture_output=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        raise StudioError("Die Audiodatei konnte nicht verarbeitet werden. Prüfen Sie das Format und die FFmpeg-Installation.") from None


def input_options(path):
    fmt = INPUT_FORMATS.get(Path(path).suffix.lower())
    if not fmt:
        raise StudioError("Unterstützte Formate: MP3, WAV, OGG, FLAC und M4A.")
    return ["-protocol_whitelist", "file,pipe", "-f", fmt, "-i", str(path)]


def probe(path):
    try:
        info = json.loads(run(["ffprobe", "-v", "error", *input_options(path),
                               "-show_entries", "format=duration:stream=codec_type", "-of", "json"]))
        duration = float(info["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        raise StudioError("Die Datei enthält keine lesbare Audiospur.") from None
    if not any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
        raise StudioError("Die Datei enthält keine Audiospur.")
    if not math.isfinite(duration) or not 0 < duration <= settings.AUDIO_STUDIO_MAX_DURATION + .08:
        raise StudioError("Audiodateien dürfen höchstens 30 Minuten lang sein.")
    return duration


def waveform(path):
    data = run(["ffmpeg", "-v", "error", *input_options(path), "-vn", "-t",
                str(settings.AUDIO_STUDIO_MAX_DURATION), "-ac", "1", "-ar", "1000",
                "-f", "f32le", "pipe:1"])
    samples = [abs(s[0]) for s in struct.iter_unpack("<f", data)]
    step = max(1, math.ceil(len(samples) / 600))
    return [round(min(1, max(samples[i:i + step])), 4) for i in range(0, len(samples), step)]


def peak_filter(source, target_peak=.6):
    data = run(["ffmpeg", "-v", "error", *input_options(source), "-vn", "-t",
                str(settings.AUDIO_STUDIO_MAX_DURATION), "-ac", "2", "-ar", "44100", "-f", "f32le", "pipe:1"])
    peak = max((abs(x[0]) for x in struct.iter_unpack("<f", data)), default=0)
    # Leave silence untouched; never boost more than 30 dB.
    factor = min(10 ** (30 / 20), target_peak / peak) if peak > .0001 else 1
    # Match the channel conversion used while measuring; mono-to-stereo applies gain.
    return f"aresample=44100,aformat=sample_rates=44100:channel_layouts=stereo,volume={factor:.8f},alimiter=limit=0.7:level=0:latency=1"


def normalize(source, target, *, target_peak=None):
    probe(source)
    command = ["ffmpeg", "-v", "error", *input_options(source), "-vn", "-map_metadata", "-1",
               "-t", str(settings.AUDIO_STUDIO_MAX_DURATION), "-ar", "44100", "-ac", "2"]
    if target_peak:
        command += ["-af", peak_filter(source, target_peak)]
    run(command + ["-c:a", "libmp3lame", "-b:a", "192k", "-y", str(target)])
    return probe(target), waveform(target)


def audible_tracks(state):
    solo = any(track["solo"] for track in state["tracks"].values())
    return {name for name, track in state["tracks"].items()
            if not track["mute"] and (not solo or track["solo"])}


def speech_intervals(state):
    intervals = sorted((c["start"], c["start"] + c["trim_end"] - c["trim_start"])
                       for c in state["clips"] if c["track"] == "speech")
    result = []
    for start, end in intervals:
        if result and start <= result[-1][1] + mix_settings(state)["duck_release_ms"] / 1000:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def render_mix(state, assets, target, output_format):
    mix = mix_settings(state)
    audible = audible_tracks(state)
    clips = [c for c in state["clips"] if c["track"] in audible]
    if not clips:
        raise StudioError("Für den Export muss mindestens ein Clip hörbar sein.")
    duration = max(c["start"] + c["trim_end"] - c["trim_start"] for c in clips)
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    filters, labels = [], {name: [] for name in audible}
    for i, clip in enumerate(clips):
        command.extend(input_options(stored_path(assets[clip["asset_id"]].file_path)))
        length = clip["trim_end"] - clip["trim_start"]
        f = (f"[{i}:a]atrim=start={clip['trim_start']}:end={clip['trim_end']},asetpts=PTS-STARTPTS,"
             "aresample=44100,aformat=sample_rates=44100:channel_layouts=stereo,"
             f"volume={10 ** (clip['gain_db'] / 20):.8f}")
        if clip["fade_in"]:
            f += f",afade=t=in:st=0:d={clip['fade_in']}"
        if clip["fade_out"]:
            f += f",afade=t=out:st={length - clip['fade_out']:.6f}:d={clip['fade_out']}"
        f += f",adelay={round(clip['start'] * 1000)}:all=1[c{i}]"
        filters.append(f)
        labels[clip["track"]].append(f"[c{i}]")
    output_labels = []
    for track, inputs in labels.items():
        if not inputs:
            continue
        f = "".join(inputs) + f"amix=inputs={len(inputs)}:normalize=0:dropout_transition=0,apad,atrim=duration={duration},"
        f += f"volume={10 ** (state['tracks'][track]['gain_db'] / 20):.8f}"
        if track == "speech" and mix["compression"]:
            amount = mix["compression"] / 100
            f += (f",acompressor=threshold=0.12589254:ratio={1 + 2 * amount:.6f}:"
                  f"attack={mix['compressor_attack_ms']}:release={mix['compressor_release_ms']}:"
                  f"knee=2:makeup={10 ** (2 * amount / 20):.8f}:link=maximum:detection=rms")
        duck_db = mix["music_duck_db"] if track == "music" else mix["effects_duck_db"] if track == "effects" else 0
        duck = duck_db > 0
        if duck and "speech" in audible:
            attack, release = mix["duck_attack_ms"] / 1000, mix["duck_release_ms"] / 1000
            envelopes = [f"min(1,min(max(0,(t-{start - attack:.6f})/{attack}),max(0,({end + release:.6f}-t)/{release})))"
                         for start, end in speech_intervals(state)]
            if envelopes:
                envelope = envelopes[0]
                for expression in envelopes[1:]:
                    envelope = f"max({envelope},{expression})"
                smooth = f"(({envelope})*({envelope})*(3-2*({envelope})))"
                f += f",volume='pow(10,-{duck_db}*{smooth}/20)':eval=frame"
        filters.append(f + f"[{track}]")
        output_labels.append(f"[{track}]")
    filters.append("".join(output_labels) + f"amix=inputs={len(output_labels)}:normalize=0:dropout_transition=0,"
                   "volume=0.8,alimiter=limit=0.95:level=0:attack=5:release=250:latency=1[out]")
    command += ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", str(duration),
                "-map_metadata", "-1"]
    command += (["-c:a", "pcm_s16le"] if output_format == "wav" else ["-c:a", "libmp3lame", "-b:a", "192k"])
    command += ["-y", str(target)]
    run(command, timeout=600)
    return probe(target), waveform(target)
