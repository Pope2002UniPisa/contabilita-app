"""
Lettura/scrittura del template Excel di bilancio.
Mappa i saldi del giornale nelle celle corrette per anno corrente.
"""
import os
import shutil
import openpyxl

_DATI = os.path.join(os.path.dirname(__file__), "dati")
EXCEL_PATH = os.path.join(_DATI, "Bilancio.xlsx")

ANNO_COLONNE = {2022: "B", 2023: "C", 2024: "D", 2025: "E", 2026: "F", 2027: "G"}

# (foglio, riga, [conti], tipo_saldo)
# netto_d = dare - avere (attivo, costi)
# netto_a = avere - dare (passivo, ricavi)
MAPPA = [
    # ── CONTO ECONOMICO ─────────────────────────────────────
    ("CONTO ECONOMICO",  4,  ["80"],                      "netto_a"),
    ("CONTO ECONOMICO", 12,  ["60"],                      "netto_d"),
    ("CONTO ECONOMICO", 13,  ["61","62","63","64","65"],  "netto_d"),
    ("CONTO ECONOMICO", 14,  ["67","68"],                 "netto_d"),
    ("CONTO ECONOMICO", 28,  ["66","69"],                 "netto_d"),
    # ── SP — ATTIVO ─────────────────────────────────────────
    ("STATO PATRIMONIALE", 13, ["10"],                   "netto_d"),
    ("STATO PATRIMONIALE", 32, ["15"],                   "netto_d"),
    ("STATO PATRIMONIALE", 35, ["18"],                   "netto_d"),
    ("STATO PATRIMONIALE", 46, ["20"],                   "netto_d"),
    ("STATO PATRIMONIALE", 47, ["21"],                   "netto_d"),
    # ── SP — PASSIVO ────────────────────────────────────────
    ("STATO PATRIMONIALE", 88, ["40"],                   "netto_a"),
    ("STATO PATRIMONIALE", 91, ["45","48"],              "netto_a"),
]

FOGLI_DA_MOSTRARE = ["STATO PATRIMONIALE", "CONTO ECONOMICO", "INDICI"]


def collega_template(src_path):
    os.makedirs(_DATI, exist_ok=True)
    shutil.copy2(src_path, EXCEL_PATH)


def excel_collegato():
    return os.path.exists(EXCEL_PATH)


def _calcola(saldi, conti, tipo):
    d = sum(saldi.get(c, {}).get("dare", 0.0) for c in conti)
    a = sum(saldi.get(c, {}).get("avere", 0.0) for c in conti)
    if tipo == "netto_d": return round(d - a, 2)
    if tipo == "netto_a": return round(a - d, 2)
    if tipo == "dare":    return round(d, 2)
    return round(a, 2)


def aggiorna_bilancio(saldi, anno):
    if anno not in ANNO_COLONNE:
        raise ValueError(f"Anno {anno} non nel template (supportati: {list(ANNO_COLONNE)})")
    col = ANNO_COLONNE[anno]
    wb = openpyxl.load_workbook(EXCEL_PATH)
    # accumula per gestire più conti → stessa cella
    cell_val: dict = {}
    for foglio, riga, conti, tipo in MAPPA:
        key = (foglio, riga)
        val = _calcola(saldi, conti, tipo)
        cell_val[key] = cell_val.get(key, 0.0) + val
    for (foglio, riga), val in cell_val.items():
        if foglio in wb.sheetnames and val != 0:
            wb[foglio][f"{col}{riga}"] = round(val, 2)
    wb.save(EXCEL_PATH)


def leggi_foglio(nome):
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    if nome not in wb.sheetnames:
        return []
    ws = wb[nome]
    rows = []
    for row in ws.iter_rows():
        celle = []
        for cell in row:
            bg = bold = None
            try:
                fill = cell.fill
                if fill.fill_type == "solid":
                    rgb = fill.fgColor.rgb
                    if rgb and rgb not in ("00000000", "FF000000", "00FFFFFF", "FFFFFFFF"):
                        bg = "#" + rgb[-6:]
            except Exception:
                pass
            try:
                bold = bool(cell.font.bold)
            except Exception:
                bold = False
            celle.append({"value": cell.value, "bg": bg, "bold": bold})
        rows.append(celle)
    return rows
