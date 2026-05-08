#!/usr/bin/env python3
"""
Tests de régression pour Siegfried Python.
Exécuter : python test_siegfried.py
Aucune dépendance externe requise (ne teste pas l'extraction PDF/DOCX).
"""
import sys
import traceback
from pathlib import Path

# Force UTF-8 sur Windows (console CP1252 par défaut)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ─── Résultat de test ─────────────────────────────────────────────────

PASS = 0
FAIL = 0


def ok(label: str, detail: str = "") -> None:
    global PASS
    PASS += 1
    print(f"  OK  {label}")


def fail(label: str, detail: str = "") -> None:
    global FAIL
    FAIL += 1
    msg = f"  FAIL  {label}"
    if detail:
        msg += f"\n        detail: {detail}"
    print(msg)


def expect(label: str, condition: bool, detail: str = "") -> None:
    (ok if condition else fail)(label, detail)


# ═══════════════════════════════════════════════════════════════════════
#  1. Checksums
# ═══════════════════════════════════════════════════════════════════════

def test_checksums() -> None:
    print("\n── Checksums ─────────────────────────────────────────────")
    from regex_fr import _validate_iban, _validate_nir, _validate_siren

    # IBAN valides
    expect("IBAN FR valide", _validate_iban("FR7630006000011234567890189"))
    expect("IBAN FR avec espaces", _validate_iban("FR76 3000 6000 0112 3456 7890 189"))
    expect("IBAN DE valide", _validate_iban("DE89370400440532013000"))
    # IBAN invalides
    expect("IBAN invalide (mod-97 ≠ 1)", not _validate_iban("FR7630006000011234567890188"))
    expect("IBAN trop court", not _validate_iban("FR76300"))

    # SIREN valides (Luhn)
    expect("SIREN valide 552 032 534", _validate_siren("552032534"))
    expect("SIREN avec espaces", _validate_siren("552 032 534"))
    # SIREN invalides
    expect("SIREN invalide (Luhn KO)", not _validate_siren("123456789"))
    expect("SIREN commençant par 0", not _validate_siren("012345678"))
    expect("SIREN tous identiques", not _validate_siren("111111111"))

    # NIR valides — clé = 97 - (1850575123456 % 97) = 97 - 24 = 73
    expect("NIR valide 1 85 05 75 123 456 73",
           _validate_nir("1 85 05 75 123 456 73"))
    # NIR invalide
    expect("NIR invalide (clé 78 au lieu de 73)", not _validate_nir("1 85 05 75 123 456 78"))
    expect("NIR trop court", not _validate_nir("185057512345"))


# ═══════════════════════════════════════════════════════════════════════
#  2. Détection PII structurée
# ═══════════════════════════════════════════════════════════════════════

def test_structured_pii() -> None:
    print("\n── PII structurée ────────────────────────────────────────")
    from regex_fr import find_structured_pii

    text = (
        "Contacter jean.martin@exemple.fr ou 06 12 34 56 78.\n"
        "IBAN FR76 3000 6000 0112 3456 7890 189.\n"
        "SIREN 552 032 534.\n"
        "NIR : 1 85 05 75 123 456 73.\n"
        "RG n°24/12345.\n"
        "Né le 15/03/1985 à Paris.\n"
        "Audience du 12/06/2024.\n"
        "Domicile : 12 rue de la Paix, 75001 Paris.\n"
    )

    matches = find_structured_pii(text)
    cats = {m.category for m in matches}

    expect("EMAIL détecté", "EMAIL" in cats, str(cats))
    expect("TEL détecté", "TEL" in cats, str(cats))
    expect("IBAN détecté", "IBAN" in cats, str(cats))
    expect("SIREN détecté", "SIREN" in cats, str(cats))
    expect("NIR détecté", "NIR" in cats, str(cats))
    expect("NUM_DOSSIER détecté", "NUM_DOSSIER" in cats, str(cats))
    expect("DATE_NAISSANCE détecté (né le)", "DATE_NAISSANCE" in cats, str(cats))
    expect("ADRESSE détectée", "ADRESSE" in cats, str(cats))

    # L'IBAN doit contenir le bon texte
    ibans = [m for m in matches if m.category == "IBAN"]
    expect("IBAN texte correct", any("FR76" in m.text for m in ibans),
           str([m.text for m in ibans]))


