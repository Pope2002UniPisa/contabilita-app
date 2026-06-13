"""
=====================================================================
  CONTABILITA AUTOMATICA - Fase 1
  App desktop per leggere fatture elettroniche (FatturaPA), proporne
  la contabilizzazione in partita doppia e tenere il libro giornale.

  USO: python3 app.py
  Richiede solo Python 3 (tkinter incluso). Nessuna libreria esterna.
=====================================================================
"""
import os
import glob
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from parser_fattura import parse_fattura
from motore_codifica import proponi_conto, salva_regola_piva
from scritture import scrittura_fattura_passiva, verifica_quadratura
from piano_conti import PIANO_CONTI, CONTI_COSTO, descrizione
import giornale


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Contabilità Automatica - Fase 1")
        self.geometry("1100x680")
        self.registrazioni = giornale.carica()
        self.in_attesa = []   # fatture parse-ate ma da approvare
        self._build_ui()
        self._refresh_giornale()

    # ---------------- UI ----------------
    def _build_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="📂 Importa cartella fatture (XML)",
                   command=self.importa_cartella).pack(side="left")
        ttk.Button(top, text="📄 Importa singolo file",
                   command=self.importa_file).pack(side="left", padx=6)
        self.lbl_stato = ttk.Label(top, text="Pronto.")
        self.lbl_stato.pack(side="left", padx=12)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 1: coda approvazione
        self.tab_appr = ttk.Frame(nb)
        nb.add(self.tab_appr, text="⏳ Da approvare")
        self._build_approvazione()

        # Tab 2: libro giornale
        self.tab_giorn = ttk.Frame(nb)
        nb.add(self.tab_giorn, text="📒 Libro giornale")
        self._build_giornale()

        # Tab 3: prospetto IVA
        self.tab_iva = ttk.Frame(nb)
        nb.add(self.tab_iva, text="🧾 Prospetto IVA")
        self._build_iva()

    def _build_approvazione(self):
        cols = ("fornitore", "data", "numero", "imponibile", "iva", "tipo", "conto", "motivo")
        self.tree_appr = ttk.Treeview(self.tab_appr, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (220, 80, 90, 90, 80, 80, 200, 160)):
            self.tree_appr.heading(c, text=c.capitalize())
            self.tree_appr.column(c, width=w, anchor="w")
        self.tree_appr.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree_appr.bind("<<TreeviewSelect>>", self._sel_appr)

        bar = ttk.Frame(self.tab_appr, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Conto:").pack(side="left")
        self.combo_conto = ttk.Combobox(bar, width=45, state="readonly",
            values=[f"{k} - {v}" for k, v in {**CONTI_COSTO, "10": descrizione("10"), "60": descrizione("60")}.items()])
        # ricostruisco lista ordinata di tutti i conti costo + cespite
        conti_sel = {k: v for k, v in PIANO_CONTI.items() if v["tipo"] in ("COSTO",)}
        conti_sel["10"] = PIANO_CONTI["10"]
        self.combo_conto["values"] = [f"{k} - {PIANO_CONTI[k]['desc']}" for k in sorted(conti_sel)]
        self.combo_conto.pack(side="left", padx=6)
        self.var_impara = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Memorizza regola per questo fornitore",
                        variable=self.var_impara).pack(side="left", padx=10)
        ttk.Button(bar, text="✓ Approva e registra", command=self.approva).pack(side="left", padx=6)
        ttk.Button(bar, text="✓✓ Approva tutte con proposta", command=self.approva_tutte).pack(side="left")

    def _build_giornale(self):
        cols = ("data", "fornitore", "numero", "conto", "descr", "dare", "avere")
        self.tree_g = ttk.Treeview(self.tab_giorn, columns=cols, show="headings")
        for c, w in zip(cols, (80, 200, 90, 60, 280, 100, 100)):
            self.tree_g.heading(c, text=c.capitalize())
            self.tree_g.column(c, width=w, anchor="w")
        self.tree_g.pack(fill="both", expand=True, padx=6, pady=6)
        bar = ttk.Frame(self.tab_giorn, padding=6)
        bar.pack(fill="x")
        self.lbl_tot = ttk.Label(bar, text="")
        self.lbl_tot.pack(side="left")
        ttk.Button(bar, text="Esporta giornale (CSV)", command=self.esporta_csv).pack(side="right")

    def _build_iva(self):
        self.txt_iva = tk.Text(self.tab_iva, height=20, font=("Courier", 11))
        self.txt_iva.pack(fill="both", expand=True, padx=6, pady=6)

    # ---------------- LOGICA ----------------
    def importa_cartella(self):
        d = filedialog.askdirectory(title="Seleziona la cartella con gli XML")
        if not d:
            return
        files = glob.glob(os.path.join(d, "*.xml")) + glob.glob(os.path.join(d, "*.XML"))
        self._processa(files)

    def importa_file(self):
        f = filedialog.askopenfilenames(title="Seleziona XML", filetypes=[("XML", "*.xml")])
        self._processa(list(f))

    def _processa(self, files):
        n_auto = n_coda = n_skip = n_err = 0
        for fp in files:
            try:
                fatt = parse_fattura(fp)
            except Exception as e:
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
                fatt["_motivo"] = motivo
                self.in_attesa.append(fatt)
                n_coda += 1
        giornale.salva(self.registrazioni)
        self._refresh_appr()
        self._refresh_giornale()
        self.lbl_stato.config(
            text=f"Importate: {n_auto} automatiche, {n_coda} da approvare, "
                 f"{n_skip} già presenti, {n_err} errori.")

    def _registra(self, fatt, conto):
        righe = scrittura_fattura_passiva(fatt, conto)
        ok, d, a = verifica_quadratura(righe)
        if not ok:
            messagebox.showerror("Errore", f"Partita doppia non quadra: D{d} A{a}")
            return
        self.registrazioni.append({
            "chiave": giornale.chiave_fattura(fatt),
            "data": fatt["data"], "fornitore": fatt["fornitore"],
            "numero": fatt["numero"], "intra_ue": fatt["intra_ue"],
            "righe": righe, "stato": "registrata",
        })

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
        idx = int(sel[0])
        f = self.in_attesa[idx]
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

    def _refresh_giornale(self):
        self.tree_g.delete(*self.tree_g.get_children())
        td = ta = 0.0
        for r in self.registrazioni:
            if r["stato"] != "registrata":
                continue
            for j, riga in enumerate(r["righe"]):
                self.tree_g.insert("", "end", values=(
                    r["data"] if j == 0 else "",
                    r["fornitore"] if j == 0 else "",
                    r["numero"] if j == 0 else "",
                    riga["conto"], riga["descr"],
                    f"{riga['dare']:.2f}" if riga["dare"] else "",
                    f"{riga['avere']:.2f}" if riga["avere"] else ""))
                td += riga["dare"]; ta += riga["avere"]
        self.lbl_tot.config(text=f"Totale Dare: € {td:,.2f}   |   Totale Avere: € {ta:,.2f}   "
                                 f"|   {'✓ quadra' if abs(td-ta)<0.01 else '✗ NON quadra'}")
        self._refresh_iva()

    def _refresh_iva(self):
        saldi = giornale.saldi_per_conto(self.registrazioni)
        iva_cred = saldi.get("18", {"dare": 0, "avere": 0})
        iva_deb = saldi.get("45", {"dare": 0, "avere": 0})
        cred = iva_cred["dare"] - iva_cred["avere"]
        deb = iva_deb["avere"] - iva_deb["dare"]
        saldo = deb - cred
        t = "PROSPETTO IVA (periodo corrente)\n" + "=" * 46 + "\n\n"
        t += f"  IVA a credito (acquisti) ....... € {cred:>12,.2f}\n"
        t += f"  IVA a debito  (vendite) ........ € {deb:>12,.2f}\n"
        t += "  " + "-" * 42 + "\n"
        if saldo >= 0:
            t += f"  IVA DA VERSARE ................. € {saldo:>12,.2f}\n"
        else:
            t += f"  CREDITO IVA da riportare ....... € {-saldo:>12,.2f}\n"
        t += "\n(Nota: include l'IVA reverse charge intra-UE, registrata\n a debito e a credito, saldo zero - non altera il versamento.)"
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
            w.writerow(["Data", "Fornitore", "Numero", "Conto", "Descrizione", "Dare", "Avere"])
            for r in self.registrazioni:
                if r["stato"] != "registrata":
                    continue
                for j, riga in enumerate(r["righe"]):
                    w.writerow([r["data"] if j == 0 else "",
                                r["fornitore"] if j == 0 else "",
                                r["numero"] if j == 0 else "",
                                riga["conto"], riga["descr"],
                                f"{riga['dare']:.2f}" if riga["dare"] else "",
                                f"{riga['avere']:.2f}" if riga["avere"] else ""])
        messagebox.showinfo("Esportato", f"Giornale esportato in:\n{path}")


if __name__ == "__main__":
    App().mainloop()
