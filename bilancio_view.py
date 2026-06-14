"""
Viewer Excel dentro l'app — usa ttk.Treeview (affidabile nel bundle .app).
Si aggiorna automaticamente ogni volta che il giornale cambia.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import datetime

import bilancio_excel as bx

_PALETTE = {
    "FFFFFF00": "#FFF0A0",
    "FFD9D9D9": "#D9D9D9",
    "FFF2F2F2": "#EEEEEE",
    "FFA9D08E": "#A9D08E",
    "FF92D050": "#C8E6A0",
    "FFBDD7EE": "#BDD7EE",
}

def _tag(bg_hex8):
    if not bg_hex8:
        return ""
    k = bg_hex8.upper().lstrip("#")
    if len(k) == 8:
        k = "FF" + k[2:]
    mapped = _PALETTE.get(k, "")
    if not mapped:
        return ""
    lookup = {v: t for t, v in {
        "yellow":     "#FFF0A0",
        "gray_dark":  "#D9D9D9",
        "gray_light": "#EEEEEE",
        "green":      "#A9D08E",
        "green2":     "#C8E6A0",
        "blue_light": "#BDD7EE",
    }.items()}
    return lookup.get(mapped, "")


def _fmt(val):
    if val is None:
        return ""
    if isinstance(val, (int, float)):
        v = float(val)
        if v == 0:
            return ""
        if isinstance(val, int) and 1900 <= val <= 2100:
            return str(val)
        if v == int(v) and abs(v) < 10000:
            return str(int(v))
        return f"{v:,.0f}".replace(",", ".")
    return str(val)


class SheetView(tk.Frame):
    _COLS = ("voce", "2022", "2023", "2024", "2025", "2026", "2027")
    _WIDTHS = (370, 78, 78, 78, 78, 78, 78)

    def __init__(self, parent, nome_foglio):
        super().__init__(parent)
        self._nome = nome_foglio
        self._build()

    def _build(self):
        tree = ttk.Treeview(self, columns=self._COLS, show="headings",
                            selectmode="none")
        for col, w in zip(self._COLS, self._WIDTHS):
            lbl = "" if col == "voce" else col
            anch = "w" if col == "voce" else "e"
            tree.heading(col, text=lbl)
            tree.column(col,  width=w, anchor=anch, stretch=(col == "voce"))

        # tag colori
        tree.tag_configure("yellow",     background="#FFF0A0", font=("Helvetica", 9, "bold"))
        tree.tag_configure("gray_dark",  background="#D9D9D9", font=("Helvetica", 9, "bold"))
        tree.tag_configure("gray_light", background="#EEEEEE")
        tree.tag_configure("green",      background="#A9D08E", font=("Helvetica", 9, "bold"))
        tree.tag_configure("green2",     background="#C8E6A0")
        tree.tag_configure("blue_light", background="#BDD7EE")

        rows = bx.leggi_foglio(self._nome)
        for row in rows:
            vals = [_fmt(row[ci]["value"] if ci < len(row) else None)
                    for ci in range(7)]
            # tag: prendi dal primo bg della riga
            t = ""
            for cell in row:
                t = _tag(cell.get("bg", ""))
                if t:
                    break
            tree.insert("", "end", values=vals, tags=(t,) if t else ())

        vsb = ttk.Scrollbar(self, orient="vertical",   command=tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)

    def ricarica(self):
        for w in self.winfo_children():
            w.destroy()
        self._build()


class BilancioView(ttk.Frame):
    def __init__(self, parent, get_saldi_fn):
        super().__init__(parent)
        self._get_saldi = get_saldi_fn
        self._tabs: dict[str, SheetView] = {}
        self._build()
        self.after(300, self._init_excel)

    def _build(self):
        tb = ttk.Frame(self, padding=(6, 4))
        tb.pack(fill="x")
        ttk.Button(tb, text="🔄 Aggiorna da giornale",
                   command=self._aggiorna).pack(side="left")
        self._anno_var = tk.IntVar(value=datetime.date.today().year)
        ttk.Label(tb, text="  Anno:").pack(side="left")
        ttk.Spinbox(tb, from_=2022, to=2027, width=5,
                    textvariable=self._anno_var).pack(side="left")
        ttk.Button(tb, text="📂 Apri in Excel",
                   command=self._apri_excel).pack(side="right")
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True)

    def _init_excel(self):
        bx.assicura_excel()
        if bx.excel_disponibile():
            self._carica_fogli()

    def _carica_fogli(self):
        for tab_id in self._nb.tabs():
            self._nb.forget(tab_id)
        self._tabs.clear()
        for nome in bx.FOGLI_DA_MOSTRARE:
            frame = ttk.Frame(self._nb)
            sv = SheetView(frame, nome)
            sv.pack(fill="both", expand=True)
            self._nb.add(frame, text=nome[:22])
            self._tabs[nome] = sv

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
            messagebox.showwarning("Attenzione", "Template Excel non trovato. Riavvia l'app.")
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
