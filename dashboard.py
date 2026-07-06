"""
Dashboard: riepilogo KPI, ultime registrazioni, crediti aperti.
Aggiornata automaticamente ad ogni cambio nel giornale.
"""
import tkinter as tk
from tkinter import ttk
import datetime


def _mese_corrente():
    oggi = datetime.date.today()
    return oggi.year, oggi.month


def _fmt(v):
    try:
        return f"€ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "€ 0,00"


class DashboardView(ttk.Frame):
    def __init__(self, parent, get_reg_fn):
        super().__init__(parent)
        self._get_reg = get_reg_fn
        self._build()

    def _build(self):
        # ── Titolo ────────────────────────────────────────────────────────────
        hdr = ttk.Frame(self, padding=(12, 10, 12, 4))
        hdr.pack(fill="x")
        oggi = datetime.date.today().strftime("%A %d %B %Y")
        ttk.Label(hdr, text="📊  Dashboard", font=("Helvetica", 16, "bold")).pack(side="left")
        ttk.Label(hdr, text=oggi, font=("Helvetica", 11),
                  foreground="#888888").pack(side="right")

        # ── Griglia KPI ───────────────────────────────────────────────────────
        self._kpi_frame = ttk.Frame(self, padding=(12, 4))
        self._kpi_frame.pack(fill="x")

        # ── Ultime registrazioni ──────────────────────────────────────────────
        mid = ttk.Frame(self, padding=(12, 4))
        mid.pack(fill="both", expand=True)

        left = ttk.LabelFrame(mid, text="Ultime registrazioni", padding=6)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        cols = ("data", "controparte", "tipo", "importo")
        self._tree_reg = ttk.Treeview(left, columns=cols, show="headings", height=8)
        for c, w, lbl in zip(cols, (80, 200, 80, 100),
                              ("Data", "Controparte", "Tipo", "Importo")):
            self._tree_reg.heading(c, text=lbl)
            self._tree_reg.column(c, width=w, anchor="w")
        self._tree_reg.tag_configure("attiva",   foreground="#007700")
        self._tree_reg.tag_configure("passiva",  foreground="#000000")
        self._tree_reg.tag_configure("movimento",foreground="#005599")
        vsb1 = ttk.Scrollbar(left, orient="vertical", command=self._tree_reg.yview)
        self._tree_reg.configure(yscrollcommand=vsb1.set)
        vsb1.pack(side="right", fill="y")
        self._tree_reg.pack(fill="both", expand=True)

        right = ttk.LabelFrame(mid, text="Crediti aperti (da incassare)", padding=6)
        right.pack(side="right", fill="both", expand=True)
        cols2 = ("data", "cliente", "numero", "importo")
        self._tree_cred = ttk.Treeview(right, columns=cols2, show="headings", height=8)
        for c, w, lbl in zip(cols2, (80, 180, 60, 100),
                              ("Data", "Cliente", "N°", "Da incassare")):
            self._tree_cred.heading(c, text=lbl)
            self._tree_cred.column(c, width=w, anchor="w")
        vsb2 = ttk.Scrollbar(right, orient="vertical", command=self._tree_cred.yview)
        self._tree_cred.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        self._tree_cred.pack(fill="both", expand=True)

        ttk.Button(self, text="🔄 Aggiorna dashboard",
                   command=self.aggiorna).pack(pady=(4, 8))

    def _kpi_card(self, parent, titolo, valore, colore, col):
        frm = tk.Frame(parent, bg=colore, padx=14, pady=10)
        frm.grid(row=0, column=col, padx=6, pady=6, sticky="nsew")
        parent.columnconfigure(col, weight=1)
        tk.Label(frm, text=titolo, bg=colore, fg="white",
                 font=("Helvetica", 10)).pack(anchor="w")
        tk.Label(frm, text=valore, bg=colore, fg="white",
                 font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(4, 0))

    def aggiorna(self):
        reg = self._get_reg()
        anno, mese = _mese_corrente()

        # Calcola KPI
        ricavi_mese = costi_mese = iva_cred = iva_deb = crediti = 0.0
        incassati = set()

        for r in reg:
            if r.get("stato") != "registrata":
                continue
            try:
                data = datetime.date.fromisoformat(r.get("data",""))
            except Exception:
                data = None

            for riga in r.get("righe", []):
                c = riga["conto"]
                d, a = riga["dare"], riga["avere"]
                # Ricavi del mese corrente
                if c == "80" and data and data.year == anno and data.month == mese:
                    ricavi_mese += a
                # Costi del mese corrente
                if c in ("60","61","62","63","64","65","66","67","68","69") \
                        and data and data.year == anno and data.month == mese:
                    costi_mese += d
                # IVA
                if c == "18": iva_cred += d - a
                if c in ("45","48"): iva_deb += a - d
                # Crediti vs clienti (conto 15)
                if c == "15": crediti += d - a

            # Segna fatture attive incassate (se c'è un incasso collegato)
            if r.get("tipo") == "movimento" and r.get("mov_tipo") == "incasso_cliente":
                # importo incassato = avere conto 15
                incassati.add(r.get("fornitore","") + r.get("data",""))

        iva_netta = max(iva_deb - iva_cred, 0)

        # Ridisegna KPI
        for w in self._kpi_frame.winfo_children():
            w.destroy()
        self._kpi_card(self._kpi_frame, f"Ricavi  ({datetime.date.today().strftime('%B %Y')})",
                       _fmt(ricavi_mese), "#2E7D32", 0)
        self._kpi_card(self._kpi_frame, f"Costi  ({datetime.date.today().strftime('%B %Y')})",
                       _fmt(costi_mese), "#B71C1C", 1)
        self._kpi_card(self._kpi_frame, "IVA da versare (netta)",
                       _fmt(iva_netta), "#1565C0", 2)
        self._kpi_card(self._kpi_frame, "Crediti aperti vs clienti",
                       _fmt(max(crediti, 0)), "#E65100", 3)

        # Ultime 10 registrazioni
        self._tree_reg.delete(*self._tree_reg.get_children())
        for r in reversed(reg[-30:]):
            if r.get("stato") != "registrata":
                continue
            tipo = r.get("tipo", "passiva")
            importo = sum(x["dare"] for x in r["righe"]
                          if x["conto"] in ("15","20","21","40")) or \
                      sum(x["avere"] for x in r["righe"] if x["conto"] == "80")
            self._tree_reg.insert("", "end",
                values=(r.get("data",""), r.get("fornitore",""),
                        tipo, _fmt(importo)),
                tags=(tipo,))

        # Crediti aperti (fatture attive non ancora incassate)
        self._tree_cred.delete(*self._tree_cred.get_children())
        for r in reg:
            if r.get("tipo") != "attiva" or r.get("stato") != "registrata":
                continue
            importo_dovuto = sum(x["dare"] for x in r["righe"] if x["conto"] == "15")
            if importo_dovuto > 0:
                self._tree_cred.insert("", "end",
                    values=(r.get("data",""), r.get("fornitore",""),
                            r.get("numero",""), _fmt(importo_dovuto)))
