"""
Generatore di fatture attive in formato FatturaPA (XML per lo SdI).
"""
import os
import json
import datetime
import xml.etree.ElementTree as ET
import config


def _counter_file():
    return os.path.join(config.get_data_dir(), "progressivo_fatture.json")


def prossimo_numero(anno=None):
    anno = anno or datetime.date.today().year
    path = _counter_file()
    counter = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            counter = json.load(f)
    n = counter.get(str(anno), 0) + 1
    counter[str(anno)] = n
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(counter, f)
    return n


def _sub(parent, tag, text=None):
    el = ET.SubElement(parent, tag)
    if text is not None:
        el.text = str(text)
    return el


def genera_xml(fattura: dict, azienda: dict) -> str:
    NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
    ET.register_namespace("p", NS)
    root = ET.Element(f"{{{NS}}}FatturaElettronica", versione="FPR12")

    hdr = _sub(root, "FatturaElettronicaHeader")
    dt  = _sub(hdr, "DatiTrasmissione")
    idt = _sub(dt, "IdTrasmittente")
    _sub(idt, "IdPaese", azienda.get("nazione", "IT"))
    _sub(idt, "IdCodice", azienda.get("piva", ""))
    _sub(dt, "ProgressivoInvio", f"{fattura['numero']:05d}")
    _sub(dt, "FormatoTrasmissione", "FPR12")
    cliente = fattura["cliente"]
    _sub(dt, "CodiceDestinatario", cliente.get("codice_sdi") or "0000000")

    ced    = _sub(hdr, "CedentePrestatore")
    da_ced = _sub(ced, "DatiAnagrafici")
    idf    = _sub(da_ced, "IdFiscaleIVA")
    _sub(idf, "IdPaese",  azienda.get("nazione", "IT"))
    _sub(idf, "IdCodice", azienda.get("piva", ""))
    if azienda.get("codice_fiscale"):
        _sub(da_ced, "CodiceFiscale", azienda["codice_fiscale"])
    an = _sub(da_ced, "Anagrafica")
    _sub(an, "Denominazione", azienda.get("denominazione", ""))
    _sub(da_ced, "RegimeFiscale", azienda.get("regime_fiscale", "RF01"))
    sede = _sub(ced, "Sede")
    _sub(sede, "Indirizzo", azienda.get("via", ""))
    _sub(sede, "CAP",       azienda.get("cap", "00000"))
    _sub(sede, "Comune",    azienda.get("comune", ""))
    if azienda.get("provincia"):
        _sub(sede, "Provincia", azienda["provincia"])
    _sub(sede, "Nazione", azienda.get("nazione", "IT"))

    cess    = _sub(hdr, "CessionarioCommittente")
    da_cess = _sub(cess, "DatiAnagrafici")
    if cliente.get("piva"):
        idf2 = _sub(da_cess, "IdFiscaleIVA")
        _sub(idf2, "IdPaese",  cliente.get("paese", "IT"))
        _sub(idf2, "IdCodice", cliente["piva"])
    if cliente.get("codice_fiscale"):
        _sub(da_cess, "CodiceFiscale", cliente["codice_fiscale"])
    an2 = _sub(da_cess, "Anagrafica")
    _sub(an2, "Denominazione", cliente.get("denominazione", ""))
    sede_cl = _sub(cess, "Sede")
    _sub(sede_cl, "Indirizzo", cliente.get("via", ""))
    _sub(sede_cl, "CAP",       cliente.get("cap", "00000"))
    _sub(sede_cl, "Comune",    cliente.get("comune", ""))
    if cliente.get("provincia"):
        _sub(sede_cl, "Provincia", cliente["provincia"])
    _sub(sede_cl, "Nazione", cliente.get("nazione", "IT"))

    body = _sub(root, "FatturaElettronicaBody")
    dg   = _sub(body, "DatiGenerali")
    dgd  = _sub(dg, "DatiGeneraliDocumento")
    _sub(dgd, "TipoDocumento", fattura.get("tipo_doc", "TD01"))
    _sub(dgd, "Divisa", "EUR")
    _sub(dgd, "Data",   fattura["data"])
    _sub(dgd, "Numero", str(fattura["numero"]))

    righe = fattura.get("righe", [])
    totali: dict[float, dict] = {}
    for riga in righe:
        al  = float(riga.get("aliquota_iva", 22))
        qt  = float(riga.get("quantita", 1))
        pr  = float(riga.get("prezzo_unitario", 0))
        tot = round(qt * pr, 2)
        if al not in totali:
            totali[al] = {"imponibile": 0.0, "imposta": 0.0}
        totali[al]["imponibile"] += tot
        totali[al]["imposta"]    += round(tot * al / 100, 2)

    totale_doc = round(sum(v["imponibile"] + v["imposta"] for v in totali.values()), 2)
    _sub(dgd, "ImportoTotaleDocumento", f"{totale_doc:.2f}")

    dbs = _sub(body, "DatiBeniServizi")
    for i, riga in enumerate(righe, 1):
        qt  = float(riga.get("quantita", 1))
        pr  = float(riga.get("prezzo_unitario", 0))
        al  = float(riga.get("aliquota_iva", 22))
        tot = round(qt * pr, 2)
        dl  = _sub(dbs, "DettaglioLinee")
        _sub(dl, "NumeroLinea",    str(i))
        _sub(dl, "Descrizione",    riga.get("descrizione", ""))
        _sub(dl, "Quantita",       f"{qt:.2f}")
        _sub(dl, "PrezzoUnitario", f"{pr:.2f}")
        _sub(dl, "PrezzoTotale",   f"{tot:.2f}")
        _sub(dl, "AliquotaIVA",    f"{al:.2f}")

    for al, vals in totali.items():
        dr = _sub(dbs, "DatiRiepilogo")
        _sub(dr, "AliquotaIVA",       f"{al:.2f}")
        _sub(dr, "ImponibileImporto", f"{vals['imponibile']:.2f}")
        _sub(dr, "Imposta",           f"{vals['imposta']:.2f}")
        _sub(dr, "EsigibilitaIVA",    "I")

    dp  = _sub(body, "DatiPagamento")
    _sub(dp, "CondizioniPagamento", "TP02")
    ddp = _sub(dp, "DettaglioPagamento")
    _sub(ddp, "ModalitaPagamento", fattura.get("modalita_pagamento", "MP05"))
    _sub(ddp, "ImportoPagamento",  f"{totale_doc:.2f}")

    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str


