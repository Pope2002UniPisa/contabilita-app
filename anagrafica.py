import json
import os

_DATI = os.path.join(os.path.dirname(__file__), "dati")
AZIENDA_FILE = os.path.join(_DATI, "azienda.json")
CLIENTI_FILE = os.path.join(_DATI, "clienti.json")

_AZIENDA_DEFAULT = {
    "denominazione": "",
    "piva": "",
    "codice_fiscale": "",
    "via": "",
    "cap": "",
    "comune": "",
    "provincia": "",
    "nazione": "IT",
    "regime_fiscale": "RF01",
    "codice_sdi": "0000000",
}


def carica_azienda():
    if os.path.exists(AZIENDA_FILE):
        with open(AZIENDA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return _AZIENDA_DEFAULT.copy()


def salva_azienda(dati):
    os.makedirs(_DATI, exist_ok=True)
    with open(AZIENDA_FILE, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)


def carica_clienti():
    if os.path.exists(CLIENTI_FILE):
        with open(CLIENTI_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def salva_clienti(lista):
    os.makedirs(_DATI, exist_ok=True)
    with open(CLIENTI_FILE, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)
