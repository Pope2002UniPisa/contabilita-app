"""
Scadenzario: fatture attive aperte con semaforo scadenza.
Verde = pagata, Giallo = in scadenza (< 7 gg), Rosso = scaduta, Bianco = aperta.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import datetime


_GIORNI_SCADENZA = 30  # default giorni di pagamento


def _fmt(v):
    try:
        return f"€ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except Exception:
        return "€ 0,00"


def _scadenza(data_fattura: str, giorni=_GIORNI_SCADENZA) -> datetime.date:
    try:
        return datetime.date.fromisoformat(data_fattura) + datetime.timedelta(days=giorni)
    except Exception:
        return datetime.date.today()


class ScadenzarioView(ttk.Frame):
    def __init__(self, parent, get_reg_fn, on_registra_incasso=None):
        super().__init__(parent)
        self._get_reg = get_reg_fn
        self._on_incasso = on_registra_incasso
        self._build()

    def _build(self):
        # Legenda + filtro
        top = ttk.Frame(self, padding=(8, 6))
        top.pack(fill="x")
        ttk.Label(top, text="Scadenzario fatture attive",
                  font=("Helvetica", 13, "bold")).pack(side="left")

        leg = ttk.Frame(top)
        leg.pack(side="right")
        for txt, col in [("✓ Pagata","#2E7D32"),("⚠ In scadenza","#E65100"),
                          ("✗ Scaduta","#B71C1C"),("• Aperta","#333333")]:
            tk.Label(leg, text=txt, fg=col, font=("Helvetica",9)).pack(side="left", padx=6)

        # Giorni scadenza
        sf = ttk.Frame(self, padding=(8, 0))
        sf.pack(fill="x")
        ttk.Label(sf, text="Giorni di pagamento predefiniti:").pack(side="left")
        self._gg_var = tk.IntVar(value=_GIORNI_SCADENZA)
        ttk.Spinbox(sf, from_=1, to=180, width=5,
                    textvariable=self._gg_var,
                    command=self.aggiorna).pack(side="left", padx=6)
        ttk.Button(sf, text="🔄 Aggiorna", command=self.aggiorna).pack(side="left", padx=6)
        ttk.Button(sf, text="✓ Segna incassata",
                   command=self._segna_incassata).pack(side="right", padx=8)

        # Tabella
        cols = ("stato", "data", "scadenza", "cliente", "numero", "importo", "giorni_rimasti")
        self._tree = ttk.Treeview(self, columns=cols, show="headings")
        for c, w, lbl in zip(cols,
            (90, 80, 80, 220, 60, 110, 110),
            ("Stato","Data fattura","Scadenza","Cliente","N°","Importo (€)","Giorni rimasti")):
            self._tree.heading(c, text=lbl)
            self._tree.column(c, width=w, anchor="w")

        self._tree.tag_configure("pagata",     foreground="#2E7D32", background="#F1F8E9")
        self._tree.tag_configure("scaduta",    foreground="#B71C1C", background="#FFEBEE")
        self._tree.tag_configure("in_scadenza",foreground="#E65100", background="#FFF3E0")
        self._tree.tag_configure("aperta",     foreground="#333333")

        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(4,8))

        self.aggiorna()

    def aggiorna(self):
        self._tree.delete(*self._tree.get_children())
        reg    = self._get_reg()
        oggi   = datetime.date.today()
        gg     = self._gg_var.get()

        # Fatture incassate: set di chiavi (fornitore+numero+data)
        incassate = set()
        for r in reg:
            if r.get("tipo") == "movimento" and r.get("mov_tipo") == "incasso_cliente":
                # chiave semplice: nome cliente + data movimento (approssimazione)
                incassate.add(r.get("fornitore","").lower())

        for r in reg:
            if r.get("tipo") != "attiva" or r.get("stato") != "registrata":
                continue
            importo = sum(x["dare"] for x in r["righe"] if x["conto"] == "15")
            data_str = r.get("data","")
            scad = _scadenza(data_str, gg)
            delta = (scad - oggi).days
            cliente = r.get("fornitore","")

            # Stato
            pagata = cliente.lower() in incassate or importo <= 0
            if pagata:
                stato, tag, rimasti = "✓ Pagata",     "pagata",      "—"
            elif delta < 0:
                stato, tag, rimasti = "✗ Scaduta",    "scaduta",     f"{abs(delta)} gg fa"
            elif delta <= 7:
                stato, tag, rimasti = "⚠ In scadenza","in_scadenza", f"{delta} giorni"
            else:
                stato, tag, rimasti = "• Aperta",     "aperta",      f"{delta} giorni"

            self._tree.insert("", "end", tags=(tag,), values=(
                stato, data_str, scad.isoformat(),
                cliente, r.get("numero",""),
                _fmt(importo), rimasti))

    def _segna_incassata(self):
        """Apre dialog per registrare l'incasso della fattura selezionata."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Info",
                "Seleziona una fattura dalla lista per registrarne l'incasso.")
            return
        item = self._tree.item(sel[0])
        vals = item["values"]
        cliente  = vals[3]
        numero   = vals[4]
        importo_str = vals[5]
        # Rimuovi simbolo € e converti
        try:
            importo = float(importo_str.replace("€","").replace(".","").replace(",",".").strip())
        except Exception:
            importo = 0.0

        if messagebox.askyesno("Registra incasso",
            f"Registrare l'incasso di {importo_str} da {cliente} (fattura n° {numero})?"):
            if self._on_incasso:
                self._on_incasso(cliente, importo,
                                 datetime.date.today().isoformat())
            self.aggiorna()
