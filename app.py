"""
Contabilità Automatica — app principale.
Fasi 1+2+3: fatture passive, bilancio Excel, emissione fatture attive.
"""
import os
import glob
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from parser_fattura   import parse_fattura
from motore_codifica  import proponi_conto, salva_regola_piva
from scritture        import (scrittura_fattura_passiva, verifica_quadratura,
                               scrittura_incasso_fattura_attiva)
from piano_conti      import PIANO_CONTI, CONTI_COSTO, descrizione
import giornale
import bilancio_excel as bx
from bilancio_view    import BilancioView
import fattura_attiva as fa
from anagrafica       import carica_azienda, salva_azienda, carica_clienti, salva_clienti


# ══════════════════════════════════════════════════════════════
#  DIALOG IMPOSTAZIONI AZIENDA
# ══════════════════════════════════════════════════════════════
class ImpostazioniDialog(tk.Toplevel):
    _CAMPI = [
        ("denominazione", "Ragione sociale"),
        ("piva",          "Partita IVA"),
        ("codice_fiscale","Codice fiscale"),
        ("via",           "Indirizzo (via)"),
        ("cap",           "CAP"),
        ("comune",        "Comune"),
        ("provincia",     "Provincia (2 lett.)"),
        ("nazione",       "Nazione (IT)"),
        ("regime_fiscale","Regime fiscale (RF01)"),
        ("codice_sdi",    "Codice SDI (7 car.)"),
    ]

    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.title("Impostazioni Azienda")
        self.resizable(False, False)
        self._on_save = on_save
        self._vars = {}
        azienda = carica_azienda()

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)
        for row, (key, label) in enumerate(self._CAMPI):
            ttk.Label(frm, text=label + ":").grid(row=row, column=0, sticky="e", pady=2, padx=(0, 8))
            var = tk.StringVar(value=azienda.get(key, ""))
            ttk.Entry(frm, textvariable=var, width=36).grid(row=row, column=1, sticky="w")
            self._vars[key] = var

        btn = ttk.Frame(self, padding=(16, 0, 16, 12))
        btn.pack(fill="x")
        ttk.Button(btn, text="Salva", command=self._salva).pack(side="right")
        ttk.Button(btn, text="Annulla", command=self.destroy).pack(side="right", padx=6)

    def _salva(self):
        dati = {k: v.get().strip() for k, v in self._vars.items()}
        salva_azienda(dati)
        if self._on_save:
            self._on_save()
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  DIALOG NUOVO CLIENTE
# ══════════════════════════════════════════════════════════════
class NuovoClienteDialog(tk.Toplevel):
    _CAMPI = [
        ("denominazione",  "Ragione sociale *"),
        ("piva",           "Partita IVA"),
        ("codice_fiscale", "Codice fiscale"),
        ("paese",          "Paese (IT)"),
        ("via",            "Indirizzo"),
        ("cap",            "CAP"),
        ("comune",         "Comune"),
        ("provincia",      "Provincia"),
        ("nazione",        "Nazione (IT)"),
        ("codice_sdi",     "Codice SDI"),
        ("pec",            "PEC"),
    ]

    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.title("Nuovo cliente")
        self.resizable(False, False)
        self._on_save = on_save
        self._vars = {}

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)
        defaults = {"paese": "IT", "nazione": "IT", "codice_sdi": "0000000"}
        for row, (key, label) in enumerate(self._CAMPI):
            ttk.Label(frm, text=label + ":").grid(row=row, column=0, sticky="e", pady=2, padx=(0, 8))
            var = tk.StringVar(value=defaults.get(key, ""))
            ttk.Entry(frm, textvariable=var, width=36).grid(row=row, column=1, sticky="w")
            self._vars[key] = var

        btn = ttk.Frame(self, padding=(16, 0, 16, 12))
        btn.pack(fill="x")
        ttk.Button(btn, text="Aggiungi", command=self._salva).pack(side="right")
        ttk.Button(btn, text="Annulla",  command=self.destroy).pack(side="right", padx=6)

    def _salva(self):
        if not self._vars["denominazione"].get().strip():
            messagebox.showwarning("Attenzione", "La ragione sociale è obbligatoria.",
                                   parent=self)
            return
        clienti = carica_clienti()
        nuovo = {k: v.get().strip() for k, v in self._vars.items()}
        clienti.append(nuovo)
        salva_clienti(clienti)
        if self._on_save:
            self._on_save(nuovo)
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  TAB EMETTI FATTURA
# ══════════════════════════════════════════════════════════════
class EmettiFatturaTab(ttk.Frame):
    def __init__(self, parent, on_registra=None):
        super().__init__(parent)
        self._on_registra = on_registra
        self._righe_vars: list[dict] = []
        self._build()

    def _build(self):
        # ── Intestazione ──────────────────────────────────────────────────
        top = ttk.LabelFrame(self, text="Intestazione fattura", padding=8)
        top.pack(fill="x", padx=8, pady=(8, 4))

        # Riga 1: cliente
        ttk.Label(top, text="Cliente:").grid(row=0, column=0, sticky="e", padx=(0, 4))
        self._cliente_var = tk.StringVar()
        self._combo_clienti = ttk.Combobox(top, textvariable=self._cliente_var,
                                            width=42, state="readonly")
        self._combo_clienti.grid(row=0, column=1, sticky="w")
        ttk.Button(top, text="+ Nuovo", width=8,
                   command=self._nuovo_cliente).grid(row=0, column=2, padx=6)
        self._aggiorna_clienti()

        # Riga 2: data, numero, tipo
        ttk.Label(top, text="Data:").grid(row=1, column=0, sticky="e", pady=(6, 0))
        self._data_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(top, textvariable=self._data_var, width=12).grid(row=1, column=1, sticky="w", pady=(6, 0))

        meta = ttk.Frame(top)
        meta.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Label(meta, text="Tipo doc:").pack(side="left")
        self._tipo_var = tk.StringVar(value="TD01")
        ttk.Combobox(meta, textvariable=self._tipo_var, width=8, state="readonly",
                     values=["TD01","TD06","TD04","TD05"]).pack(side="left", padx=(4, 16))
        ttk.Label(meta, text="Pagamento:").pack(side="left")
        self._pag_var = tk.StringVar(value="MP05")
        ttk.Combobox(meta, textvariable=self._pag_var, width=8, state="readonly",
                     values=["MP05","MP01","MP02","MP08"]).pack(side="left", padx=4)

        # ── Righe fattura ─────────────────────────────────────────────────
        rig_frm = ttk.LabelFrame(self, text="Righe", padding=8)
        rig_frm.pack(fill="both", expand=True, padx=8, pady=4)

        # Header colonne
        for c, (txt, w) in enumerate([("Descrizione", 38), ("Qtà", 6),
                                       ("Prezzo unit.", 10), ("IVA %", 6), ("Totale", 10)]):
            ttk.Label(rig_frm, text=txt, font=("Helvetica", 9, "bold")).grid(
                row=0, column=c, padx=4, pady=(0, 4))

        self._righe_frame = rig_frm
        self._add_riga()

        ttk.Button(self, text="+ Aggiungi riga",
                   command=self._add_riga).pack(anchor="w", padx=10, pady=(0, 4))

        # ── Totali ────────────────────────────────────────────────────────
        tot_frm = ttk.Frame(self, padding=(8, 4))
        tot_frm.pack(fill="x")
        self._lbl_totali = ttk.Label(tot_frm, text="", font=("Helvetica", 10, "bold"))
        self._lbl_totali.pack(side="left")

        # ── Bottoni ───────────────────────────────────────────────────────
        btn_frm = ttk.Frame(self, padding=(8, 4))
        btn_frm.pack(fill="x")
        ttk.Button(btn_frm, text="💾 Salva XML",
                   command=self._salva_xml).pack(side="left")
        ttk.Button(btn_frm, text="✓ Registra nel giornale",
                   command=self._registra).pack(side="left", padx=8)
        ttk.Button(btn_frm, text="🔄 Ricalcola totali",
                   command=self._ricalcola).pack(side="left")

    def _aggiorna_clienti(self, nuovo=None):
        clienti = carica_clienti()
        self._clienti_lista = clienti
        nomi = [c.get("denominazione", "") for c in clienti]
        self._combo_clienti["values"] = nomi
        if nuovo:
            self._cliente_var.set(nuovo.get("denominazione", ""))

    def _nuovo_cliente(self):
        NuovoClienteDialog(self, on_save=self._aggiorna_clienti)

    def _add_riga(self):
        row_idx = len(self._righe_vars) + 1
        vs = {
            "descrizione":    tk.StringVar(),
            "quantita":       tk.StringVar(value="1"),
            "prezzo_unitario":tk.StringVar(value="0.00"),
            "aliquota_iva":   tk.StringVar(value="22"),
        }
        self._righe_vars.append(vs)
        f = self._righe_frame
        r = row_idx
        ttk.Entry(f, textvariable=vs["descrizione"],    width=40).grid(row=r, column=0, padx=4, pady=1)
        ttk.Entry(f, textvariable=vs["quantita"],       width=6).grid(row=r, column=1, padx=4)
        ttk.Entry(f, textvariable=vs["prezzo_unitario"],width=10).grid(row=r, column=2, padx=4)
        ttk.Combobox(f, textvariable=vs["aliquota_iva"],width=6, state="readonly",
                     values=["22", "10", "5", "4", "0"]).grid(row=r, column=3, padx=4)
        lbl_tot = ttk.Label(f, text="0.00", width=10, anchor="e")
        lbl_tot.grid(row=r, column=4, padx=4)
        vs["_lbl_tot"] = lbl_tot

    def _ricalcola(self):
        imp = iva = 0.0
        for vs in self._righe_vars:
            try:
                qt = float(vs["quantita"].get() or 0)
                pr = float(vs["prezzo_unitario"].get() or 0)
                al = float(vs["aliquota_iva"].get() or 0)
                tot_r = round(qt * pr, 2)
                vs["_lbl_tot"].config(text=f"{tot_r:,.2f}")
                imp += tot_r
                iva += round(tot_r * al / 100, 2)
            except (ValueError, KeyError):
                pass
        tot = round(imp + iva, 2)
        self._lbl_totali.config(
            text=f"Imponibile: € {imp:,.2f}   |   IVA: € {iva:,.2f}   |   TOTALE: € {tot:,.2f}")
        return imp, iva, tot

    def _build_fattura_dict(self):
        nome_cliente = self._cliente_var.get().strip()
        if not nome_cliente:
            raise ValueError("Seleziona un cliente.")
        cliente = next((c for c in self._clienti_lista
                        if c.get("denominazione") == nome_cliente), None)
        if not cliente:
            raise ValueError("Cliente non trovato in anagrafica.")
        righe = []
        for vs in self._righe_vars:
            descr = vs["descrizione"].get().strip()
            if not descr:
                continue
            righe.append({
                "descrizione":    descr,
                "quantita":       float(vs["quantita"].get() or 1),
                "prezzo_unitario":float(vs["prezzo_unitario"].get() or 0),
                "aliquota_iva":   float(vs["aliquota_iva"].get() or 22),
            })
        if not righe:
            raise ValueError("Inserisci almeno una riga con descrizione.")
        anno = int(self._data_var.get()[:4]) if self._data_var.get() else datetime.date.today().year
        numero = fa.prossimo_numero(anno)
        return {
            "numero":            numero,
            "data":              self._data_var.get().strip() or datetime.date.today().isoformat(),
            "tipo_doc":          self._tipo_var.get(),
            "modalita_pagamento":self._pag_var.get(),
            "cliente":           cliente,
            "righe":             righe,
        }

    def _salva_xml(self):
        try:
            self._ricalcola()
            fatt = self._build_fattura_dict()
            azienda = carica_azienda()
            if not azienda.get("piva"):
                messagebox.showwarning("Attenzione",
                    "Configura prima i dati azienda (bottone ⚙ Impostazioni).")
                return
            dest = filedialog.askdirectory(title="Cartella dove salvare l'XML")
            if not dest:
                return
            path = fa.salva_fattura_xml(fatt, azienda, dest)
            messagebox.showinfo("Salvato", f"Fattura XML salvata in:\n{path}")
        except ValueError as e:
            messagebox.showerror("Errore", str(e))

    def _registra(self):
        try:
            self._ricalcola()
            fatt = self._build_fattura_dict()
            azienda = carica_azienda()
            reg = fa.fattura_a_registrazione(fatt, azienda)
            if self._on_registra:
                self._on_registra(reg)
        except ValueError as e:
            messagebox.showerror("Errore", str(e))


