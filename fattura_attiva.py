"""
Generatore di fatture attive in formato FatturaPA (XML per lo SdI).
"""
import os
import json
import datetime
import xml.etree.ElementTree as ET

_DATI = os.path.join(os.path.dirname(__file__), "dati")
_COUNTER_FILE = os.path.join(_DATI, "progressivo_fatture.json")
_EMESSE_DIR   = os.path.join(_DATI, "fatture_emesse")


def prossimo_numero(anno=None):
    anno = anno or datetime.date.today().year
    counter = {}
    if os.path.exists(_COUNTER_FILE):
        with open(_COUNTER_FILE, encoding="utf-8") as f:
            counter = json.load(f)
    n = counter.get(str(anno), 0) + 1
    counter[str(anno)] = n
    os.makedirs(_DATI, exist_ok=True)
    with open(_COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(counter, f)
    return n


def _sub(parent, tag, text=None):
    el = ET.SubElement(parent, tag)
    if text is not None:
        el.text = str(text)
    return el


def genera_xml(fattura: dict, azienda: dict) -> str:
    """
    fattura: {
      numero, data (YYYY-MM-DD), tipo_doc (TD01...),
      cliente: {denominazione, piva, paese, via, cap, comune, provincia, nazione, codice_sdi},
      righe: [{descrizione, quantita, prezzo_unitario, aliquota_iva}],
      modalita_pagamento: "MP05" (default bonifico)
    }
    """
    NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
    ET.register_namespace("p", NS)

    root = ET.Element(f"{{{NS}}}FatturaElettronica", versione="FPR12")

    # ── Header ────────────────────────────────────────────────────────────
    hdr = _sub(root, "FatturaElettronicaHeader")

    # Trasmissione
    dt = _sub(hdr, "DatiTrasmissione")
    idt = _sub(dt, "IdTrasmittente")
    _sub(idt, "IdPaese", azienda.get("nazione", "IT"))
    _sub(idt, "IdCodice", azienda.get("piva", ""))
    _sub(dt, "ProgressivoInvio", f"{fattura['numero']:05d}")
    _sub(dt, "FormatoTrasmissione", "FPR12")
    cliente = fattura["cliente"]
    _sub(dt, "CodiceDestinatario", cliente.get("codice_sdi") or "0000000")

    # Cedente (nostra azienda)
    ced = _sub(hdr, "CedentePrestatore")
    da_ced = _sub(ced, "DatiAnagrafici")
    idf = _sub(da_ced, "IdFiscaleIVA")
    _sub(idf, "IdPaese", azienda.get("nazione", "IT"))
    _sub(idf, "IdCodice", azienda.get("piva", ""))
    if azienda.get("codice_fiscale"):
        _sub(da_ced, "CodiceFiscale", azienda["codice_fiscale"])
    an = _sub(da_ced, "Anagrafica")
    _sub(an, "Denominazione", azienda.get("denominazione", ""))
    _sub(da_ced, "RegimeFiscale", azienda.get("regime_fiscale", "RF01"))
    sede_c = _sub(ced, "Sede")
    _sub(sede_c, "Indirizzo",  azienda.get("via", ""))
    _sub(sede_c, "CAP",        azienda.get("cap", "00000"))
    _sub(sede_c, "Comune",     azienda.get("comune", ""))
    if azienda.get("provincia"):
        _sub(sede_c, "Provincia", azienda["provincia"])
    _sub(sede_c, "Nazione", azienda.get("nazione", "IT"))

    # Cessionario (cliente)
    cess = _sub(hdr, "CessionarioCommittente")
    da_cess = _sub(cess, "DatiAnagrafici")
    if cliente.get("piva"):
        idf2 = _sub(da_cess, "IdFiscaleIVA")
        _sub(idf2, "IdPaese", cliente.get("paese", "IT"))
        _sub(idf2, "IdCodice", cliente["piva"])
    if cliente.get("codice_fiscale"):
        _sub(da_cess, "CodiceFiscale", cliente["codice_fiscale"])
    an2 = _sub(da_cess, "Anagrafica")
    _sub(an2, "Denominazione", cliente.get("denominazione", ""))
    sede_cl = _sub(cess, "Sede")
    _sub(sede_cl, "Indirizzo",  cliente.get("via", ""))
    _sub(sede_cl, "CAP",        cliente.get("cap", "00000"))
    _sub(sede_cl, "Comune",     cliente.get("comune", ""))
    if cliente.get("provincia"):
        _sub(sede_cl, "Provincia", cliente["provincia"])
    _sub(sede_cl, "Nazione", cliente.get("nazione", "IT"))

    # ── Body ──────────────────────────────────────────────────────────────
    body = _sub(root, "FatturaElettronicaBody")

    # Dati generali
    dg = _sub(body, "DatiGenerali")
    dgd = _sub(dg, "DatiGeneraliDocumento")
    _sub(dgd, "TipoDocumento", fattura.get("tipo_doc", "TD01"))
    _sub(dgd, "Divisa", "EUR")
    _sub(dgd, "Data",   fattura["data"])
    _sub(dgd, "Numero", str(fattura["numero"]))

    # Calcola importi
    righe = fattura.get("righe", [])
    # Raggruppa per aliquota
    totali_per_aliquota: dict[float, dict] = {}
    for riga in righe:
        al = float(riga.get("aliquota_iva", 22))
        qt = float(riga.get("quantita", 1))
        pr = float(riga.get("prezzo_unitario", 0))
        tot_riga = round(qt * pr, 2)
        if al not in totali_per_aliquota:
            totali_per_aliquota[al] = {"imponibile": 0.0, "imposta": 0.0}
        totali_per_aliquota[al]["imponibile"] += tot_riga
        totali_per_aliquota[al]["imposta"] += round(tot_riga * al / 100, 2)

    imponibile_tot = round(sum(v["imponibile"] for v in totali_per_aliquota.values()), 2)
    imposta_tot    = round(sum(v["imposta"] for v in totali_per_aliquota.values()), 2)
    totale_doc     = round(imponibile_tot + imposta_tot, 2)

    _sub(dgd, "ImportoTotaleDocumento", f"{totale_doc:.2f}")

    # Righe prodotto/servizio
    dbs = _sub(body, "DatiBeniServizi")
    for i, riga in enumerate(righe, 1):
        qt = float(riga.get("quantita", 1))
        pr = float(riga.get("prezzo_unitario", 0))
        al = float(riga.get("aliquota_iva", 22))
        tot_r = round(qt * pr, 2)
        dl = _sub(dbs, "DettaglioLinee")
        _sub(dl, "NumeroLinea",     str(i))
        _sub(dl, "Descrizione",     riga.get("descrizione", ""))
        _sub(dl, "Quantita",        f"{qt:.2f}")
        _sub(dl, "PrezzoUnitario",  f"{pr:.2f}")
        _sub(dl, "PrezzoTotale",    f"{tot_r:.2f}")
        _sub(dl, "AliquotaIVA",     f"{al:.2f}")

    # Riepilogo IVA (uno per aliquota)
    for al, vals in totali_per_aliquota.items():
        dr = _sub(dbs, "DatiRiepilogo")
        _sub(dr, "AliquotaIVA",       f"{al:.2f}")
        _sub(dr, "ImponibileImporto", f"{vals['imponibile']:.2f}")
        _sub(dr, "Imposta",           f"{vals['imposta']:.2f}")
        _sub(dr, "EsigibilitaIVA",    "I")

    # Pagamento
    dp = _sub(body, "DatiPagamento")
    _sub(dp, "CondizioniPagamento", "TP02")
    ddp = _sub(dp, "DettaglioPagamento")
    _sub(ddp, "ModalitaPagamento", fattura.get("modalita_pagamento", "MP05"))
    _sub(ddp, "ImportoPagamento",  f"{totale_doc:.2f}")

    ET.indent(root, space="  ")
    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes


def salva_fattura_xml(fattura: dict, azienda: dict, dest_dir: str) -> str:
    xml = genera_xml(fattura, azienda)
    piva = (azienda.get("piva") or "XXXXXXXX").replace(" ", "")
    nome = f"IT{piva}_{fattura['numero']:05d}.xml"
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, nome)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    return path