def salva_fattura_xml(fattura: dict, azienda: dict, dest_dir: str) -> str:
    xml  = genera_xml(fattura, azienda)
    piva = (azienda.get("piva") or "XXXXXXXX").replace(" ", "")
    nome = f"IT{piva}_{fattura['numero']:05d}.xml"
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, nome)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    return path


def fattura_a_registrazione(fattura: dict, azienda: dict) -> dict:
    righe    = fattura.get("righe", [])
    imp      = round(sum(float(r.get("quantita",1))*float(r.get("prezzo_unitario",0)) for r in righe), 2)
    iva      = round(sum(float(r.get("quantita",1))*float(r.get("prezzo_unitario",0))
                         * float(r.get("aliquota_iva",22))/100 for r in righe), 2)
    totale   = round(imp + iva, 2)
    cliente  = fattura["cliente"]
    return {
        "chiave":    f"ATTIVA|{azienda.get('piva','')}|{fattura['numero']}|{fattura['data']}",
        "data":      fattura["data"],
        "fornitore": cliente.get("denominazione", ""),
        "numero":    str(fattura["numero"]),
        "intra_ue":  cliente.get("paese", "IT") != "IT",
        "stato":     "registrata",
        "tipo":      "attiva",
        "righe": [
            {"conto":"15","descr":f"Crediti c/ {cliente.get('denominazione','')}",
             "dare":totale, "avere":0.0},
            {"conto":"80","descr":"Ricavi delle vendite",
             "dare":0.0,   "avere":imp},
            {"conto":"45","descr":"IVA a debito",
             "dare":0.0,   "avere":iva},
        ]
    }
