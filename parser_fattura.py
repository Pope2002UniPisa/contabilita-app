"""
Parser FatturaPA (formato elettronico standard italiano).
Legge un file XML e restituisce un dizionario con i dati essenziali.
Robusto rispetto ai namespace e a piccole varianti di struttura.
"""
import xml.etree.ElementTree as ET


def _strip_ns(tag):
    return tag.split("}")[-1] if "}" in tag else tag


def _find(elem, path_tags):
    """Cerca un percorso di tag ignorando i namespace. path_tags = lista di nomi."""
    cur = [elem]
    for tag in path_tags:
        nxt = []
        for e in cur:
            for child in e:
                if _strip_ns(child.tag) == tag:
                    nxt.append(child)
        cur = nxt
        if not cur:
            return []
    return cur


def _text(elem, path_tags, default=""):
    res = _find(elem, path_tags)
    return res[0].text.strip() if res and res[0].text else default


def parse_fattura(filepath):
    """Restituisce un dict con i dati della fattura, o solleva ValueError se non valida."""
    try:
        tree = ET.parse(filepath)
    except ET.ParseError as e:
        raise ValueError(f"XML non valido: {e}")
    root = tree.getroot()

    header = _find(root, ["FatturaElettronicaHeader"])
    body = _find(root, ["FatturaElettronicaBody"])
    if not header or not body:
        raise ValueError("Struttura FatturaPA non riconosciuta (manca Header o Body)")
    header, body = header[0], body[0]

    # Cedente/prestatore (chi emette la fattura = il fornitore se è passiva)
    ced = _find(header, ["CedentePrestatore"])
    ced = ced[0] if ced else header
    denom = _text(ced, ["DatiAnagrafici", "Anagrafica", "Denominazione"])
    if not denom:
        # persona fisica: nome + cognome
        nome = _text(ced, ["DatiAnagrafici", "Anagrafica", "Nome"])
        cognome = _text(ced, ["DatiAnagrafici", "Anagrafica", "Cognome"])
        denom = f"{nome} {cognome}".strip()
    paese_ced = _text(ced, ["DatiAnagrafici", "IdFiscaleIVA", "IdPaese"], "IT")
    piva_ced = _text(ced, ["DatiAnagrafici", "IdFiscaleIVA", "IdCodice"])

    # Cessionario (chi riceve = la nostra azienda se passiva)
    cess = _find(header, ["CessionarioCommittente"])
    cess = cess[0] if cess else header
    denom_cess = _text(cess, ["DatiAnagrafici", "Anagrafica", "Denominazione"])

    # Dati documento
    docgen = _find(body, ["DatiGenerali", "DatiGeneraliDocumento"])
    docgen = docgen[0] if docgen else body
    tipo_doc = _text(docgen, ["TipoDocumento"], "TD01")
    data = _text(docgen, ["Data"])
    numero = _text(docgen, ["Numero"])
    totale = _text(docgen, ["ImportoTotaleDocumento"], "0")

    # Riepilogo IVA (può esserci più di un'aliquota: sommiamo)
    imponibile_tot = 0.0
    imposta_tot = 0.0
    aliquote = []
    nature = []
    for riep in _find(body, ["DatiBeniServizi", "DatiRiepilogo"]):
        imp = _text(riep, ["ImponibileImporto"], "0")
        iva = _text(riep, ["Imposta"], "0")
        al = _text(riep, ["AliquotaIVA"], "0")
        nat = _text(riep, ["Natura"])
        try:
            imponibile_tot += float(imp)
            imposta_tot += float(iva)
            aliquote.append(float(al))
            if nat:
                nature.append(nat)
        except ValueError:
            pass

    # Descrizione (prima riga di dettaglio)
    descr = ""
    linee = _find(body, ["DatiBeniServizi", "DettaglioLinee"])
    if linee:
        descr = _text(linee[0], ["Descrizione"])

    # Intra-UE: paese estero o natura N3.2 (non imponibili cessioni intra)
    intra_ue = (paese_ced != "IT") or any(n.startswith("N3") for n in nature)

    return {
        "file": filepath,
        "fornitore": denom,
        "paese_fornitore": paese_ced,
        "piva_fornitore": piva_ced,
        "cliente": denom_cess,
        "tipo_doc": tipo_doc,
        "data": data,
        "numero": numero,
        "imponibile": round(imponibile_tot, 2),
        "imposta": round(imposta_tot, 2),
        "totale": round(float(totale) if totale else imponibile_tot + imposta_tot, 2),
        "aliquota": aliquote[0] if aliquote else 0.0,
        "natura": nature[0] if nature else "",
        "intra_ue": intra_ue,
        "descrizione": descr,
    }
