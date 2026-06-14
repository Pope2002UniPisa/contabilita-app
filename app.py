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
import config
import notifiche


# ══════════════════════════════════════════════════════════════
#  DIALOG IMPOSTAZIONI AZIENDA
# ══════════════════════════════════════════════════════════════
class ImpostazioniDialog(tk.Toplevel):
    _CAMPI_AZIENDA = [
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
        self.title("Impostazioni")
        self.resizable(False, False)
        self._on_save = on_save
        self._vars = {}
        azienda = carica_azienda()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Tab Azienda ──────────────────────────────────────────────────
        frm = ttk.Frame(nb, padding=16)
        nb.add(frm, text="Dati Azienda")
        for row, (key, label) in enumerate(self._CAMPI_AZIENDA):
            ttk.Label(frm, text=label + ":").grid(row=row, column=0, sticky="e", pady=2, padx=(0,8))
            var = tk.StringVar(value=azienda.get(key, ""))
            ttk.Entry(frm, textvariable=var, width=36).grid(row=row, column=1, sticky="w")
            self._vars[key] = var

        # ── Tab Cartella Dati (sync) ──────────────────────────────────────
        sync_frm = ttk.Frame(nb, padding=16)
        nb.add(sync_frm, text="Cartella Dati / Sync")

        ttk.Label(sync_frm,
            text="Cartella dove vengono salvati giornale, bilancio e anagrafica.\n"
                 "Per sincronizzare Mac ↔ Windows in tempo reale:\n"
                 "scegli una cartella OneDrive o Dropbox condivisa.",
            justify="left", foreground="#555555").pack(anchor="w", pady=(0, 12))

        path_frm = ttk.Frame(sync_frm)
        path_frm.pack(fill="x")
        self._data_dir_var = tk.StringVar(value=config.get_data_dir())
        ttk.Entry(path_frm, textvariable=self._data_dir_var,
                  width=44, state="readonly").pack(side="left")
        ttk.Button(path_frm, text="Cambia…",
                   command=self._cambia_cartella).pack(side="left", padx=6)

        ttk.Label(sync_frm,
            text="\nCartella attuale:  " + config.get_data_dir(),
            foreground="#888888").pack(anchor="w", pady=(8, 0))

        ttk.Label(sync_frm,
            text="⚠️  Dopo aver cambiato cartella riavvia l'app.",
            foreground="#cc6600").pack(anchor="w", pady=(4, 0))

        btn = ttk.Frame(self, padding=(16, 0, 16, 12))
        btn.pack(fill="x")
        ttk.Button(btn, text="Salva", command=self._salva).pack(side="right")
        ttk.Button(btn, text="Annulla", command=self.destroy).pack(side="right", padx=6)

    def _cambia_cartella(self):
        d = filedialog.askdirectory(title="Scegli cartella dati (es. OneDrive/ContabilitaApp)")
        if d:
            self._data_dir_var.set(d)

    def _salva(self):
        dati = {k: v.get().strip() for k, v in self._vars.items()}
        salva_azienda(dati)
        new_dir = self._data_dir_var.get().strip()
        if new_dir and new_dir != config.get_data_dir():
            config.set_data_dir(new_dir)
        if self._on_save:
            self._on_save()
        self.destroy()


# ══════════════════════════════════════════════════════════════
#  DIALOG NUOVO CLIENTE
# ══════════════════════════════════════════════════════════════
class GestisciClientiDialog(tk.Toplevel):
    """Lista clienti con modifica ed eliminazione."""
    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        self.title("Gestisci clienti")
        self.geometry("680x420")
        self._on_change = on_change
        self._build()

    def _build(self):
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill="both", expand=True)

        cols = ("denominazione", "piva", "email", "telefono")
        self._tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
        for c, w, lbl in zip(cols, (220,120,180,120),
                              ("Ragione sociale","P.IVA","Email","Telefono")):
            self._tree.heading(c, text=lbl)
            self._tree.column(c, width=w, anchor="w")
        vsb = ttk.Scrollbar(frm, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._ricarica()

        btn = ttk.Frame(self, padding=(8, 0, 8, 10))
        btn.pack(fill="x")
        ttk.Button(btn, text="✏️ Modifica selezionato",
                   command=self._modifica).pack(side="left")
        ttk.Button(btn, text="🗑 Elimina selezionato",
                   command=self._elimina).pack(side="left", padx=8)
        ttk.Button(btn, text="Chiudi",
                   command=self.destroy).pack(side="right")

    def _ricarica(self):
        self._tree.delete(*self._tree.get_children())
        for i, c in enumerate(carica_clienti()):
            self._tree.insert("", "end", iid=str(i),
                values=(c.get("denominazione",""), c.get("piva",""),
                        c.get("email",""), c.get("telefono","")))

    def _modifica(self):
        sel = self._tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        clienti = carica_clienti()
        ModificaClienteDialog(self, clienti[idx], idx, on_save=self._dopo_modifica)

    def _dopo_modifica(self):
        self._ricarica()
        if self._on_change:
            self._on_change()

    def _elimina(self):
        sel = self._tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        clienti = carica_clienti()
        nome = clienti[idx].get("denominazione", "?")
        if messagebox.askyesno("Conferma", f"Eliminare '{nome}'?", parent=self):
            clienti.pop(idx)
            salva_clienti(clienti)
            self._ricarica()
            if self._on_change:
                self._on_change()


class ModificaClienteDialog(tk.Toplevel):
    _CAMPI = [
        ("denominazione","Ragione sociale"), ("piva","Partita IVA"),
        ("codice_fiscale","Codice fiscale"), ("paese","Paese (IT)"),
        ("via","Indirizzo"), ("cap","CAP"), ("comune","Comune"),
        ("provincia","Provincia"), ("nazione","Nazione (IT)"),
        ("codice_sdi","Codice SDI"), ("pec","PEC"),
        ("email","Email"), ("telefono","Telefono/WhatsApp"),
    ]

    def __init__(self, parent, cliente: dict, idx: int, on_save=None):
        super().__init__(parent)
        self.title(f"Modifica — {cliente.get('denominazione','')}")
        self.resizable(False, False)
        self._idx = idx
        self._on_save = on_save
        self._vars = {}

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)
        for row, (key, label) in enumerate(self._CAMPI):
            ttk.Label(frm, text=label+":").grid(row=row,column=0,sticky="e",pady=2,padx=(0,8))
            var = tk.StringVar(value=cliente.get(key,""))
            ttk.Entry(frm, textvariable=var, width=36).grid(row=row,column=1,sticky="w")
            self._vars[key] = var

        btn = ttk.Frame(self, padding=(16,0,16,12))
        btn.pack(fill="x")
        ttk.Button(btn, text="Salva", command=self._salva).pack(side="right")
        ttk.Button(btn, text="Annulla", command=self.destroy).pack(side="right", padx=6)

    def _salva(self):
        clienti = carica_clienti()
        clienti[self._idx] = {k: v.get().strip() for k, v in self._vars.items()}
        salva_clienti(clienti)
        if self._on_save:
            self._on_save()
        self.destroy()


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
        ("email",          "Email (per invio fatture)"),
        ("telefono",       "Telefono/WhatsApp"),
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
        ttk.Button(top, text="✏️ Gestisci", width=9,
                   command=self._gestisci_clienti).grid(row=0, column=3, padx=2)
        self._aggiorna_clienti()

        # Riga 2: data, numero, tipo
        ttk.Label(top, text="Data:").grid(row=1, column=0, sticky="e", pady=(6, 0))
        self._data_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(top, textvariable=self._data_var, width=12).grid(row=1, column=1, sticky="w", pady=(6, 0))

        meta = ttk.Frame(top)
        meta.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Label(meta, text="Tipo doc:").pack(side="left")
        self._tipo_var = tk.StringVar(value=config.TIPI_DOCUMENTO[0][1])
        ttk.Combobox(meta, textvariable=self._tipo_var, width=28, state="readonly",
                     values=[v for _, v in config.TIPI_DOCUMENTO]).pack(side="left", padx=(4, 16))
        ttk.Label(meta, text="Pagamento:").pack(side="left")
        self._pag_var = tk.StringVar(value=config.MODALITA_PAGAMENTO[0][1])
        ttk.Combobox(meta, textvariable=self._pag_var, width=28, state="readonly",
                     values=[v for _, v in config.MODALITA_PAGAMENTO]).pack(side="left", padx=4)

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

        # Notifiche — abilitate solo dopo aver salvato l'XML
        sep = ttk.Separator(btn_frm, orient="vertical")
        sep.pack(side="left", fill="y", padx=12)
        self._btn_email = ttk.Button(btn_frm, text="📧 Invia per Email",
                                     command=self._invia_email, state="disabled")
        self._btn_email.pack(side="left")
        self._btn_wa = ttk.Button(btn_frm, text="📱 Invia su WhatsApp",
                                  command=self._invia_wa, state="disabled")
        self._btn_wa.pack(side="left", padx=6)

        # Stato interno per notifiche
        self._ultimo_xml  = None
        self._ultima_fatt = None
        self._ultima_az   = None

    def _aggiorna_clienti(self, nuovo=None):
        clienti = carica_clienti()
        self._clienti_lista = clienti
        nomi = [c.get("denominazione", "") for c in clienti]
        self._combo_clienti["values"] = nomi
        if nuovo:
            self._cliente_var.set(nuovo.get("denominazione", ""))

    def _nuovo_cliente(self):
        NuovoClienteDialog(self, on_save=self._aggiorna_clienti)

    def _gestisci_clienti(self):
        GestisciClientiDialog(self, on_change=lambda: self._aggiorna_clienti())

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
            "tipo_doc":          self._tipo_var.get().split(" ")[0],      # "TD01 — Fattura" → "TD01"
            "modalita_pagamento":self._pag_var.get().split(" ")[0],       # "MP05 — ..." → "MP05"
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
            self._ultimo_xml   = path
            self._ultima_fatt  = fatt
            self._ultima_az    = azienda
            messagebox.showinfo("Salvato", f"Fattura XML salvata in:\n{path}")
            self._abilita_notifiche(True)
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

    def _abilita_notifiche(self, on: bool):
        state = "normal" if on else "disabled"
        self._btn_email.config(state=state)
        self._btn_wa.config(state=state)

    def _invia_email(self):
        try:
            obj, body = notifiche.testo_fattura_email(self._ultima_fatt, self._ultima_az)
            dest = self._ultima_fatt["cliente"].get("email", "")
            notifiche.invia_email(dest, obj, body, allegato=self._ultimo_xml)
        except Exception as e:
            messagebox.showerror("Errore email", str(e))

    def _invia_wa(self):
        try:
            msg = notifiche.testo_fattura_whatsapp(self._ultima_fatt, self._ultima_az)
            tel = self._ultima_fatt["cliente"].get("telefono", "")
            notifiche.invia_whatsapp(tel, msg)
        except Exception as e:
            messagebox.showerror("Errore WhatsApp", str(e))


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

        # Tab 6 — Movimenti / Pagamenti
        self.tab_pag = ttk.Frame(nb)
        nb.add(self.tab_pag, text="💳 Movimenti")
        self._build_pagamenti()

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

        # Menu tasto destro
        self._menu_g = tk.Menu(self.tree_g, tearoff=0)
        self._menu_g.add_command(label="🗑  Elimina questa registrazione",
                                  command=self._elimina_registrazione)
        self.tree_g.bind("<Button-2>", self._show_menu_g)
        self.tree_g.bind("<Button-3>", self._show_menu_g)

        bar = ttk.Frame(self.tab_giorn, padding=6)
        bar.pack(fill="x")
        self.lbl_tot = ttk.Label(bar, text="")
        self.lbl_tot.pack(side="left")
        ttk.Button(bar, text="🗑 Elimina selezionata",
                   command=self._elimina_registrazione).pack(side="left", padx=12)
        ttk.Button(bar, text="Esporta giornale (CSV)",
                   command=self.esporta_csv).pack(side="right")

    def _build_iva(self):
        self.txt_iva = tk.Text(self.tab_iva, height=20, font=("Courier", 11))
        self.txt_iva.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_pagamenti(self):
        """Tab Movimenti: incassi, pagamenti fornitori, tasse, altri movimenti."""
        # ── Form registrazione ────────────────────────────────────────────────
        form = ttk.LabelFrame(self.tab_pag, text="Nuovo movimento", padding=10)
        form.pack(fill="x", padx=8, pady=8)

        _TIPI = [
            ("incasso_cliente",    "Incasso da cliente  (Banca ← Crediti clienti)"),
            ("pagamento_fornitore","Pagamento fornitore (Banca → Debiti fornitori)"),
            ("pagamento_tasse",    "Pagamento imposte   (Banca → Erario c/IVA o IRPEF)"),
            ("prelievo",           "Prelievo/uscita cassa generica"),
            ("versamento",         "Versamento/entrata cassa generica"),
        ]
        self._mov_tipo = tk.StringVar(value=_TIPI[0][0])

        for col, (cod, lbl) in enumerate(_TIPI):
            ttk.Radiobutton(form, text=lbl, variable=self._mov_tipo,
                            value=cod).grid(row=0, column=col, sticky="w",
                                            padx=6, pady=(0, 6))

        ttk.Label(form, text="Data:").grid(row=1, column=0, sticky="e", padx=(0,4))
        self._mov_data = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(form, textvariable=self._mov_data, width=12).grid(row=1, column=1, sticky="w")

        ttk.Label(form, text="Controparte:").grid(row=1, column=2, sticky="e", padx=(12,4))
        self._mov_cp = tk.StringVar()
        ttk.Entry(form, textvariable=self._mov_cp, width=28).grid(row=1, column=3, sticky="w")

        ttk.Label(form, text="Importo €:").grid(row=2, column=0, sticky="e", padx=(0,4), pady=4)
        self._mov_importo = tk.StringVar(value="0.00")
        ttk.Entry(form, textvariable=self._mov_importo, width=12).grid(row=2, column=1, sticky="w")

        ttk.Label(form, text="Note:").grid(row=2, column=2, sticky="e", padx=(12,4))
        self._mov_note = tk.StringVar()
        ttk.Entry(form, textvariable=self._mov_note, width=28).grid(row=2, column=3, sticky="w")

        ttk.Button(form, text="✓ Registra movimento",
                   command=self._registra_movimento).grid(row=3, column=0, columnspan=4,
                                                          pady=(8,0), sticky="w")

        # ── Elenco movimenti già registrati ───────────────────────────────────
        lst = ttk.LabelFrame(self.tab_pag, text="Movimenti registrati", padding=6)
        lst.pack(fill="both", expand=True, padx=8, pady=(0,8))
        cols = ("data", "tipo", "controparte", "importo", "note")
        self.tree_mov = ttk.Treeview(lst, columns=cols, show="headings")
        for c, w, lbl in zip(cols, (90,180,200,100,200),
                              ("Data","Tipo","Controparte","Importo €","Note")):
            self.tree_mov.heading(c, text=lbl)
            self.tree_mov.column(c, width=w, anchor="w")
        vsb = ttk.Scrollbar(lst, orient="vertical", command=self.tree_mov.yview)
        self.tree_mov.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree_mov.pack(fill="both", expand=True)
        self._refresh_movimenti()

    def _registra_movimento(self):
        try:
            importo = round(float(self._mov_importo.get().replace(",",".")), 2)
        except ValueError:
            messagebox.showerror("Errore", "Importo non valido.")
            return
        if importo <= 0:
            messagebox.showerror("Errore", "Importo deve essere > 0.")
            return

        tipo  = self._mov_tipo.get()
        data  = self._mov_data.get().strip()
        cp    = self._mov_cp.get().strip() or tipo
        note  = self._mov_note.get().strip()

        # Mappa tipo → scrittura contabile
        _MAPPE = {
            "incasso_cliente":     [("20","Banca c/c",importo,0),
                                    ("15",f"Crediti c/ {cp}",0,importo)],
            "pagamento_fornitore": [("40",f"Debiti c/ {cp}",importo,0),
                                    ("20","Banca c/c",0,importo)],
            "pagamento_tasse":     [("48","Erario c/IVA",importo,0),
                                    ("20","Banca c/c",0,importo)],
            "prelievo":            [("21","Cassa",0,importo),
                                    ("20","Banca c/c",importo,0)],
            "versamento":          [("20","Banca c/c",importo,0),
                                    ("21","Cassa",0,importo)],
        }
        righe_cont = []
        for conto, descr, dare, avere in _MAPPE.get(tipo, []):
            righe_cont.append({"conto":conto,"descr":descr,"dare":dare,"avere":avere})

        reg = {
            "chiave":    f"MOV|{data}|{tipo}|{importo}|{cp}",
            "data":      data,
            "fornitore": cp,
            "numero":    "",
            "intra_ue":  False,
            "stato":     "registrata",
            "tipo":      "movimento",
            "mov_tipo":  tipo,
            "note":      note,
            "righe":     righe_cont,
        }
        self.registrazioni.append(reg)
        giornale.salva(self.registrazioni)
        self._refresh_giornale()
        self._refresh_movimenti()
        self.bilancio_view.aggiorna_silenzioso()
        self._mov_cp.set("")
        self._mov_importo.set("0.00")
        self._mov_note.set("")
        messagebox.showinfo("Registrato", f"Movimento € {importo:,.2f} registrato.")

    def _refresh_movimenti(self):
        self.tree_mov.delete(*self.tree_mov.get_children())
        _LABEL = {
            "incasso_cliente":"Incasso cliente","pagamento_fornitore":"Pag. fornitore",
            "pagamento_tasse":"Pag. imposte","prelievo":"Prelievo","versamento":"Versamento",
        }
        for r in reversed(self.registrazioni):
            if r.get("tipo") != "movimento":
                continue
            self.tree_mov.insert("", "end", values=(
                r.get("data",""), _LABEL.get(r.get("mov_tipo",""),"Movimento"),
                r.get("fornitore",""), f"{sum(x['dare'] for x in r['righe'] if x['conto']=='20'):,.2f}",
                r.get("note","")))

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
        self.bilancio_view.aggiorna_silenzioso()
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
        self.bilancio_view.aggiorna_silenzioso()

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
        self.bilancio_view.aggiorna_silenzioso()

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

    def _show_menu_g(self, event):
        row = self.tree_g.identify_row(event.y)
        if row:
            self.tree_g.selection_set(row)
            self._menu_g.post(event.x_root, event.y_root)

    def _elimina_registrazione(self):
        sel = self.tree_g.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona una riga del giornale.")
            return
        # Trova la chiave della registrazione dalla riga selezionata
        item = self.tree_g.item(sel[0])
        data_val = item["values"][0]   # colonna Data (non vuota solo prima riga del gruppo)
        fornitore_val = item["values"][1]
        numero_val = item["values"][2]
        if not data_val:
            messagebox.showinfo("Info",
                "Clicca sulla prima riga di una registrazione (quella con la data).")
            return
        # Trova la registrazione corrispondente
        match = next((r for r in self.registrazioni
                      if r.get("data") == str(data_val)
                      and r.get("fornitore") == str(fornitore_val)
                      and str(r.get("numero","")) == str(numero_val)), None)
        if not match:
            messagebox.showerror("Errore", "Registrazione non trovata.")
            return
        tipo = match.get("tipo", "passiva")
        msg = (f"Eliminare la registrazione:\n"
               f"  {tipo.upper()} — {fornitore_val} n° {numero_val} del {data_val}?\n\n"
               f"L'operazione è irreversibile.")
        if messagebox.askyesno("Conferma eliminazione", msg):
            self.registrazioni.remove(match)
            giornale.salva(self.registrazioni)
            self._refresh_giornale()
            self.bilancio_view.aggiorna_silenzioso()

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
