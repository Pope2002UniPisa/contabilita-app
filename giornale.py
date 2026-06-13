"""
Libro giornale: archivio persistente delle registrazioni.
Salvato in JSON locale. Ogni registrazione contiene i dati fattura,
le righe in partita doppia e lo stato (registrata/da_approvare).
"""
import json
import os

GIORNALE_FILE = os.path.join(os.path.dirname(__file__), "dati", "giornale.json")


def carica():
    if os.path.exists(GIORNALE_FILE):
        with open(GIORNALE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def salva(registrazioni):
    os.makedirs(os.path.dirname(GIORNALE_FILE), exist_ok=True)
    with open(GIORNALE_FILE, "w", encoding="utf-8") as f:
        json.dump(registrazioni, f, ensure_ascii=False, indent=2)


def chiave_fattura(fattura):
    """ID univoco per evitare doppie registrazioni dello stesso file."""
    return f"{fattura['piva_fornitore']}|{fattura['numero']}|{fattura['data']}"


def gia_presente(registrazioni, fattura):
    k = chiave_fattura(fattura)
    return any(r.get("chiave") == k for r in registrazioni)


def saldi_per_conto(registrazioni):
    """Somma Dare-Avere per ogni conto (base per la Fase 2 - bilancio)."""
    saldi = {}
    for r in registrazioni:
        if r["stato"] != "registrata":
            continue
        for riga in r["righe"]:
            c = riga["conto"]
            saldi.setdefault(c, {"dare": 0.0, "avere": 0.0})
            saldi[c]["dare"] += riga["dare"]
            saldi[c]["avere"] += riga["avere"]
    return saldi
