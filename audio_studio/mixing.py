"""Mix defaults shared by validation and offline rendering, including older saves."""


MIX_RANGES = {
    "music_duck_db": (0, 18), "effects_duck_db": (0, 18),
    "compression": (0, 100), "duck_attack_ms": (50, 2000),
    "duck_release_ms": (100, 3000), "compressor_attack_ms": (5, 100),
    "compressor_release_ms": (100, 1500),
}


def mix_settings(state):
    return {
        "music_duck_db": 4 if state.get("ducking", True) else 0,
        "effects_duck_db": 2 if state.get("effects_ducking", False) else 0,
        "compression": 35 if state.get("speech_compression", False) else 0,
        "duck_attack_ms": 250, "duck_release_ms": 900,
        "compressor_attack_ms": 25, "compressor_release_ms": 350,
        **state.get("mix", {}),
    }
