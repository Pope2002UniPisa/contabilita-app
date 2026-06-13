# Contabilità Automatica — Fase 1

App desktop per leggere le fatture elettroniche (FatturaPA), proporne la
contabilizzazione in partita doppia e tenere il libro giornale interno.

> **Importante**: questo è uno strumento gestionale interno per *vedere e
> capire i numeri in tempo reale*. **Non sostituisce la contabilità ufficiale**
> (che resta su Aruba / Fatture in Cloud e sotto la responsabilità del
> commercialista). È un affiancamento analitico, non il registro fiscale legale.

## Requisiti

Solo **Python 3** (tkinter è incluso di serie). Nessuna libreria da installare.

## Come si avvia

Apri il Terminale nella cartella del progetto e lancia:

```bash
python3 app.py
```

## Come si usa

1. **Esporta gli XML** delle fatture da Aruba o Fatture in Cloud in una cartella.
2. Nell'app, clicca **"Importa cartella fatture (XML)"** e seleziona quella cartella.
3. Le fatture di fornitori già noti vengono **registrate automaticamente**.
   Le altre finiscono nella scheda **"Da approvare"**.
4. Per ogni fattura da approvare: selezionala, scegli il **conto** dal menu
   (l'app propone già quello più probabile), e clicca **"Approva e registra"**.
   Lasciando attiva la spunta *"Memorizza regola per questo fornitore"*, la
   prossima fattura di quel fornitore sarà registrata da sola.
5. La scheda **"Libro giornale"** mostra tutte le scritture in partita doppia,
   con il controllo di quadratura Dare = Avere.
6. La scheda **"Prospetto IVA"** calcola IVA a credito, a debito e il saldo
   (da versare o credito da riportare).

## Cosa gestisce già

- Lettura XML FatturaPA standard (qualsiasi fornitore, formato ufficiale).
- Estrazione di imponibile, IVA, fornitore, data, numero.
- Codifica automatica per fornitore (appresa) e per parole chiave.
- Coda di approvazione per i casi dubbi, con proposta del conto.
- Registrazione in **partita doppia** con verifica di quadratura.
- **Reverse charge intra-UE** (es. acquisti dalla Romania): IVA auto-applicata
  a debito e a credito, saldo zero, come prescrive la norma.
- Prospetto IVA periodico.
- Esportazione del giornale in CSV.
- Anti-duplicati (la stessa fattura non viene registrata due volte).

## Cosa NON fa ancora (fasi successive)

- **Fase 2**: collegamento automatico ai prospetti di bilancio (SP, CE) nel
  template Excel.
- **Fase 3**: emissione delle fatture attive in formato XML per lo SdI.

## File del progetto

- `app.py` — interfaccia grafica e flusso principale
- `parser_fattura.py` — lettura degli XML FatturaPA
- `piano_conti.py` — piano dei conti (modificabile)
- `motore_codifica.py` — regole fornitore→conto e parole chiave
- `scritture.py` — generazione partita doppia + reverse charge
- `giornale.py` — archivio persistente delle registrazioni
- `genera_esempi.py` — genera fatture XML di test (cartella `fatture_esempio/`)
- `dati/` — qui vengono salvati giornale e regole apprese (JSON locali)

## Personalizzazione

- Per aggiungere/rinominare conti: modifica `piano_conti.py`.
- Per aggiungere regole automatiche per parole chiave: modifica la lista
  `REGOLE_KEYWORD` in `motore_codifica.py`.
