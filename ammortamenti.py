"""
Gestione cespiti e calcolo ammortamenti annui.
I cespiti vengono salvati in dati/cespiti.json.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import datetime
import config


def _cespiti_file():
    return os.path.join(config.get_data_dir(), "cespiti.json")


def carica_cespiti():
    p = _cespiti_file()
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return []


def salva_cespiti(lista):
    p = _cespiti_file()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def _valore_residuo(cespite, anno_corrente):
    """Calcola il valore residuo al 31/12 dell'anno corrente."""
    val    = float(cespite.get("valore", 0))
    perc   = float(cespite.get("perc_amm", 20)) / 100
    anno_acq = int(cespite.get("anno_acquisto", datetime.date.today().year))
    anni_passati = max(0, anno_corrente - anno_acq)
    for i in range(anni_passati):
        quota = round(val * perc, 2)
        if i == 0:
            quota = round(quota / 2, 2)  # primo anno 50% per norma fiscale italiana
        val = max(0, round(val - quota, 2))
    return val


class AmmortamentiView(ttk.Frame):
    def __init__(self, parent, on_registra_fn=None):
        super().__init__(parent)
        self._on_registra = on_registra_fn
        self._build()

    def _build(self):
        # ── Form nuovo cespite ─────────────────────────────────────────────────
        frm = ttk.LabelFrame(self, text="Aggiungi cespite", padding=10)
        frm.pack(fill="x", padx=8, pady=8)

        campos = [("descrizione","Descrizione",30),("valore","Valore acquisto (€)",12),
                  ("anno_acquisto","Anno acquisto",6),("perc_amm","% ammortamento",6),
                  ("categoria","Categoria",20)]
        self._vars = {}
        for i, (k, lbl, w) in enumerate(campos):
            col = (i % 3) * 2
            row = i // 3
            ttk.Label(frm, text=lbl+":").grid(row=row, column=col, sticky="e",
                                               padx=(0,4), pady=3)
            default = {"anno_acquisto": str(datetime.date.today().year),
                       "perc_amm": "20"}.get(k, "")
            var = tk.StringVar(value=default)
            ttk.Entry(frm, textvariable=var, width=w).grid(row=row, column=col+1,
                                                             sticky="w", padx=(0,12))
            self._vars[k] = var

        ttk.Button(frm, text="+ Aggiungi", command=self._aggiungi).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6,0))

        # ── Tabella cespiti ────────────────────────────────────────────────────
        tab = ttk.LabelFrame(self, text="Registro cespiti", padding=6)
        tab.pack(fill="both", expand=True, padx=8, pady=(0,4))

        cols = ("descrizione","categoria","valore","anno","perc","residuo")
        self._tree = ttk.Treeview(tab, columns=cols, show="headings", height=8)
        for c, w, lbl in zip(cols, (200,120,110,70,60,110),
            ("Descrizione","Categoria","Valore acq.","Anno","% Amm.","Valore residuo")):
            self._tree.heading(c, text=lbl)
            self._tree.column(c, width=w, anchor="w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)

        # ── Azioni ────────────────────────────────────────────────────────────
        bar = ttk.Frame(self, padding=(8,4))
        bar.pack(fill="x")
        self._anno_var = tk.IntVar(value=datetime.date.today().year)
        ttk.Label(bar, text="Anno di calcolo:").pack(side="left")
        ttk.Spinbox(bar, from_=2020, to=2030, width=6,
                    textvariable=self._anno_var).pack(side="left", padx=6)
        ttk.Button(bar, text="📋 Calcola ammortamenti anno",
                   command=self._calcola).pack(side="left", padx=6)
        ttk.Button(bar, text="✓ Registra nel giornale",
                   command=self._registra).pack(side="left")
        ttk.Button(bar, text="🗑 Elimina selezionato",
                   command=self._elimina).pack(side="right")

        self._amm_calcolati = []
        self._lbl_tot = ttk.Label(self, text="", font=("Helvetica", 10, "bold"))
        self._lbl_tot.pack(pady=(0, 6))
        self._aggiorna_tree()

    def _aggiorna_tree(self):
        self._tree.delete(*self._tree.get_children())
        anno = self._anno_var.get() if hasattr(self, '_anno_var') else datetime.date.today().year
        for c in carica_cespiti():
            res = _valore_residuo(c, anno)
            self._tree.insert("", "end", values=(
                c.get("descrizione",""), c.get("categoria",""),
                f"€ {float(c.get('valore',0)):,.2f}",
                c.get("anno_acquisto",""),
                f"{c.get('perc_amm',20)} %",
                f"€ {res:,.2f}"))

    def _aggiungi(self):
        dati = {k: v.get().strip() for k, v in self._vars.items()}
        if not dati.get("descrizione"):
            messagebox.showwarning("Attenzione", "Inserisci almeno la descrizione.", parent=self)
            return
        try:
            float(dati["valore"])
        except ValueError:
            messagebox.showwarning("Attenzione", "Valore non valido.", parent=self)
            return
        cespiti = carica_cespiti()
        cespiti.append(dati)
        salva_cespiti(cespiti)
        for v in self._vars.values():
            v.set("")
        self._vars["anno_acquisto"].set(str(datetime.date.today().year))
        self._vars["perc_amm"].set("20")
        self._aggiorna_tree()

    def _calcola(self):
        anno = self._anno_var.get()
        cespiti = carica_cespiti()
        if not cespiti:
            messagebox.showinfo("Info", "Nessun cespite registrato.")
            return
        self._amm_calcolati = []
        tot = 0.0
        for c in cespiti:
            val  = float(c.get("valore", 0))
            perc = float(c.get("perc_amm", 20)) / 100
            anno_acq = int(c.get("anno_acquisto", anno))
            if anno < anno_acq:
                continue
            anni = anno - anno_acq
            quota = round(val * perc, 2)
            if anni == 0:
                quota = round(quota / 2, 2)  # primo anno dimezzato
            res = _valore_residuo(c, anno - 1)
            quota = min(quota, res)
            if quota > 0:
                self._amm_calcolati.append({
                    "descrizione": c.get("descrizione",""),
                    "quota": quota,
                })
                tot += quota
        if not self._amm_calcolati:
            messagebox.showinfo("Risultato", "Nessun ammortamento da calcolare per quest'anno.")
            return
        testo = "\n".join(f"  • {a['descrizione']}: € {a['quota']:,.2f}"
                          for a in self._amm_calcolati)
        self._lbl_tot.config(
            text=f"Ammortamenti {anno}: totale € {tot:,.2f}  "
                 f"— clicca 'Registra nel giornale' per contabilizzarli")
        messagebox.showinfo(f"Ammortamenti {anno}",
            f"Quote calcolate:\n{testo}\n\nTotale: € {tot:,.2f}\n\n"
            "Clicca 'Registra nel giornale' per contabilizzarli.")
        self._aggiorna_tree()

    def _registra(self):
        if not self._amm_calcolati:
            messagebox.showinfo("Info", "Prima clicca 'Calcola ammortamenti anno'.")
            return
        anno = self._anno_var.get()
        tot  = sum(a["quota"] for a in self._amm_calcolati)
        descr = f"Ammortamento cespiti {anno}"
        reg = {
            "chiave": f"AMM|{anno}",
            "data":   f"{anno}-12-31",
            "fornitore": "Ammortamento",
            "numero": f"AMM{anno}",
            "intra_ue": False,
            "stato": "registrata",
            "tipo": "movimento",
            "mov_tipo": "ammortamento",
            "note": descr,
            "righe": [
                {"conto":"70","descr":f"Ammortamento imm. materiali {anno}",
                 "dare": tot, "avere": 0.0},
                {"conto":"10","descr":f"Fondo ammortamento {anno}",
                 "dare": 0.0, "avere": tot},
            ],
        }
        if self._on_registra:
            self._on_registra(reg)
        self._amm_calcolati = []
        self._lbl_tot.config(text=f"✓ Ammortamenti {anno} registrati nel giornale.")

    def _elimina(self):
        sel = self._tree.selection()
        if not sel:
            return
        idx = self._tree.index(sel[0])
        cespiti = carica_cespiti()
        nome = cespiti[idx].get("descrizione","?")
        if messagebox.askyesno("Conferma", f"Eliminare '{nome}'?", parent=self):
            cespiti.pop(idx)
            salva_cespiti(cespiti)
            self._aggiorna_tree()
