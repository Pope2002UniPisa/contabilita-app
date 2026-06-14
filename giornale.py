import json
import os
import config


def _path():
    return os.path.join(config.get_data_dir(), "giornale.json")


def carica():
    p = _path()
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return []


def salva(registrazioni):
    p = _path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(registrazioni, f, ensure_ascii=False, indent=2)


def chiave_fattura(fattura):
    return f"{fattura['piva_fornitore']}|{fattura['numero']}|{fattura['data']}"


def gia_presente(registrazioni, fattura):
    k = chiave_fattura(fattura)
    return any(r.get("chiave") == k for r in registrazioni)


def saldi_per_conto(registrazioni):
    saldi = {}
    for r in registrazioni:
        if r.get("stato") != "registrata":
            continue
        for riga in r["righe"]:
            c = riga["conto"]
            saldi.setdefault(c, {"dare": 0.0, "avere": 0.0})
            saldi[c]["dare"]  += riga["dare"]
            saldi[c]["avere"] += riga["avere"]
    return saldi
