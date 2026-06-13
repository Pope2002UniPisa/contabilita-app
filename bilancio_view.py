"""
Rendering del template Excel di bilancio in una tab tkinter.
Usa un Canvas scrollabile per replicare l'aspetto del foglio.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import datetime

import bilancio_excel as bx

COL_A_W   = 380
COL_YR_W  = 80
ROW_H     = 21
ANNI      = [2022, 2023, 2024, 2025, 2026, 2027]
N_COLS    = 7   # col A + 6 anni
TOTAL_W   = COL_A_W + COL_YR_W * 6

_PALETTE = {
    "FFFFFF00": "#FFF0A0",  # giallo → oro morbido
    "FFD9D9D9": "#D9D9D9",  # grigio sezione
    "FFF2F2F2": "#F2F2F2",  # grigio chiaro totale
    "FFA9D08E": "#A9D08E",  # verde risultato
    "FFFF0000": "#FF4444",
}

def _tk_color(hex8):
    if not hex8:
        return None
    key = hex8.upper().lstrip("#")
    if len(key) == 8:
        return _PALETTE.get("FF" + key[2:]) or ("#" + key[2:])
    if len(key) == 6:
        return "#" + key
    return None


def _fmt(val):
    if val is None:
        return ""
    if isinstance(val, (int, float)):
        v = float(val)
        if v == 0:
            return ""
        if abs(v) >= 1:
            return f"{v:,.0f}".replace(",", ".")
        return f"{v:.2f}"
    return str(val)


class SheetCanvas(tk.Frame):
    def __init__(self, parent, rows):
        super().__init__(parent, bg="white")
        self._canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical",   command=self._canvas.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<MouseWheel>",       self._on_scroll)
        self._canvas.bind("<Button-4>",         self._on_scroll)
        self._canvas.bind("<Button-5>",         self._on_scroll)
        self.render(rows)

    def _on_scroll(self, e):
        delta = -1 if (getattr(e, "delta", 0) > 0 or e.num == 4) else 1
        self._canvas.yview_scroll(delta, "units")

    def render(self, rows):
        c = self._canvas
        c.delete("all")
        col_ws = [COL_A_W] + [COL_YR_W] * 6
        y = 0
        for row in rows:
            # Determina bg di riga dalla prima cella con colore
            row_bg = "white"
            for cell in row:
                clr = _tk_color(cell.get("bg"))
                if clr:
                    row_bg = clr
                    break
            x = 0
            for ci in range(N_COLS):
                w = col_ws[ci]
                cell = row[ci] if ci < len(row) else {}
                bg = _tk_color(cell.get("bg")) or row_bg
                bold = cell.get("bold", False)
                val  = _fmt(cell.get("value"))
                c.create_rectangle(x, y, x + w, y + ROW_H, fill=bg, outline="#D0D0D0", width=0)
                if val:
                    font = ("Helvetica", 9, "bold") if bold else ("Helvetica", 9)
                    if ci == 0:
                        c.create_text(x + 6, y + ROW_H // 2, text=val, font=font,
                                      anchor="w", fill="black")
                    else:
                        c.create_text(x + w - 5, y + ROW_H // 2, text=val, font=font,
                                      anchor="e", fill="black")
                x += w
            y += ROW_H
        c.configure(scrollregion=(0, 0, TOTAL_W, y))


class BilancioView(ttk.Frame):
    def __init__(self, parent, get_saldi_fn):
        super().__init__(parent)
        self._get_saldi = get_saldi_fn
        self._sheet_canvases: dict[str, SheetCanvas] = {}
        self._build()

    def _build(self):
        # ── toolbar ──────────────────────────────────────────────────────
        tb = ttk.Frame(self, padding=(6, 4))
        tb.pack(fill="x")

        ttk.Button(tb, text="🔗 Collega template Excel",
                   command=self._collega).pack(side="left")
        ttk.Button(tb, text="🔄 Aggiorna da giornale",
                   command=self._aggiorna).pack(side="left", padx=6)

        self._lbl_anno = ttk.Label(tb, text="")
        self._lbl_anno.pack(side="left", padx=8)

        ttk.Button(tb, text="📂 Apri in Excel",
                   command=self._apri_excel).pack(side="right")

        self._anno_var = tk.IntVar(value=datetime.date.today().year)
        ttk.Label(tb, text="Anno:").pack(side="right", padx=(12, 2))
        ttk.Spinbox(tb, from_=2022, to=2027, width=5,
                    textvariable=self._anno_var).pack(side="right")

        # ── contenuto ────────────────────────────────────────────────────
        self._placeholder = ttk.Label(
            self, text="\n\n  📊  Nessun template collegato.\n"
                       "  Clicca 'Collega template Excel' per selezionare il file .xlsx.\n",
            font=("Helvetica", 12), foreground="#888888")

        self._nb = ttk.Notebook(self)

        if bx.excel_collegato():
            self._carica_fogli()
        else:
            self._placeholder.pack(fill="both", expand=True)

    def _carica_fogli(self):
        self._placeholder.pack_forget()
        for tab_id in self._nb.tabs():
            self._nb.forget(tab_id)
        self._sheet_canvases.clear()

        for nome in bx.FOGLI_DA_MOSTRARE:
            rows = bx.leggi_foglio(nome)
            if not rows:
                continue
            frame = ttk.Frame(self._nb)
            sc = SheetCanvas(frame, rows)
            sc.pack(fill="both", expand=True)
            self._nb.add(frame, text=nome)
            self._sheet_canvases[nome] = sc

        self._nb.pack(fill="both", expand=True)

    def _collega(self):
        path = filedialog.askopenfilename(
            title="Seleziona il template Excel",
            filetypes=[("Excel", "*.xlsx *.xlsm"), ("Tutti", "*.*")])
        if not path:
            return
        try:
            bx.collega_template(path)
            self._carica_fogli()
            messagebox.showinfo("Collegato", "Template collegato correttamente.")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _aggiorna(self):
        if not bx.excel_collegato():
            messagebox.showwarning("Attenzione", "Prima collega il template Excel.")
            return
        anno = self._anno_var.get()
        try:
            saldi = self._get_saldi()
            bx.aggiorna_bilancio(saldi, anno)
            self._carica_fogli()
            messagebox.showinfo("Aggiornato",
                                f"Saldi {anno} scritti nel template Excel.")
        except Exception as e:
            messagebox.showerror("Errore aggiornamento", str(e))

    def _apri_excel(self):
        if not bx.excel_collegato():
            messagebox.showwarning("Attenzione", "Prima collega il template Excel.")
            return
        subprocess.Popen(["open", bx.EXCEL_PATH])
