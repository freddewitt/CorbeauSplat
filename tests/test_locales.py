"""Garde-fous i18n : alignement des 9 locales et absence de clés orphelines.

Ces tests remplacent la vérification manuelle qui laissait passer, avant l'audit
du 2026-08-07, 375 clés héritées de l'UI à onglets (aucune source ne les
référençait) tout en gardant les 9 fichiers parfaitement « alignés ».
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCALES_DIR = ROOT / "assets" / "locales"
EXPECTED_LOCALES = {"ar", "de", "en", "es", "fr", "it", "ja", "ru", "zh"}


def _load(name):
    return json.loads((LOCALES_DIR / f"{name}.json").read_text())


def _sources():
    """Concatenated Python sources of the app (locale keys may be built as
    ``tr(key, default)`` from literal tables, so a substring scan is enough)."""
    text = ""
    for path in list((ROOT / "app").rglob("*.py")) + [ROOT / "main.py"]:
        text += path.read_text(errors="ignore")
    return text


def test_all_nine_locales_present():
    found = {p.stem for p in LOCALES_DIR.glob("*.json")}
    assert found == EXPECTED_LOCALES


def test_locales_share_the_exact_same_keys():
    """Une clé ajoutée doit l'être dans les 9 fichiers, pas seulement fr/en."""
    reference = set(_load("fr"))
    for name in sorted(EXPECTED_LOCALES):
        keys = set(_load(name))
        assert keys - reference == set(), f"{name}.json a des clés en trop"
        assert reference - keys == set(), f"{name}.json a des clés manquantes"


def test_no_orphan_locale_keys():
    """Aucune clé de locale ne doit être absente de tout le code applicatif."""
    sources = _sources()
    orphans = sorted(k for k in _load("fr") if k not in sources)
    assert orphans == [], f"clés de locale jamais référencées : {orphans}"


def test_every_tr_literal_has_a_translation():
    """Toute clé passée en littéral à tr() doit exister dans les 9 locales."""
    used = set(re.findall(r'\btr\(\s*"([^"]+)"', _sources()))
    assert used, "aucun appel tr(\"...\") détecté — le scan est cassé"
    for name in sorted(EXPECTED_LOCALES):
        missing = sorted(used - set(_load(name)))
        assert missing == [], f"{name}.json : clés manquantes {missing}"
