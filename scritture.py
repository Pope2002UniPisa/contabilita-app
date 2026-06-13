"""
Genera le scritture in partita doppia per una fattura passiva.
Gestisce il caso standard (IVA italiana) e il reverse charge intra-UE.

Convenzione: ogni scrittura è una lista di righe {conto, descr, dare, avere}.
Il totale Dare deve sempre uguagliare il totale Avere.
"""
from piano_conti import descrizione


def scrittura_fattura_passiva(fattura, conto_costo):
    """
    Caso standard (fornitore italiano):
      Dare  Costo            imponibile
      Dare  IVA a credito    imposta
      Avere Debiti fornitori totale
    """
    righe = []
    imp = fattura["imponibile"]
    iva = fattura["imposta"]
    tot = fattura["totale"]

    if fattura.get("intra_ue"):
        return scrittura_reverse_charge(fattura, conto_costo)

    righe.append({"conto": conto_costo, "descr": descrizione(conto_costo),
                  "dare": imp, "avere": 0.0})
    if iva > 0:
        righe.append({"conto": "18", "descr": descrizione("18"),
                      "dare": iva, "avere": 0.0})
    righe.append({"conto": "40", "descr": descrizione("40"),
                  "dare": 0.0, "avere": tot})
    return righe


def scrittura_reverse_charge(fattura, conto_costo):
    """
    Acquisto intra-UE (es. Romania): il fornitore fattura SENZA IVA.
    Si auto-applica l'IVA italiana, registrandola SIA a debito SIA a credito
    (saldo zero), come prescrive il reverse charge.

      Dare  Costo            imponibile
      Avere Debiti fornitori imponibile
      ---- integrazione IVA (aliquota IT, qui 22%) ----
      Dare  IVA a credito    iva_teorica
      Avere IVA a debito     iva_teorica
    """
    righe = []
    imp = fattura["imponibile"]
    aliquota_it = 22.0  # aliquota ordinaria italiana applicata in reverse charge
    iva_teorica = round(imp * aliquota_it / 100, 2)

    righe.append({"conto": conto_costo, "descr": descrizione(conto_costo),
                  "dare": imp, "avere": 0.0})
    righe.append({"conto": "40", "descr": descrizione("40") + " (intra-UE)",
                  "dare": 0.0, "avere": imp})
    righe.append({"conto": "18", "descr": descrizione("18") + " (reverse charge)",
                  "dare": iva_teorica, "avere": 0.0})
    righe.append({"conto": "45", "descr": descrizione("45") + " (reverse charge)",
                  "dare": 0.0, "avere": iva_teorica})
    return righe


def scrittura_incasso_fattura_attiva(registrazione):
    """
    Quando il cliente paga: Banca c/c a Crediti vs clienti.
    registrazione = elemento del giornale di tipo 'attiva'
    """
    totale = sum(r["dare"] for r in registrazione["righe"] if r["conto"] == "15")
    return [
        {"conto": "20", "descr": "Banca c/c",
         "dare": totale, "avere": 0.0},
        {"conto": "15", "descr": f"Crediti c/ {registrazione['fornitore']}",
         "dare": 0.0,   "avere": totale},
    ]


def verifica_quadratura(righe):
    """Controlla che Dare == Avere (regola fondamentale partita doppia)."""
    tot_dare = round(sum(r["dare"] for r in righe), 2)
    tot_avere = round(sum(r["avere"] for r in righe), 2)
    return abs(tot_dare - tot_avere) < 0.01, tot_dare, tot_avere
