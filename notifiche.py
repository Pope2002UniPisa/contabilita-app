"""
Invio notifiche: email (con allegato) e WhatsApp.
Mac: usa Mail.app via AppleScript per allegare il PDF/XML.
Windows: usa Outlook via win32com se disponibile, altrimenti mailto:.
WhatsApp: apre wa.me nel browser (funziona ovunque).
"""
import os
import sys
import subprocess
import urllib.parse
import webbrowser


# ── EMAIL ────────────────────────────────────────────────────────────────────

def _email_mac(dest, oggetto, corpo, allegati=None):
    corpo_esc   = corpo.replace('"', '\\"').replace('\n', '\\n')
    oggetto_esc = oggetto.replace('"', '\\"')
    lines = [
        'tell application "Mail"',
        '    activate',
        '    set msg to make new outgoing message',
        f'    set subject of msg to "{oggetto_esc}"',
        f'    set content of msg to "{corpo_esc}"',
        f'    make new to recipient at end of to recipients of msg '
        f'with properties {{address: "{dest}"}}',
    ]
    for a in (allegati or []):
        if a and os.path.exists(a):
            lines.append(f'    add attachment "{a}" to msg')
    lines += ['    set visible of msg to true', 'end tell']
    subprocess.run(['osascript', '-e', '\n'.join(lines)])


def _email_win(dest, oggetto, corpo, allegato=None):
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To      = dest
        mail.Subject = oggetto
        mail.Body    = corpo
        if allegato and os.path.exists(allegato):
            mail.Attachments.Add(allegato)
        mail.Display()
    except ImportError:
        _email_fallback(dest, oggetto, corpo)


def _email_fallback(dest, oggetto, corpo, **_):
    url = (f"mailto:{urllib.parse.quote(dest)}"
           f"?subject={urllib.parse.quote(oggetto)}"
           f"&body={urllib.parse.quote(corpo)}")
    webbrowser.open(url)


def invia_email(dest: str, oggetto: str, corpo: str, allegato: str = None):
    invia_email_multi(dest, oggetto, corpo, allegati=[allegato] if allegato else [])


def invia_email_multi(dest: str, oggetto: str, corpo: str, allegati: list = None):
    """Apre Mail.app/Outlook con più allegati (PDF + XML)."""
    if not dest:
        raise ValueError("Indirizzo email del cliente non presente in anagrafica.")
    allegati = [a for a in (allegati or []) if a]
    if sys.platform == "darwin":
        _email_mac(dest, oggetto, corpo, allegati)
    elif sys.platform == "win32":
        # Invia il primo allegato disponibile (Outlook non supporta multi-attach via AppleScript)
        for a in allegati:
            if os.path.exists(a):
                _email_win(dest, oggetto, corpo, a)
                break
        else:
            _email_fallback(dest, oggetto, corpo)
    else:
        _email_fallback(dest, oggetto, corpo)


# ── WHATSAPP ─────────────────────────────────────────────────────────────────

def _normalizza_telefono(tel: str) -> str:
    """Porta il numero in formato internazionale senza +."""
    digits = ''.join(c for c in tel if c.isdigit() or c == '+')
    if digits.startswith('+'):
        return digits[1:]
    if digits.startswith('00'):
        return digits[2:]
    if digits.startswith('0'):          # numero nazionale italiano
        return '39' + digits[1:]
    return '39' + digits                # assume Italia se senza prefisso


def invia_whatsapp(telefono: str, messaggio: str):
    """Apre WhatsApp Web/Desktop con numero e testo precompilati."""
    if not telefono:
        raise ValueError("Numero di telefono del cliente non presente in anagrafica.")
    num = _normalizza_telefono(telefono)
    url = f"https://wa.me/{num}?text={urllib.parse.quote(messaggio)}"
    webbrowser.open(url)


# ── TESTI PREDEFINITI ────────────────────────────────────────────────────────

def testo_fattura_email(fattura: dict, azienda: dict) -> tuple[str, str]:
    """Ritorna (oggetto, corpo) per l'email di invio fattura."""
    cliente  = fattura["cliente"].get("denominazione", "")
    numero   = fattura["numero"]
    data     = fattura["data"]
    righe    = fattura.get("righe", [])
    imp      = round(sum(float(r.get("quantita",1))*float(r.get("prezzo_unitario",0)) for r in righe), 2)
    iva      = round(sum(float(r.get("quantita",1))*float(r.get("prezzo_unitario",0))
                         *float(r.get("aliquota_iva",22))/100 for r in righe), 2)
    totale   = round(imp + iva, 2)
    emit     = azienda.get("denominazione", "")

    oggetto = f"Fattura n° {numero} del {data} — {emit}"
    corpo = (
        f"Gentile {cliente},\n\n"
        f"in allegato la fattura elettronica n° {numero} del {data}.\n\n"
        f"  Imponibile:  € {imp:,.2f}\n"
        f"  IVA:         € {iva:,.2f}\n"
        f"  Totale:      € {totale:,.2f}\n\n"
        f"Cordiali saluti,\n{emit}"
    )
    return oggetto, corpo


def testo_fattura_whatsapp(fattura: dict, azienda: dict) -> str:
    righe  = fattura.get("righe", [])
    totale = round(sum(
        float(r.get("quantita",1))*float(r.get("prezzo_unitario",0))
        *(1 + float(r.get("aliquota_iva",22))/100) for r in righe), 2)
    emit   = azienda.get("denominazione", "")
    return (
        f"Buongiorno, le inviamo la fattura n° {fattura['numero']} "
        f"del {fattura['data']} per un totale di € {totale:,.2f}.\n"
        f"Cordiali saluti,\n{emit}"
    )
