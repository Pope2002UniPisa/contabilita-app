"""Genera fatture XML di esempio in formato FatturaPA per testare l'app."""
import os

DIR = "/home/claude/contabilita_app/fatture_esempio"

def fattura_passiva(nome, prog, cedente_denom, piva_ced, data, numero, descr,
                    imponibile, aliquota=22.0, tipo_doc="TD01", regime="RF01",
                    intra=False, paese_ced="IT"):
    imposta = round(imponibile * aliquota / 100, 2)
    totale = round(imponibile + imposta, 2)
    natura = ""
    if intra:
        aliquota = 0.0
        imposta = 0.0
        totale = imponibile
        natura = "<Natura>N3.2</Natura>"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica versione="FPR12" xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <IdTrasmittente><IdPaese>{paese_ced}</IdPaese><IdCodice>{piva_ced}</IdCodice></IdTrasmittente>
      <ProgressivoInvio>{prog}</ProgressivoInvio>
      <FormatoTrasmissione>FPR12</FormatoTrasmissione>
      <CodiceDestinatario>ABCDEFG</CodiceDestinatario>
    </DatiTrasmissione>
    <CedentePrestatore>
      <DatiAnagrafici>
        <IdFiscaleIVA><IdPaese>{paese_ced}</IdPaese><IdCodice>{piva_ced}</IdCodice></IdFiscaleIVA>
        <Anagrafica><Denominazione>{cedente_denom}</Denominazione></Anagrafica>
        <RegimeFiscale>{regime}</RegimeFiscale>
      </DatiAnagrafici>
      <Sede><Indirizzo>Via Esempio 1</Indirizzo><CAP>56100</CAP><Comune>Pisa</Comune><Provincia>PI</Provincia><Nazione>{paese_ced}</Nazione></Sede>
    </CedentePrestatore>
    <CessionarioCommittente>
      <DatiAnagrafici>
        <IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>01234567890</IdCodice></IdFiscaleIVA>
        <Anagrafica><Denominazione>LA NOSTRA AZIENDA SRL</Denominazione></Anagrafica>
      </DatiAnagrafici>
      <Sede><Indirizzo>Via Aziendale 10</Indirizzo><CAP>56100</CAP><Comune>Pisa</Comune><Provincia>PI</Provincia><Nazione>IT</Nazione></Sede>
    </CessionarioCommittente>
  </FatturaElettronicaHeader>
  <FatturaElettronicaBody>
    <DatiGenerali>
      <DatiGeneraliDocumento>
        <TipoDocumento>{tipo_doc}</TipoDocumento>
        <Divisa>EUR</Divisa>
        <Data>{data}</Data>
        <Numero>{numero}</Numero>
        <ImportoTotaleDocumento>{totale:.2f}</ImportoTotaleDocumento>
      </DatiGeneraliDocumento>
    </DatiGenerali>
    <DatiBeniServizi>
      <DettaglioLinee>
        <NumeroLinea>1</NumeroLinea>
        <Descrizione>{descr}</Descrizione>
        <Quantita>1.00</Quantita>
        <PrezzoUnitario>{imponibile:.2f}</PrezzoUnitario>
        <PrezzoTotale>{imponibile:.2f}</PrezzoTotale>
        <AliquotaIVA>{aliquota:.2f}</AliquotaIVA>
        {natura}
      </DettaglioLinee>
      <DatiRiepilogo>
        <AliquotaIVA>{aliquota:.2f}</AliquotaIVA>
        {natura}
        <ImponibileImporto>{imponibile:.2f}</ImponibileImporto>
        <Imposta>{imposta:.2f}</Imposta>
      </DatiRiepilogo>
    </DatiBeniServizi>
  </FatturaElettronicaBody>
</p:FatturaElettronica>"""
    with open(os.path.join(DIR, nome), "w", encoding="utf-8") as f:
        f.write(xml)

# --- Fatture PASSIVE (ricevute) ---
fattura_passiva("IT00111223344_001.xml", "00001", "ENEL ENERGIA SPA", "00934061003",
                "2026-01-15", "2026/000123", "Fornitura energia elettrica dicembre", 450.00)
fattura_passiva("IT05544332211_001.xml", "00002", "Q8 PETROLEUM ITALIA SPA", "05544332211",
                "2026-01-20", "FT-889", "Rifornimento carburante automezzi", 180.00)
fattura_passiva("IT09988776655_001.xml", "00003", "AUTOFFICINA ROSSI SRL", "09988776655",
                "2026-02-03", "12/2026", "Tagliando e riparazione furgone", 620.00)
fattura_passiva("IT03344556677_001.xml", "00004", "IMMOBILIARE TOSCANA SRL", "03344556677",
                "2026-02-01", "AFF-02", "Canone locazione capannone febbraio", 2000.00)
fattura_passiva("IT07766554433_001.xml", "00005", "RISTORANTE DA MARIO", "07766554433",
                "2026-02-10", "55", "Pranzo di lavoro con cliente", 88.00, aliquota=10.0)
fattura_passiva("IT01122334455_001.xml", "00006", "FORNITORE MERCI ITALIA SPA", "01122334455",
                "2026-02-12", "2026-0456", "Acquisto merci per rivendita", 5400.00)
# Fornitore NUOVO non in regole -> deve finire in coda approvazione
fattura_passiva("IT08877665544_001.xml", "00007", "STUDIO GRAFICO PIXEL SNC", "08877665544",
                "2026-02-15", "44", "Progettazione materiale pubblicitario", 1200.00)
# Fattura INTRA-UE Romania -> reverse charge
fattura_passiva("RO12345678_001.xml", "00008", "ROMANIA COMPONENTS SRL", "RO12345678",
                "2026-02-18", "INV-2026-77", "Acquisto componenti", 3000.00,
                tipo_doc="TD01", regime="RF01", intra=True, paese_ced="RO")

print("Generati", len(os.listdir(DIR)), "file XML di esempio")
for f in sorted(os.listdir(DIR)):
    print("  -", f)
