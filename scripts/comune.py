"""Funzioni condivise dagli script del progetto."""
import json
from pathlib import Path

# cartella principale del progetto (quella che contiene spots.json)
RADICE = Path(__file__).resolve().parent.parent


def carica_spot():
    """Legge le schede degli spot da spots.json."""
    with open(RADICE / "spots.json", encoding="utf-8") as f:
        return json.load(f)
