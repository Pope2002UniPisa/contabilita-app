import json
import os
import config


def _azienda_file():
    return os.path.join(config.get_data_dir(), "azienda.json")


def _clienti_file():
    return os.path.join(config.get_data_dir(), "clienti.json")


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
    p = _azienda_file()
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return _AZIENDA_DEFAULT.copy()


def salva_azienda(dati):
    p = _azienda_file()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)


def carica_clienti():
    p = _clienti_file()
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return []


def salva_clienti(lista):
    p = _clienti_file()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)
