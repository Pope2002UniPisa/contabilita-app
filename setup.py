from setuptools import setup

APP = ["app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "Contabilita.icns",
    "plist": {
        "CFBundleName": "Contabilità",
        "CFBundleDisplayName": "Contabilità Automatica",
        "CFBundleIdentifier": "it.pope2002.contabilita",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
        "LSUIElement": False,
    },
    "packages": [],
    "includes": [
        "parser_fattura",
        "motore_codifica",
        "scritture",
        "piano_conti",
        "giornale",
        "bilancio_excel",
        "bilancio_view",
        "fattura_attiva",
        "anagrafica",
        "openpyxl",
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