# ═══════════════════════════════════════════════════════════════════════
#  3. Détection de personnes
# ═══════════════════════════════════════════════════════════════════════

def test_person_names() -> None:
    print("\n── Noms de personnes ─────────────────────────────────────")
    from regex_fr import find_person_names, find_avocats

    text = (
        "Monsieur Jean DUPONT a assigné Madame Marie MARTIN.\n"
        "Le demandeur Pierre LEBLANC est représenté par Maître Sophie DURAND.\n"
        "ENTRE : François BERNARD et la société SAS TechCorp.\n"
    )

    persons = find_person_names(text)
    person_texts = [m.text for m in persons]

    expect("Jean DUPONT détecté", any("DUPONT" in t for t in person_texts),
           str(person_texts))
    expect("Marie MARTIN détectée", any("MARTIN" in t for t in person_texts),
           str(person_texts))
    expect("Pierre LEBLANC détecté", any("LEBLANC" in t for t in person_texts),
           str(person_texts))
    expect("François BERNARD détecté (ENTRE pattern)", any("BERNARD" in t for t in person_texts),
           str(person_texts))

    avocats = find_avocats(text)
    avocat_texts = [m.text for m in avocats]
    expect("Sophie DURAND détectée comme AVOCAT", any("DURAND" in t for t in avocat_texts),
           str(avocat_texts))


# ═══════════════════════════════════════════════════════════════════════
#  4. PseudoMap — cohérence cross-document
# ═══════════════════════════════════════════════════════════════════════

def test_pseudo_map() -> None:
    print("\n── PseudoMap ─────────────────────────────────────────────")
    from pseudo_map import PseudoMap

    pm = PseudoMap()

    p1 = pm.assign("Jean DUPONT", "PERSONNE")
    p2 = pm.assign("jean dupont", "PERSONNE")   # normalisé → même pseudonyme
    p3 = pm.assign("Marie MARTIN", "PERSONNE")
    p4 = pm.assign("Jean DUPONT", "PERSONNE")   # déjà connu

    expect("Pseudonyme format PERSONNE_001", p1 == "PERSONNE_001", p1)
    expect("Casse ignorée pour cohérence", p1 == p2, f"{p1} ≠ {p2}")
    expect("Entité différente → pseudonyme différent", p1 != p3, f"{p1} == {p3}")
    expect("Même entité → même pseudonyme", p1 == p4, f"{p1} ≠ {p4}")

    d = pm.to_dict()
    expect("to_dict contient PERSONNE_001", "PERSONNE_001" in d, str(d))
    expect("Valeur originale préservée", d["PERSONNE_001"] == "Jean DUPONT",
           d.get("PERSONNE_001"))


# ═══════════════════════════════════════════════════════════════════════
#  5. Pipeline complet — apply_pseudonyms
# ═══════════════════════════════════════════════════════════════════════

def test_pipeline() -> None:
    print("\n── Pipeline complet ──────────────────────────────────────")
    from anonymizer import analyze, apply_pseudonyms
    from pseudo_map import PseudoMap

    text = (
        "Monsieur Jean DUPONT, né le 15/03/1985, demeurant au "
        "12 rue de la Paix 75001 Paris, titulaire du compte "
        "FR76 3000 6000 0112 3456 7890 189, a contacté "
        "jean.dupont@example.com pour l'audience du 10/01/2024.\n"
        "Jean DUPONT a ensuite rencontré Madame Marie MARTIN.\n"
    )

    pm = PseudoMap()
    entities = analyze(text, pm)
    anonymized = apply_pseudonyms(text, entities)

    # Les PII doivent avoir disparu
    expect("Nom DUPONT remplacé", "DUPONT" not in anonymized,
           anonymized[:200])
    expect("IBAN remplacé", "FR76 3000" not in anonymized,
           anonymized[:200])
    expect("Email remplacé", "jean.dupont@example.com" not in anonymized,
           anonymized[:200])
    expect("Date de naissance remplacée", "15/03/1985" not in anonymized,
           anonymized[:200])

    # La date procédurale (audience du) doit rester
    expect("Date procédurale conservée", "10/01/2024" in anonymized,
           anonymized[:300])

    # Cohérence : Jean DUPONT apparaît deux fois → même pseudonyme
    enabled = [e for e in entities if e.enabled and "DUPONT" in e.text]
    pseudos = {e.pseudonym for e in enabled}
    expect("Cohérence cross-occurrence DUPONT", len(pseudos) == 1,
           f"pseudonymes distincts : {pseudos}")

    # Les pseudonymes ont le bon format [CATEGORIE_NNN]
    import re
    placeholders = re.findall(r"\[([A-Z_]+_\d{3})\]", anonymized)
    expect("Pseudonymes au format [CAT_NNN] présents", len(placeholders) > 0,
           anonymized[:300])


