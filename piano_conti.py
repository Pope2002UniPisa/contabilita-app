"""
Piano dei conti semplificato (schema italiano CEE).
Ogni conto ha: codice, descrizione, tipo (ATTIVO/PASSIVO/COSTO/RICAVO),
e la sezione di bilancio in cui confluisce (per la futura Fase 2).
"""

PIANO_CONTI = {
    # --- ATTIVO PATRIMONIALE ---
    "10": {"desc": "Immobilizzazioni materiali (cespiti)", "tipo": "ATTIVO", "sezione": "SP_B_II"},
    "15": {"desc": "Crediti verso clienti", "tipo": "ATTIVO", "sezione": "SP_C_II_1"},
    "18": {"desc": "IVA a credito", "tipo": "ATTIVO", "sezione": "SP_C_II_5bis"},
    "20": {"desc": "Banca c/c", "tipo": "ATTIVO", "sezione": "SP_C_IV_1"},
    "21": {"desc": "Cassa", "tipo": "ATTIVO", "sezione": "SP_C_IV_3"},

    # --- PASSIVO PATRIMONIALE ---
    "40": {"desc": "Debiti verso fornitori", "tipo": "PASSIVO", "sezione": "SP_D_7"},
    "45": {"desc": "IVA a debito", "tipo": "PASSIVO", "sezione": "SP_D_12"},
    "48": {"desc": "Erario c/IVA (saldo da versare)", "tipo": "PASSIVO", "sezione": "SP_D_12"},

    # --- COSTI (Conto Economico B) ---
    "60": {"desc": "Acquisto merci e materie prime", "tipo": "COSTO", "sezione": "CE_B_6"},
    "61": {"desc": "Utenze (energia, gas, acqua)", "tipo": "COSTO", "sezione": "CE_B_7"},
    "62": {"desc": "Carburante automezzi", "tipo": "COSTO", "sezione": "CE_B_7"},
    "63": {"desc": "Manutenzione automezzi", "tipo": "COSTO", "sezione": "CE_B_7"},
    "64": {"desc": "Manutenzione macchinari/impianti", "tipo": "COSTO", "sezione": "CE_B_7"},
    "65": {"desc": "Servizi vari (consulenze, grafica, ecc.)", "tipo": "COSTO", "sezione": "CE_B_7"},
    "66": {"desc": "Pasti e rappresentanza", "tipo": "COSTO", "sezione": "CE_B_7"},
    "67": {"desc": "Affitti e locazioni", "tipo": "COSTO", "sezione": "CE_B_8"},
    "68": {"desc": "Noleggi", "tipo": "COSTO", "sezione": "CE_B_8"},
    "69": {"desc": "Materiale d'ufficio e consumo", "tipo": "COSTO", "sezione": "CE_B_6"},

    # --- RICAVI (Conto Economico A) ---
    "80": {"desc": "Ricavi delle vendite e prestazioni", "tipo": "RICAVO", "sezione": "CE_A_1"},
}

def descrizione(codice):
    c = PIANO_CONTI.get(codice)
    return c["desc"] if c else f"Conto {codice}"

def tipo(codice):
    c = PIANO_CONTI.get(codice)
    return c["tipo"] if c else "?"

# Conti di costo selezionabili in fase di approvazione manuale
CONTI_COSTO = {k: v["desc"] for k, v in PIANO_CONTI.items() if v["tipo"] == "COSTO"}
CONTI_CESPITE = {"10": PIANO_CONTI["10"]["desc"]}
