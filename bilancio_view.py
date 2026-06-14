"""
Viewer Excel dentro l'app.
Layout: colonna Voce + colonna Anno selezionato (€).
I dati vengono letti una volta e tenuti in cache: cambio tab istantaneo.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import datetime

import bilancio_excel as bx

_ANNI = [2022, 2023, 2024, 2025, 2026, 2027]
_ANNI_SET = set(_ANNI)

_PALETTE_TAG = {
    "FFFFFF00": "yellow",  "FFFFE699": "yellow",
    "FFD9D9D9": "gray_dk", "FFC9C9C9": "gray_dk",
    "FFF2F2F2": "gray_lt", "FFEEEEEE": "gray_lt",
    "FFA9D08E": "green",   "FF92D050": "green",
    "FFBDD7EE": "blue",
}

def _cell_tag(hex8):
    if not hex8:
        return ""
    k = hex8.upper().lstrip("#")
    if len(k) == 6:
        k = "FF" + k
    return _PALETTE_TAG.get(k, "")


def _fmt_euro(val):
    """Formato contabile italiano: 1.234,56  oppure stringa vuota se 0/None."""
    if val is None:
        return ""
    if isinstance(val, (int, float)):
        v = float(val)
        if v == 0:
            return ""
        # 1234.56 → "1.234,56"
        formatted = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"-{formatted}" if v < 0 else formatted
    return str(val)


def _is_year_header(row):
    for cell in row[1:7]:
        if isinstance(cell.get("value"), int) and cell["value"] in _ANNI_SET:
            return True
    return False


class SheetView(tk.Frame):
    _LABEL_W = 500
    _VALUE_W = 130

    def __init__(self, parent, nome, anno, rows_data):
        super().__init__(parent)
        self._nome = nome
        self._build(anno, rows_data)

    def _build(self, anno, rows_data):
        # Indice colonna per anno selezionato (A=0, B=1=2022, …, F=5=2026)
        col_idx = _ANNI.index(anno) + 1 if anno in _ANNI else 5

        # Stile Treeview chiaro (override dark mode)
        style = ttk.Style()
        style.configure("Bil.Treeview",
                        background="white", foreground="black",
                        fieldbackground="white", rowheight=26)
        style.configure("Bil.Treeview.Heading",
                        background="#444444", foreground="white",
                        font=("Helvetica", 12, "bold"))
        style.map("Bil.Treeview",
                  background=[("selected", "#B8D4F0")],
                  foreground=[("selected", "black")])

        cols = ("voce", "valore")
        tree = ttk.Treeview(self, columns=cols, show="headings",
                            selectmode="none", style="Bil.Treeview")
        tree.heading("voce",   text="Voce di bilancio", anchor="w")
        tree.heading("valore", text=f"{anno}  (€)",    anchor="e")
        tree.column("voce",   width=self._LABEL_W, anchor="w", stretch=True)
        tree.column("valore", width=self._VALUE_W, anchor="e", stretch=False)

        fn = ("Helvetica", 11)
        fb = ("Helvetica", 11, "bold")
        fg = "black"
        tree.tag_configure("yellow",  background="#FFF0A0", foreground=fg, font=fb)
        tree.tag_configure("gray_dk", background="#D0D0D0", foreground=fg, font=fb)
        tree.tag_configure("gray_lt", background="#F0F0F0", foreground=fg, font=fn)
        tree.tag_configure("green",   background="#A9D08E", foreground=fg, font=fb)
        tree.tag_configure("blue",    background="#BDD7EE", foreground=fg, font=fn)
        tree.tag_configure("normal",  background="white",   foreground=fg, font=fn)

        for row in rows_data:
            if _is_year_header(row):
                continue
            col_a = row[0] if row else {}
            label_val = col_a.get("value")
            value = row[col_idx].get("value") if col_idx < len(row) else None
            if label_val is None and (value is None or value == 0):
                continue

            indent = col_a.get("indent", 0)
            label  = ("    " * indent) + (str(label_val) if label_val is not None else "")
            vals   = [label, _fmt_euro(value)]

            t = next((_cell_tag(c.get("bg","")) for c in row if _cell_tag(c.get("bg",""))), "normal")
            tree.insert("", "end", values=vals, tags=(t,))

        vsb = ttk.Scrollbar(self, orient="vertical",   command=tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.bind("<MouseWheel>",
                  lambda e: tree.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)


class BilancioView(ttk.Frame):
    def __init__(self, parent, get_saldi_fn):
        super().__init__(parent)
        self._get_saldi = get_saldi_fn
        self._build()
        self.after(300, self._init_excel)

    def _build(self):
        tb = ttk.Frame(self, padding=(6, 4))
        tb.pack(fill="x")
        ttk.Button(tb, text="🔄 Aggiorna da giornale",
                   command=self._aggiorna).pack(side="left")
        self._anno_var = tk.IntVar(value=datetime.date.today().year)
        ttk.Label(tb, text="  Anno:").pack(side="left")
        sp = ttk.Spinbox(tb, from_=2022, to=2027, width=6,
                         textvariable=self._anno_var,
                         command=self._on_anno_change)
        sp.pack(side="left")
        sp.bind("<Return>", lambda _: self._on_anno_change())
        ttk.Button(tb, text="📂 Apri in Excel",
                   command=self._apri_excel).pack(side="right")
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True)

    def _on_anno_change(self):
        """Ricostruisce le tab quando l'anno cambia (dati già in cache → veloce)."""
        if bx.excel_disponibile():
            self._carica_fogli()

    def _init_excel(self):
        bx.assicura_excel()
        if bx.excel_disponibile():
            self._carica_fogli()

    def _carica_fogli(self):
        anno = self._anno_var.get()
        for tab_id in self._nb.tabs():
            self._nb.forget(tab_id)

        for nome in bx.FOGLI_DA_MOSTRARE:
            rows = bx.leggi_foglio_cached(nome)   # usa la cache
            frame = ttk.Frame(self._nb)
            SheetView(frame, nome, anno, rows).pack(fill="both", expand=True)
            self._nb.add(frame, text=nome[:22])

    def aggiorna_silenzioso(self):
        if not bx.excel_disponibile():
            return
        try:
            bx.aggiorna_bilancio(self._get_saldi(), self._anno_var.get())
            self._carica_fogli()
        except Exception:
            pass

    def _aggiorna(self):
        if not bx.excel_disponibile():
            messagebox.showwarning("Attenzione", "Template Excel non trovato.")
            return
        try:
            bx.aggiorna_bilancio(self._get_saldi(), self._anno_var.get())
            self._carica_fogli()
            messagebox.showinfo("Aggiornato",
                f"Bilancio {self._anno_var.get()} aggiornato.")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _apri_excel(self):
        if not bx.excel_disponibile():
            return
        path = bx._working_path()
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["open", path])
