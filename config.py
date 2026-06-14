"""
Configurazione centralizzata dei percorsi.
- DATA_DIR: cartella dati utente (fuori dal bundle, sincronizzabile)
- RESOURCES_DIR: risorse bundled (template Excel, icona, ecc.)
Leggere sempre tramite get_data_dir() per supportare cambio cartella a caldo.
"""
import os
import sys
import json
from pathlib import Path

_PREFS_FILE = Path.home() / ".contabilita_prefs.json"

_DEFAULT_DATA_DIR = Path.home() / "Documents" / "ContabilitaApp"


def _load_prefs() -> dict:
    if _PREFS_FILE.exists():
        try:
            return json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_prefs(p: dict):
    _PREFS_FILE.write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")


def get_resources_dir() -> str:
    """Cartella con le risorse bundled (template Excel, ecc.)."""
    if getattr(sys, "frozen", False):
        # py2app: l'eseguibile è in .app/Contents/MacOS/
        exe = os.path.dirname(sys.executable)
        return os.path.normpath(os.path.join(exe, "..", "Resources"))
    # In sviluppo: stessa cartella del sorgente
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir() -> str:
    """Cartella dati utente (scrivibile, fuori dal bundle)."""
    prefs = _load_prefs()
    custom = prefs.get("data_dir", "")
    if custom and os.path.isdir(custom):
        return custom
    path = str(_DEFAULT_DATA_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def set_data_dir(path: str):
    prefs = _load_prefs()
    prefs["data_dir"] = path
    _save_prefs(prefs)


# Codici FatturaPA con descrizione leggibile
TIPI_DOCUMENTO = [
    ("TD01", "TD01 — Fattura"),
    ("TD06", "TD06 — Parcella"),
    ("TD04", "TD04 — Nota di credito"),
    ("TD05", "TD05 — Nota di debito"),
    ("TD07", "TD07 — Fattura semplificata"),
    ("TD16", "TD16 — Integrazione reverse charge"),
    ("TD17", "TD17 — Integrazione acquisto servizi UE"),
    ("TD19", "TD19 — Integrazione acquisto beni UE"),
]

MODALITA_PAGAMENTO = [
    ("MP05", "MP05 — Bonifico bancario"),
    ("MP01", "MP01 — Contanti"),
    ("MP02", "MP02 — Assegno"),
    ("MP08", "MP08 — Carta di credito/debito"),
    ("MP10", "MP10 — RID utenze"),
    ("MP12", "MP12 — RIBA"),
    ("MP22", "MP22 — Trattenuta su somme già riscosse"),
]