def fattura_a_registrazione(fattura: dict, azienda: dict) -> dict:
    """Trasforma la fattura attiva in un dict compatibile con giornale.registrazioni."""
    righe = fattura.get("righe", [])
    imponibile = round(sum(
        float(r.get("quantita", 1)) * float(r.get("prezzo_unitario", 0))
        for r in righe), 2)
    imposta = round(sum(
        float(r.get("quantita", 1)) * float(r.get("prezzo_unitario", 0))
        * float(r.get("aliquota_iva", 22)) / 100
        for r in righe), 2)
    totale = round(imponibile + imposta, 2)
    cliente = fattura["cliente"]
    return {
        "chiave": f"ATTIVA|{azienda.get('piva','')}|{fattura['numero']}|{fattura['data']}",
        "data":      fattura["data"],
        "fornitore": cliente.get("denominazione", ""),  # campo riutilizzato come controparte
        "numero":    str(fattura["numero"]),
        "intra_ue":  cliente.get("paese", "IT") != "IT",
        "stato":     "registrata",
        "tipo":      "attiva",
        "righe": [
            {"conto": "15", "descr": f"Crediti c/ {cliente.get('denominazione','')}",
             "dare": totale,  "avere": 0.0},
            {"conto": "80", "descr": "Ricavi delle vendite",
             "dare": 0.0,    "avere": imponibile},
            {"conto": "45", "descr": "IVA a debito",
             "dare": 0.0,    "avere": imposta},
        ]
    }
