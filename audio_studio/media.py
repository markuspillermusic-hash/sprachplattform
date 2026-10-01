"""Local, bounded audio processing. Never use a client-supplied path or URL."""
import json
import math
import struct
import subprocess
from pathlib import Path

from django.conf import settings


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
    if not math.isfinite(duration) or not 0 < duration <= settings.AUDIO_STUDIO_MAX_DURATION:
        raise StudioError("Audiodateien dürfen höchstens 30 Minuten lang sein.")
    return duration


def waveform(path):
    data = run(["ffmpeg", "-v", "error", *input_options(path), "-vn", "-t",
                str(settings.AUDIO_STUDIO_MAX_DURATION), "-ac", "1", "-ar", "1000",
                "-f", "f32le", "pipe:1"])
    samples = [abs(s[0]) for s in struct.iter_unpack("<f", data)]
    step = max(1, math.ceil(len(samples) / 600))
    return [round(min(1, max(samples[i:i + step])), 4) for i in range(0, len(samples), step)]


def normalize(source, target):
    probe(source)
    run(["ffmpeg", "-v", "error", *input_options(source), "-vn", "-map_metadata", "-1",
         "-t", str(settings.AUDIO_STUDIO_MAX_DURATION), "-ar", "44100", "-ac", "2",
         "-c:a", "libmp3lame", "-b:a", "192k", "-y", str(target)])
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
        if result and start <= result[-1][1] + 0.3:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def render_mix(state, assets, target, output_format):
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
        if track == "speech" and state.get("speech_compression", False):
            f += ",acompressor=threshold=0.12589254:ratio=3:attack=10:release=150:knee=2:makeup=1.41253754:link=maximum:detection=peak"
        duck = ((track == "music" and state["ducking"])
                or (track == "effects" and state.get("effects_ducking", False)))
        if duck and "speech" in audible:
            envelopes = [f"min(1,min(max(0,(t-{start - .15:.6f})/0.15),max(0,({end + .15:.6f}-t)/0.15)))"
                         for start, end in speech_intervals(state)]
            if envelopes:
                envelope = envelopes[0]
                for expression in envelopes[1:]:
                    envelope = f"max({envelope},{expression})"
                reduction = 0.75 if track == "music" else 0.5
                f += f",volume='1-{reduction}*({envelope})':eval=frame"
        filters.append(f + f"[{track}]")
        output_labels.append(f"[{track}]")
    filters.append("".join(output_labels) + f"amix=inputs={len(output_labels)}:normalize=0:dropout_transition=0,"
                   "volume=0.8,alimiter=limit=0.95:level=0:latency=1[out]")
    command += ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", str(duration),
                "-map_metadata", "-1"]
    command += (["-c:a", "pcm_s16le"] if output_format == "wav" else ["-c:a", "libmp3lame", "-b:a", "192k"])
    command += ["-y", str(target)]
    run(command, timeout=600)
    return probe(target), waveform(target)
