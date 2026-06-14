"""
Viewer Excel dentro l'app — ttk.Treeview con indentazione, senza righe vuote,
colonne compatte e layout che riempie tutta la finestra.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import datetime

import bilancio_excel as bx

# Anni presenti come intestazioni nel foglio Excel (da saltare come righe dati)
_ANNI_SET = {2022, 2023, 2024, 2025, 2026, 2027}

_PALETTE_TAG = {
    "FFFFFF00": "yellow",
    "FFD9D9D9": "gray_dark",
    "FFF2F2F2": "gray_light",
    "FFA9D08E": "green",
    "FF92D050": "green2",
    "FFBDD7EE": "blue_light",
    "FFFFE699": "yellow",   # variante giallo
    "FFFFFFCC": "yellow",
}


def _cell_tag(hex8):
    if not hex8:
        return ""
    k = hex8.upper().lstrip("#")
    if len(k) == 6:
        k = "FF" + k
    return _PALETTE_TAG.get(k, "")


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


def _is_year_header_row(row):
    """True se la riga contiene gli anni come intestazioni (riga 2 del foglio)."""
    for cell in row[1:7]:
        v = cell.get("value")
        if isinstance(v, int) and v in _ANNI_SET:
            return True
    return False


class SheetView(tk.Frame):
    _LABEL_W = 430
    _YEAR_W  = 78

    def __init__(self, parent, nome_foglio):
        super().__init__(parent)
        self._nome = nome_foglio
        self._build()

    def _build(self):
        rows_raw = bx.leggi_foglio(self._nome)
        if not rows_raw:
            ttk.Label(self, text="Foglio non disponibile", padding=20).pack()
            return

        cols = ("voce", "2022", "2023", "2024", "2025", "2026", "2027")
        tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="none")

        # Intestazioni colonne
        tree.heading("voce", text="Voce di bilancio", anchor="w")
        tree.column("voce", width=self._LABEL_W, minwidth=200,
                    anchor="w", stretch=True)
        for yr in ("2022", "2023", "2024", "2025", "2026", "2027"):
            tree.heading(yr, text=yr, anchor="e")
            tree.column(yr, width=self._YEAR_W, minwidth=60,
                        anchor="e", stretch=False)

        # Tag colori + font bold per sezioni
        f_normal = ("Helvetica", 9)
        f_bold   = ("Helvetica", 9, "bold")
        tree.tag_configure("yellow",     background="#FFF0A0", font=f_bold)
        tree.tag_configure("gray_dark",  background="#D9D9D9", font=f_bold)
        tree.tag_configure("gray_light", background="#EEEEEE", font=f_normal)
        tree.tag_configure("green",      background="#A9D08E", font=f_bold)
        tree.tag_configure("green2",     background="#C8E6A0", font=f_normal)
        tree.tag_configure("blue_light", background="#BDD7EE", font=f_normal)
        tree.tag_configure("",          font=f_normal)

        for row in rows_raw:
            # Salta righe intestazione anni (row 2 di ogni foglio)
            if _is_year_header_row(row):
                continue

            col_a = row[0] if row else {}
            label_val = col_a.get("value")

            # Salta righe completamente vuote (nessun testo, nessun valore)
            has_values = any(
                row[i].get("value") not in (None, "", 0)
                for i in range(1, min(7, len(row)))
            )
            if label_val is None and not has_values:
                continue

            # Applica indentazione Excel
            indent = col_a.get("indent", 0)
            prefix = "    " * indent if indent else ""
            label = prefix + (str(label_val) if label_val is not None else "")

            # Valori anni
            yr_vals = [
                _fmt(row[i].get("value") if i < len(row) else None)
                for i in range(1, 7)
            ]

            vals = [label] + yr_vals

            # Tag colore dalla prima cella con bg
            t = ""
            for cell in row:
                t = _cell_tag(cell.get("bg", ""))
                if t:
                    break

            tree.insert("", "end", values=vals, tags=(t,) if t else ("",))

        vsb = ttk.Scrollbar(self, orient="vertical",   command=tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.bind("<MouseWheel>", lambda e: tree.yview_scroll(
            -1 if e.delta > 0 else 1, "units"))
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