# ══════════════════════════════════════════════════════════════
#  APP PRINCIPALE
# ══════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Contabilità Automatica")
        self.geometry("1200x720")
        self.registrazioni = giornale.carica()
        self.in_attesa = []
        self._build_ui()
        self._refresh_giornale()

    def _build_ui(self):
        # ── Toolbar globale ───────────────────────────────────────────────
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="📂 Importa cartella fatture (XML)",
                   command=self.importa_cartella).pack(side="left")
        ttk.Button(top, text="📄 Importa singolo file",
                   command=self.importa_file).pack(side="left", padx=6)
        self.lbl_stato = ttk.Label(top, text="Pronto.")
        self.lbl_stato.pack(side="left", padx=12)
        ttk.Button(top, text="⚙ Impostazioni",
                   command=self._apri_impostazioni).pack(side="right")

        # ── Notebook principale ───────────────────────────────────────────
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 1 — Da approvare
        self.tab_appr = ttk.Frame(nb)
        nb.add(self.tab_appr, text="⏳ Da approvare")
        self._build_approvazione()

        # Tab 2 — Libro giornale
        self.tab_giorn = ttk.Frame(nb)
        nb.add(self.tab_giorn, text="📒 Libro giornale")
        self._build_giornale()

        # Tab 3 — Prospetto IVA
        self.tab_iva = ttk.Frame(nb)
        nb.add(self.tab_iva, text="🧾 Prospetto IVA")
        self._build_iva()

        # Tab 4 — Bilancio Excel
        self.bilancio_view = BilancioView(
            nb, get_saldi_fn=lambda: giornale.saldi_per_conto(self.registrazioni))
        nb.add(self.bilancio_view, text="📊 Bilancio")

        # Tab 5 — Emetti fattura
        self.emetti_tab = EmettiFatturaTab(nb, on_registra=self._registra_attiva)
        nb.add(self.emetti_tab, text="📤 Emetti fattura")

    # ── Approvazione ────────────────────────────────────────────────────────
    def _build_approvazione(self):
        cols = ("fornitore","data","numero","imponibile","iva","tipo","conto","motivo")
        self.tree_appr = ttk.Treeview(self.tab_appr, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (220,80,90,90,80,80,200,160)):
            self.tree_appr.heading(c, text=c.capitalize())
            self.tree_appr.column(c, width=w, anchor="w")
        self.tree_appr.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree_appr.bind("<<TreeviewSelect>>", self._sel_appr)

        bar = ttk.Frame(self.tab_appr, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Conto:").pack(side="left")
        conti_sel = {k: v for k, v in PIANO_CONTI.items() if v["tipo"] == "COSTO"}
        conti_sel["10"] = PIANO_CONTI["10"]
        self.combo_conto = ttk.Combobox(bar, width=45, state="readonly",
            values=[f"{k} - {PIANO_CONTI[k]['desc']}" for k in sorted(conti_sel)])
        self.combo_conto.pack(side="left", padx=6)
        self.var_impara = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Memorizza regola per questo fornitore",
                        variable=self.var_impara).pack(side="left", padx=10)
        ttk.Button(bar, text="✓ Approva e registra",
                   command=self.approva).pack(side="left", padx=6)
        ttk.Button(bar, text="✓✓ Approva tutte con proposta",
                   command=self.approva_tutte).pack(side="left")

    def _build_giornale(self):
        cols = ("data","fornitore","numero","tipo","conto","descr","dare","avere")
        self.tree_g = ttk.Treeview(self.tab_giorn, columns=cols, show="headings")
        for c, w in zip(cols, (80,180,90,60,60,260,100,100)):
            self.tree_g.heading(c, text=c.capitalize())
            self.tree_g.column(c, width=w, anchor="w")
        self.tree_g.tag_configure("attiva", foreground="#0066aa")
        self.tree_g.pack(fill="both", expand=True, padx=6, pady=6)
        bar = ttk.Frame(self.tab_giorn, padding=6)
        bar.pack(fill="x")
        self.lbl_tot = ttk.Label(bar, text="")
        self.lbl_tot.pack(side="left")
        ttk.Button(bar, text="Esporta giornale (CSV)",
                   command=self.esporta_csv).pack(side="right")

    def _build_iva(self):
        self.txt_iva = tk.Text(self.tab_iva, height=20, font=("Courier", 11))
        self.txt_iva.pack(fill="both", expand=True, padx=6, pady=6)

    # ── Importa fatture passive ──────────────────────────────────────────────
    def importa_cartella(self):
        d = filedialog.askdirectory(title="Seleziona la cartella con gli XML")
        if not d:
            return
        files = glob.glob(os.path.join(d, "*.xml")) + glob.glob(os.path.join(d, "*.XML"))
        self._processa(files)

    def importa_file(self):
        f = filedialog.askopenfilenames(title="Seleziona XML",
                                        filetypes=[("XML", "*.xml")])
        self._processa(list(f))

    def _processa(self, files):
        n_auto = n_coda = n_skip = n_err = 0
        for fp in files:
            try:
                fatt = parse_fattura(fp)
            except Exception:
                n_err += 1
                continue
            if giornale.gia_presente(self.registrazioni, fatt):
                n_skip += 1
                continue
            conto, motivo, certo = proponi_conto(fatt)
            if certo and conto:
                self._registra(fatt, conto)
                n_auto += 1
            else:
                fatt["_conto_proposto"] = conto
                fatt["_motivo"]         = motivo
                self.in_attesa.append(fatt)
                n_coda += 1
        giornale.salva(self.registrazioni)
        self._refresh_appr()
        self._refresh_giornale()
        self.lbl_stato.config(
            text=f"Importate: {n_auto} auto, {n_coda} da approvare, "
                 f"{n_skip} già presenti, {n_err} errori.")

    def _registra(self, fatt, conto):
        from scritture import scrittura_fattura_passiva
        righe = scrittura_fattura_passiva(fatt, conto)
        ok, d, a = verifica_quadratura(righe)
        if not ok:
            messagebox.showerror("Errore", f"Partita doppia non quadra: D{d} A{a}")
            return
        self.registrazioni.append({
            "chiave":    giornale.chiave_fattura(fatt),
            "data":      fatt["data"],
            "fornitore": fatt["fornitore"],
            "numero":    fatt["numero"],
            "intra_ue":  fatt["intra_ue"],
            "righe":     righe,
            "stato":     "registrata",
            "tipo":      "passiva",
        })

    def _registra_attiva(self, reg: dict):
        self.registrazioni.append(reg)
        giornale.salva(self.registrazioni)
        self._refresh_giornale()
        messagebox.showinfo("Registrata",
            f"Fattura n° {reg['numero']} registrata nel giornale.")

    # ── Approvazione manuale ─────────────────────────────────────────────────
    def _refresh_appr(self):
        self.tree_appr.delete(*self.tree_appr.get_children())
        for i, f in enumerate(self.in_attesa):
            cp = f.get("_conto_proposto")
            self.tree_appr.insert("", "end", iid=str(i), values=(
                f["fornitore"], f["data"], f["numero"],
                f"{f['imponibile']:.2f}", f"{f['imposta']:.2f}",
                "INTRA-UE" if f["intra_ue"] else "IT",
                f"{cp} - {descrizione(cp)}" if cp else "(da scegliere)",
                f.get("_motivo", "")))

    def _sel_appr(self, _e):
        sel = self.tree_appr.selection()
        if not sel:
            return
        f = self.in_attesa[int(sel[0])]
        cp = f.get("_conto_proposto")
        if cp:
            self.combo_conto.set(f"{cp} - {descrizione(cp)}")

    def approva(self):
        sel = self.tree_appr.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona una fattura dalla lista.")
            return
        val = self.combo_conto.get()
        if not val:
            messagebox.showinfo("Info", "Scegli un conto.")
            return
        conto = val.split(" - ")[0]
        idx   = int(sel[0])
        f     = self.in_attesa[idx]
        if self.var_impara.get() and f.get("piva_fornitore"):
            salva_regola_piva(f["piva_fornitore"], conto)
        self._registra(f, conto)
        self.in_attesa.pop(idx)
        giornale.salva(self.registrazioni)
        self._refresh_appr()
        self._refresh_giornale()

    def approva_tutte(self):
        restanti = []
        for f in self.in_attesa:
            cp = f.get("_conto_proposto")
            if cp:
                if self.var_impara.get() and f.get("piva_fornitore"):
                    salva_regola_piva(f["piva_fornitore"], cp)
                self._registra(f, cp)
            else:
                restanti.append(f)
        self.in_attesa = restanti
        giornale.salva(self.registrazioni)
        self._refresh_appr()
        self._refresh_giornale()

    # ── Giornale ─────────────────────────────────────────────────────────────
    def _refresh_giornale(self):
        self.tree_g.delete(*self.tree_g.get_children())
        td = ta = 0.0
        for r in self.registrazioni:
            if r.get("stato") != "registrata":
                continue
            tag = "attiva" if r.get("tipo") == "attiva" else ""
            for j, riga in enumerate(r["righe"]):
                self.tree_g.insert("", "end", tags=(tag,), values=(
                    r["data"]      if j == 0 else "",
                    r["fornitore"] if j == 0 else "",
                    r["numero"]    if j == 0 else "",
                    r.get("tipo","passiva") if j == 0 else "",
                    riga["conto"], riga["descr"],
                    f"{riga['dare']:.2f}"  if riga["dare"]  else "",
                    f"{riga['avere']:.2f}" if riga["avere"] else ""))
                td += riga["dare"]
                ta += riga["avere"]
        self.lbl_tot.config(
            text=f"Totale Dare: € {td:,.2f}   |   Totale Avere: € {ta:,.2f}   "
                 f"|   {'✓ quadra' if abs(td-ta)<0.01 else '✗ NON quadra'}")
        self._refresh_iva()

    def _refresh_iva(self):
        saldi   = giornale.saldi_per_conto(self.registrazioni)
        iva_c   = saldi.get("18", {"dare": 0, "avere": 0})
        iva_d45 = saldi.get("45", {"dare": 0, "avere": 0})
        iva_d48 = saldi.get("48", {"dare": 0, "avere": 0})
        cred    = iva_c["dare"]  - iva_c["avere"]
        deb     = (iva_d45["avere"] - iva_d45["dare"]) + (iva_d48["avere"] - iva_d48["dare"])
        saldo   = deb - cred
        t = "PROSPETTO IVA (periodo corrente)\n" + "=" * 46 + "\n\n"
        t += f"  IVA a credito (acquisti) ....... € {cred:>12,.2f}\n"
        t += f"  IVA a debito  (vendite/RC) ..... € {deb:>12,.2f}\n"
        t += "  " + "-" * 42 + "\n"
        if saldo >= 0:
            t += f"  IVA DA VERSARE ................. € {saldo:>12,.2f}\n"
        else:
            t += f"  CREDITO IVA da riportare ....... € {-saldo:>12,.2f}\n"
        t += "\n(Include reverse charge intra-UE: registrato a debito e credito, saldo zero.)"
        self.txt_iva.delete("1.0", "end")
        self.txt_iva.insert("1.0", t)

    def esporta_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Data","Fornitore/Cliente","Numero","Tipo","Conto",
                        "Descrizione","Dare","Avere"])
            for r in self.registrazioni:
                if r.get("stato") != "registrata":
                    continue
                for j, riga in enumerate(r["righe"]):
                    w.writerow([
                        r["data"]      if j == 0 else "",
                        r["fornitore"] if j == 0 else "",
                        r["numero"]    if j == 0 else "",
                        r.get("tipo","passiva") if j == 0 else "",
                        riga["conto"], riga["descr"],
                        f"{riga['dare']:.2f}"  if riga["dare"]  else "",
                        f"{riga['avere']:.2f}" if riga["avere"] else ""])
        messagebox.showinfo("Esportato", f"Giornale esportato in:\n{path}")

    def _apri_impostazioni(self):
        ImpostazioniDialog(self)


if __name__ == "__main__":
    App().mainloop()
