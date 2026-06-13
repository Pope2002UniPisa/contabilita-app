"""
Motore di codifica: decide il conto di costo per una fattura passiva.
1. Cerca una regola per P.IVA fornitore (le più affidabili, "imparate").
2. Altrimenti cerca per parole chiave nella descrizione/denominazione.
3. Se nessuna corrisponde -> ritorna None (la fattura va in coda APPROVAZIONE).

Le regole per P.IVA sono salvate su file JSON e crescono man mano che approvi.
"""
import json
import os

REGOLE_FILE = os.path.join(os.path.dirname(__file__), "dati", "regole.json")

# Regole iniziali per parole chiave (categorie indicate da Leonardo)
REGOLE_KEYWORD = [
    (["energia", "enel", "gas", "acqua", "luce", "utenze", "eni gas"], "61"),
    (["carburante", "rifornimento", "q8", "benzina", "gasolio", "diesel", "eni station"], "62"),
    (["officina", "tagliando", "riparazione furgone", "riparazione auto", "gomme", "pneumatici"], "63"),
    (["manutenzione macchin", "manutenzione impiant", "riparazione macchin"], "64"),
    (["affitto", "locazione", "canone locazione", "immobiliare"], "67"),
    (["noleggio", "rent", "autonoleggio"], "68"),
    (["pranzo", "cena", "ristorante", "bar ", "catering", "pasti"], "66"),
    (["merci", "materie prime", "materiale per rivendita", "acquisto merci"], "60"),
    (["cancelleria", "materiale ufficio", "toner", "carta ", "articoli ufficio"], "69"),
    (["consulenza", "grafica", "progettazione", "servizi", "pubblicit"], "65"),
]


def carica_regole_piva():
    if os.path.exists(REGOLE_FILE):
        with open(REGOLE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def salva_regola_piva(piva, conto):
    """Memorizza l'associazione fornitore->conto (apprendimento)."""
    regole = carica_regole_piva()
    regole[piva] = conto
    os.makedirs(os.path.dirname(REGOLE_FILE), exist_ok=True)
    with open(REGOLE_FILE, "w", encoding="utf-8") as f:
        json.dump(regole, f, ensure_ascii=False, indent=2)


def proponi_conto(fattura):
    """
    Restituisce (conto, motivo, certo).
    certo=True  -> registrazione automatica
    certo=False -> proposta da approvare (conto può essere None)
    """
    piva = fattura.get("piva_fornitore", "")
    regole_piva = carica_regole_piva()

    # 1) Regola appresa per P.IVA: massima affidabilità -> automatico
    if piva in regole_piva:
        return regole_piva[piva], "regola fornitore (appresa)", True

    # 2) Parole chiave
    testo = (fattura.get("descrizione", "") + " " + fattura.get("fornitore", "")).lower()
    for chiavi, conto in REGOLE_KEYWORD:
        if any(k in testo for k in chiavi):
            return conto, f"parola chiave riconosciuta", False  # proposta, da confermare

    # 3) Nessuna corrispondenza
    return None, "fornitore/voce sconosciuti", False
