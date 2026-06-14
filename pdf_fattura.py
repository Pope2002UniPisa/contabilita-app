"""
Generatore PDF fattura attiva — formato professionale italiano A4.
Usa Arial (TrueType) per supporto completo Unicode + simbolo €.
"""
import os
import sys
import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos


def _font_dir() -> str:
    """Trova la cartella fonts/ sia in sviluppo che nel bundle .app."""
    if getattr(sys, "frozen", False):
        exe = os.path.dirname(sys.executable)
        d = os.path.normpath(os.path.join(exe, "..", "Resources", "fonts"))
    else:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    return d


def _font(name: str) -> str:
    """Percorso del font: prima nella cartella bundled, poi nel sistema."""
    bundled = os.path.join(_font_dir(), name)
    if os.path.exists(bundled):
        return bundled
    # Fallback percorsi di sistema
    candidates = [
        f"/System/Library/Fonts/Supplemental/{name}",
        f"/Library/Fonts/{name}",
        f"C:/Windows/Fonts/{name.lower().replace(' ','').replace('bold','bd')}",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return bundled  # lascia che fpdf lanci un errore descrittivo


def _num(v, dec=2) -> str:
    """Formato italiano: 1.234,56"""
    try:
        f = float(v)
        s = f"{abs(f):,.{dec}f}".replace(",","X").replace(".",",").replace("X",".")
        return f"-{s}" if f < 0 else s
    except (TypeError, ValueError):
        return str(v) if v else ""


def _dt(iso: str) -> str:
    try:
        return datetime.date.fromisoformat(iso).strftime("%d/%m/%Y")
    except Exception:
        return iso or ""


_TIPO = {"TD01":"FATTURA","TD06":"PARCELLA","TD04":"NOTA DI CREDITO",
         "TD05":"NOTA DI DEBITO","TD07":"FATTURA SEMPLIFICATA"}
_PAG  = {"MP01":"Contanti","MP02":"Assegno","MP05":"Bonifico bancario",
         "MP08":"Carta di credito/debito","MP10":"RID","MP12":"RIBA"}


class _PDF(FPDF):
    M  = 14   # margine
    CW = [97, 18, 28, 16, 28]  # Descr | Qtà | P.unit | IVA% | Importo

    def __init__(self, fattura, azienda):
        super().__init__("P", "mm", "A4")
        self.f  = fattura
        self.az = azienda
        self.set_margins(self.M, self.M, self.M)
        self.set_auto_page_break(True, margin=18)
        # Carica font Unicode
        self.add_font("Arial",  "",  _font("Arial.ttf"))
        self.add_font("Arial",  "B", _font("Arial Bold.ttf"))
        self.set_font("Arial", "", 10)

    # ── header / footer ──────────────────────────────────────────────────────
    def header(self):
        az = self.az
        self.set_font("Arial", "B", 15)
        self.cell(0, 8, az.get("denominazione",""),
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Arial", "", 9)
        self.set_text_color(80, 80, 80)
        self.cell(0, 5,
            f"P.IVA {az.get('piva','')}  ·  C.F. {az.get('codice_fiscale','')}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 5,
            f"{az.get('via','')} · {az.get('cap','')} "
            f"{az.get('comune','')} ({az.get('provincia','')})",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)
        self.ln(2)
        self.set_draw_color(180, 180, 180)
        self.line(self.M, self.get_y(), 210-self.M, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "", 8)
        self.set_text_color(150, 150, 150)
        az = self.az
        self.cell(0, 5,
            f"{az.get('denominazione','')} · P.IVA {az.get('piva','')} · "
            f"Regime fiscale {az.get('regime_fiscale','RF01')}",
            align="C")

    # ── sezione titolo fattura ────────────────────────────────────────────────
    def _titolo(self):
        tipo  = _TIPO.get(self.f.get("tipo_doc","TD01"), "FATTURA")
        self.set_fill_color(40, 40, 40)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 13)
        self.cell(0, 10,
            f"{tipo}  n° {self.f.get('numero','')}   del   {_dt(self.f.get('data',''))}",
            fill=True, align="C",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)
        self.ln(5)

    # ── dati cliente ─────────────────────────────────────────────────────────
    def _cliente(self):
        cl = self.f.get("cliente", {})
        self.set_font("Arial", "B", 10)
        self.cell(0, 6, "Destinatario",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        x0, y0 = self.get_x(), self.get_y()
        self.set_draw_color(200, 200, 200)
        # Riga 1
        self.set_font("Arial", "B", 11)
        self.cell(0, 7, cl.get("denominazione",""),
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # Riga 2
        self.set_font("Arial", "", 9)
        self.set_text_color(80, 80, 80)
        piva = cl.get("piva","–")
        self.cell(0, 5,
            f"P.IVA {piva}  ·  "
            f"{cl.get('via','')} · {cl.get('cap','')} {cl.get('comune','')}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        sdi = cl.get("codice_sdi","–")
        pec = cl.get("pec","–")
        self.cell(0, 5, f"Cod. SDI: {sdi}  ·  PEC: {pec}",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)
        # Box intorno
        self.rect(x0, y0, 210-2*self.M, self.get_y()-y0)
        self.ln(6)

    # ── tabella righe ─────────────────────────────────────────────────────────
    def _tabella(self):
        cw     = self.CW
        hdrs   = ["Descrizione", "Qtà", "Prezzo unit.", "IVA %", "Importo (€)"]
        aligns = ["L","C","R","C","R"]

        # Header
        self.set_fill_color(40, 40, 40)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 9)
        for lbl, w, al in zip(hdrs, cw, aligns):
            self.cell(w, 7, lbl, border=1, align=al, fill=True)
        self.ln()
        self.set_text_color(0, 0, 0)

        # Righe
        alt = False
        for r in self.f.get("righe", []):
            qt  = float(r.get("quantita", 1))
            pr  = float(r.get("prezzo_unitario", 0))
            al_ = float(r.get("aliquota_iva", 22))
            tot = round(qt * pr, 2)
            self.set_fill_color(248, 248, 248) if alt else self.set_fill_color(255, 255, 255)
            self.set_font("Arial", "", 9)
            x0, y0 = self.get_x(), self.get_y()
            self.multi_cell(cw[0], 6, r.get("descrizione",""),
                            border="LRB", fill=alt,
                            new_x=XPos.RIGHT, new_y=YPos.TOP)
            h = self.get_y() - y0
            self.set_xy(x0+cw[0], y0)
            for val, w, al in zip(
                [_num(qt,2), _num(pr,2), f"{al_:.0f}%", _num(tot,2)],
                cw[1:], aligns[1:]
            ):
                self.cell(w, h, val, border="LRB", align=al, fill=alt)
            self.ln()
            alt = not alt
        self.ln(4)

    # ── riepilogo IVA + totali ────────────────────────────────────────────────
    def _totali(self):
        righe = self.f.get("righe", [])
        per_al: dict = {}
        for r in righe:
            al  = float(r.get("aliquota_iva", 22))
            qt  = float(r.get("quantita", 1))
            pr  = float(r.get("prezzo_unitario", 0))
            tot = round(qt * pr, 2)
            per_al.setdefault(al, {"imp":0.0,"iva":0.0})
            per_al[al]["imp"] += tot
            per_al[al]["iva"] += round(tot * al / 100, 2)

        imp_tot = round(sum(v["imp"] for v in per_al.values()), 2)
        iva_tot = round(sum(v["iva"] for v in per_al.values()), 2)
        tot_doc = round(imp_tot + iva_tot, 2)

        rw = 55
        x  = 210 - self.M - rw*3

        # Riepilogo IVA
        self.set_xy(x, self.get_y())
        self.set_fill_color(40, 40, 40)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 9)
        for lbl, al in [("Aliquota IVA","C"),("Imponibile (€)","R"),("Imposta (€)","R")]:
            self.cell(rw, 6, lbl, border=1, align=al, fill=True)
        self.ln()
        self.set_text_color(0, 0, 0)
        self.set_font("Arial", "", 9)
        for al, v in sorted(per_al.items()):
            self.set_xy(x, self.get_y())
            self.cell(rw, 6, f"{al:.0f} %",   border=1, align="C")
            self.cell(rw, 6, _num(v["imp"]),   border=1, align="R")
            self.cell(rw, 6, _num(v["iva"]),   border=1, align="R")
            self.ln()

        self.ln(3)

        # Totale
        tw = rw*2
        tx = 210 - self.M - tw
        for lbl, val, bold in [
            ("Imponibile totale", f"€  {_num(imp_tot)}", False),
            ("IVA totale",        f"€  {_num(iva_tot)}", False),
            ("TOTALE FATTURA",    f"€  {_num(tot_doc)}", True),
        ]:
            self.set_xy(tx, self.get_y())
            if bold:
                self.set_fill_color(40, 40, 40)
                self.set_text_color(255, 255, 255)
                self.set_font("Arial", "B", 12)
                self.cell(rw, 10, lbl, border=1, align="R", fill=True)
                self.cell(rw, 10, val, border=1, align="R", fill=True)
                self.set_text_color(0, 0, 0)
            else:
                self.set_font("Arial", "", 10)
                self.cell(rw, 7, lbl, border="TLB", align="R")
                self.cell(rw, 7, val, border="TRB", align="R")
            self.ln()

        self.ln(6)

    # ── dati pagamento ────────────────────────────────────────────────────────
    def _pagamento(self):
        mod = _PAG.get(self.f.get("modalita_pagamento","MP05"), "Bonifico bancario")
        self.set_font("Arial", "", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, f"Modalità di pagamento: {mod}",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)

    # ── entry point ───────────────────────────────────────────────────────────
    def genera(self) -> bytes:
        self.add_page()
        self._titolo()
        self._cliente()
        self._tabella()
        self._totali()
        self._pagamento()
        return bytes(self.output())


def genera_pdf(fattura: dict, azienda: dict) -> bytes:
    return _PDF(fattura, azienda).genera()


def salva_pdf(fattura: dict, azienda: dict, dest_dir: str) -> str:
    piva = (azienda.get("piva") or "XXXXXXXX").replace(" ", "")
    nome = f"IT{piva}_{fattura['numero']:05d}.pdf"
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, nome)
    with open(path, "wb") as f:
        f.write(genera_pdf(fattura, azienda))
    return path