# ═══════════════════════════════════════════════════════════════════════
#  6. Juritools — reclassification dates & propagation
# ═══════════════════════════════════════════════════════════════════════

def test_juritools() -> None:
    print("\n── Juritools ─────────────────────────────────────────────")
    from regex_fr import find_structured_pii
    from juritools import propagate_multi_occurrences, reclassify_dates

    # Date de naissance vs date procédurale
    text = "née le 12/05/1990, arrêt du 03/06/2023."
    raw = find_structured_pii(text)
    reclassified = reclassify_dates(text, raw)
    cats_after = {m.category for m in reclassified}

    expect("DATE_NAISSANCE conservée après reclassification",
           "DATE_NAISSANCE" in cats_after, str(cats_after))
    expect("Date procédurale supprimée (arrêt du)",
           not any(m.text == "03/06/2023" for m in reclassified),
           str([(m.category, m.text) for m in reclassified]))

    # Propagation
    from regex_fr import RawMatch
    text2 = "Jean DUPONT a signé. Jean DUPONT était présent."
    seed = [RawMatch(start=0, end=11, text="Jean DUPONT", category="PERSONNE")]
    propagated = propagate_multi_occurrences(text2, seed)
    positions = [m.start for m in propagated]
    expect("Propagation détecte la 2ème occurrence", len(propagated) >= 1,
           f"positions trouvées : {positions}")


# ═══════════════════════════════════════════════════════════════════════
#  7. Sortie Markdown
# ═══════════════════════════════════════════════════════════════════════

def test_markdown_output() -> None:
    print("\n── Format Markdown ───────────────────────────────────────")
    from anonymizer import analyze, apply_pseudonyms
    from pseudo_map import PseudoMap
    import re

    text = "Monsieur Paul DUMONT, SIREN 552 032 534, tél. 06 99 88 77 66."
    pm = PseudoMap()
    entities = analyze(text, pm)
    anon = apply_pseudonyms(text, entities)

    # Vérifie que les pseudonymes sont bien entre crochets
    pattern = re.compile(r"\[[A-Z_]+_\d{3}\]")
    found = pattern.findall(anon)
    expect("Pseudonymes entre crochets dans la sortie", len(found) > 0,
           repr(anon))

    # Vérifie que le nom original n'est plus là
    expect("DUMONT absent de la sortie", "DUMONT" not in anon, repr(anon))

    print(f"  → Exemple de sortie : {repr(anon[:120])}")


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════

def main() -> None:
    print("Siegfried -- tests de regression\n" + "=" * 50)

    suites = [
        test_checksums,
        test_structured_pii,
        test_person_names,
        test_pseudo_map,
        test_pipeline,
        test_juritools,
        test_markdown_output,
    ]

    for suite in suites:
        try:
            suite()
        except Exception:
            global FAIL
            FAIL += 1
            print(f"\n  ✗  EXCEPTION dans {suite.__name__}:")
            traceback.print_exc()

    print(f"\n{'=' * 50}")
    print(f"  {PASS} passe(s)   {FAIL} echoue(s)")

    if FAIL:
        print("\n  Des corrections sont necessaires avant utilisation.")
        sys.exit(1)
    else:
        print("\n  Tous les tests passent -- moteur operationnel.")
        sys.exit(0)


if __name__ == "__main__":
    main()
