"""
Enumerazione dei dispositivi di ingresso audio disponibili sulla macchina,
usata dal menu Impostazioni di Electron per popolare la scelta del microfono
(un indice hardware non ha senso hardcoded: e' specifico di ogni macchina).
"""

from __future__ import annotations

import sounddevice as sd


def list_input_devices() -> list[dict[str, int | str]]:
    devices = sd.query_devices()
    return [
        {"index": i, "name": str(d["name"])}
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]
