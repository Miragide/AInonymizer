"""
Port Python de src/lib/regex-fr.ts — détection PII française.
Catégories : EMAIL, TEL, NIR, IBAN, SIREN, PLAQUE, NUM_DOSSIER,
             DATE, DATE_NAISSANCE, ADRESSE, JURIDICTION, PERSONNE_MORALE,
             AVOCAT, MAGISTRAT, PERSONNE, LIEU.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class RawMatch:
    start: int
    end: int
    text: str
    category: str


# ═══════════════════════════════════════════════════════════════════════
#  Validation checksums
# ═══════════════════════════════════════════════════════════════════════

def _luhn(num: str) -> bool:
    if not num.isdigit() or len(num) not in (9, 14):
        return False
    total, alt = 0, False
    for ch in reversed(num):
        n = int(ch)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


def _validate_siren(s: str) -> bool:
    clean = s.replace(" ", "")
    if not _luhn(clean):
        return False
    if clean.startswith("0"):
        return False
    if len(set(clean)) == 1:   # tous identiques → faux positif
        return False
    return True


def _validate_nir(s: str) -> bool:
    digits = s.replace(" ", "")
    if len(digits) != 15:
        return False
    num = digits[:13]
    try:
        key = int(digits[13:])
    except ValueError:
        return False
    adjusted = (
        num.replace("2A", "19").replace("2a", "19")
           .replace("2B", "18").replace("2b", "18")
    )
    try:
        return 97 - int(adjusted) % 97 == key
    except ValueError:
        return False


def _validate_iban(s: str) -> bool:
    clean = s.replace(" ", "").upper()
    if not (15 <= len(clean) <= 34):
        return False
    rearranged = clean[4:] + clean[:4]
    numeric = "".join(
        str(ord(c) - 55) if c.isalpha() else c for c in rearranged
    )
    remainder = 0
    for ch in numeric:
        remainder = (remainder * 10 + int(ch)) % 97
    return remainder == 1


# ═══════════════════════════════════════════════════════════════════════
#  PII structurée (patterns + checksums)
# ═══════════════════════════════════════════════════════════════════════

_STRUCTURED: list[tuple[str, re.Pattern, Optional[int], Optional[Callable]]] = [
    ("EMAIL",
     re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
     None, None),
    ("TEL",
     re.compile(r"(?:(?:\+33|0033)\s?[1-9]|0[1-9])(?:[\s.\-]?\d{2}){4}"),
     None, None),
    ("NIR",
     re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b"),
     None, _validate_nir),
    ("IBAN",
     re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){10,30}\b"),
     None, _validate_iban),
    ("SIREN",
     re.compile(r"(?<!\d[-/.])\b\d{3}\s?\d{3}\s?\d{3}(?:\s?\d{5})?\b(?![-/.]?\d)"),
     None, _validate_siren),
    ("PLAQUE",
     re.compile(r"\b[A-Z]{2}[-\s]?\d{3}[-\s]?[A-Z]{2}\b"),
     None, None),
    ("PLAQUE",
     re.compile(r"\b\d{1,4}[-\s]?[A-Z]{2,3}[-\s]?\d{2}\b"),
     None, None),
    ("NUM_DOSSIER",
     re.compile(r"\bRG\s*(?:n°?\s*)?\d{2}[/\-]\d{3,6}\b", re.IGNORECASE),
     None, None),
    ("NUM_DOSSIER",
     re.compile(r"\bn°?\s?\d{2}[/\-]\d{3,6}\b"),
     None, None),
    ("NUM_DOSSIER",
     re.compile(r"\b(?:MINUTE|PARQUET)\s*(?:n°?\s*)?\d{2}[/\-]\d{3,8}\b", re.IGNORECASE),
     None, None),
    # Date de naissance explicite (capturée via groupe 1)
    ("DATE_NAISSANCE",
     re.compile(r"(?:n[ée]{1,2}\s+le\s+)(\d{1,2}[/\s.\-]\d{1,2}[/\s.\-]\d{2,4})", re.IGNORECASE),
     1, None),
    ("DATE_NAISSANCE",
     re.compile(
         r"(?:n[ée]{1,2}\s+le\s+)"
         r"(\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet"
         r"|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)\s+\d{2,4})",
         re.IGNORECASE,
     ),
     1, None),
    # Dates génériques
    ("DATE",
     re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}\b"),
     None, None),
    ("DATE",
     re.compile(
         r"\b\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet"
         r"|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)\s+\d{2,4}\b",
         re.IGNORECASE,
     ),
     None, None),
    # Adresse : numéro + type de voie + ville/code postal
    ("ADRESSE",
     re.compile(
         r"\b\d{1,4}(?:\s?(?:bis|ter))?,?\s+"
         r"(?:rue|avenue|av\.|boulevard|bd\.|bd|place|pl\.|impasse|imp\."
         r"|all[ée]e|chemin|route|quai|cours|passage|voie|r[ée]sidence"
         r"|lot|lotissement|hameau|lieudit|lieu-dit|square|parvis"
         r"|esplanade|promenade|sentier|traverse|mont[ée]e)"
         r"\s+[^,\n]{3,60}?(?=[,\n]|$)",
         re.IGNORECASE,
     ),
     None, None),
    ("ADRESSE",
     re.compile(r"\b\d{5}\s+[A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ'\- ]{2,40}"),
     None, None),
]


def find_structured_pii(text: str) -> list[RawMatch]:
    out: list[RawMatch] = []
    for category, pattern, group, validate in _STRUCTURED:
        for m in pattern.finditer(text):
            if group is not None:
                raw = m.group(group)
                if not raw:
                    continue
                start = m.start(group)
            else:
                raw = m.group(0)
                start = m.start()
            if validate and not validate(raw):
                continue
            out.append(RawMatch(start=start, end=start + len(raw), text=raw, category=category))
    return out


# ═══════════════════════════════════════════════════════════════════════
#  Juridictions françaises
# ═══════════════════════════════════════════════════════════════════════

_JURIDICTIONS_LIST = [
    "Cour de cassation", "Cour d'appel", "cour d'appel", "Cour d'assises",
    "Tribunal judiciaire", "tribunal judiciaire",
    "Tribunal de commerce", "tribunal de commerce",
    "Tribunal administratif", "tribunal administratif",
    "Tribunal correctionnel", "tribunal correctionnel",
    "Tribunal de police",
    r"Tribunal des affaires de s[ée]curit[ée] sociale",
    "Tribunal paritaire des baux ruraux",
    r"Tribunal de proximit[ée]",
    "Conseil de prud'hommes", "conseil de prud'hommes",
    r"Conseil d'[EÉeé]tat", "Conseil constitutionnel",
    r"Juge de l'ex[ée]cution", "Juge aux affaires familiales",
    "Juge des enfants", r"Juge d'instruction",
    r"Juge de la mise en [ée]tat",
    r"Juge des libert[ée]s et de la d[ée]tention",
    "Juge des contentieux de la protection", "Juge commissaire",
    "Cour administrative d'appel",
    "Chambre de l'instruction",
    "Chambre des appels correctionnels",
]

_JURIDICTION_RE = re.compile(
    r"(?:" + "|".join(_JURIDICTIONS_LIST) + r")"
    r"(?:\s+(?:de|d'|du|des)\s+[A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ']+(?:-[A-Za-zÀ-ÿ']+){0,4})?"
)


def find_juridictions(text: str) -> list[RawMatch]:
    return [
        RawMatch(start=m.start(), end=m.end(), text=m.group(0), category="JURIDICTION")
        for m in _JURIDICTION_RE.finditer(text)
    ]


# ═══════════════════════════════════════════════════════════════════════
#  Sociétés / personnes morales
# ═══════════════════════════════════════════════════════════════════════

_FORMES = [
    "SAS", "SASU", "SARL", "EURL", "SA", "SCI", "SCP", "SCM",
    "SNC", "GIE", "SELARL", "SELAS", "SEL", "SELAFA", "SELCA",
    "GAEC", "EARL", "SCA", "SCIC", "SCOP",
]
_FORMES_STR = "|".join(_FORMES)
_SOC_NAME = (
    r"[A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ&'\-]{1,40}"
    r"(?:[ '\-][A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ&'\-]{0,40}){0,3}"
)

_SOCIETE_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"\b(?:" + _FORMES_STR + r")\s+(" + _SOC_NAME + r")"), 1),
    (re.compile(r"\b(" + _SOC_NAME + r")\s+(?:" + _FORMES_STR + r")\b"), 1),
    (re.compile(
        r"(?:[Ll]a\s+)?(?:[Ss]oci[ée]t[ée]|[Ll]'(?:entreprise|association"
        r"|fondation|mutuelle|caisse|banque|compagnie))\s+(" + _SOC_NAME + r")"
    ), 1),
    (re.compile(r"(?:Cabinet|[EÉ]tude|Office)\s+(" + _SOC_NAME + r")"), 1),
]

_STOPWORDS: set[str] = {
    "ENTRE", "ET", "CONTRE", "SUR", "PAR", "POUR", "DANS", "AVEC",
    "ATTENDU", "QUE", "VU", "CONSIDERANT", "ORDONNE", "CONDAMNE",
    "DEBOUTE", "DIT", "JUGE", "DECLARE", "STATUANT", "REJETTE",
    "CONFIRME", "INFIRME", "ANNULE", "CASSE", "RENVOIE",
    "TRIBUNAL", "COUR", "CHAMBRE", "AUDIENCE", "ARRET", "JUGEMENT",
    "DECISION", "ORDONNANCE", "CONCLUSIONS", "BORDEREAU",
    "REPUBLIQUE", "FRANCAISE", "FRANCAIS",
    "ARTICLE", "CODE", "CIVIL", "PENAL", "PROCEDURE", "TRAVAIL", "COMMERCE",
    "PREMIER", "DEUXIEME", "TROISIEME",
    "TITRE", "CHAPITRE", "SECTION", "ALINEA", "PARAGRAPHE",
} | set(_FORMES)


def _is_stopword(text: str) -> bool:
    upper = text.upper().strip()
    if upper in _STOPWORDS:
        return True
    words = upper.split()
    return bool(words) and all(w in _STOPWORDS for w in words)


def find_societes(text: str) -> list[RawMatch]:
    out: list[RawMatch] = []
    for pattern, grp in _SOCIETE_PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(grp)
            if not name or len(name.strip()) < 2 or _is_stopword(name):
                continue
            out.append(RawMatch(
                start=m.start(grp), end=m.end(grp),
                text=name.strip(), category="PERSONNE_MORALE",
            ))
    return out


# ═══════════════════════════════════════════════════════════════════════
#  Noms de personnes
# ═══════════════════════════════════════════════════════════════════════

_CIVILITES = (
    r"Monsieur|Madame|Mme|Mlle|M\.|Me|Ma[iî]tre|Dr|Docteur|Pr|Professeur"
)
_CONTEXTES: list[str] = [
    r"(?:" + _CIVILITES + r")",
    r"(?:le|la|les)\s+(?:requ[ée]rant(?:e)?|d[ée]fendeur(?:esse)?"
    r"|demandeur(?:esse)?|appelant(?:e)?|intim[ée](?:e)?|pr[ée]venu(?:e)?"
    r"|accus[ée](?:e)?|partie\s+civile|partie\s+intervenante"
    r"|assignant(?:e)?|assign[ée](?:e)?)",
    r"(?:consorts|[ée]poux|[ée]pouse|veuve|h[ée]ritiers\s+de"
    r"|aux\s+droits\s+de|repr[ée]sent[ée](?:e)?\s+par|assist[ée](?:e)?\s+de)",
    r"(?:repr[ée]sent[ée]e?\s+par\s+(?:Me|Ma[iî]tre))",
]
_NOM_PART = (
    r"(?:[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+(?:\s+|\-))*[A-ZÀ-ÖØ-ÞŸ][A-ZÀ-ÖØ-ÞŸ'\-]{1,}"
    r"|(?:[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+(?:\s+)){1,3}[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+"
)
_NAME_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?:" + ctx + r")\s+(" + _NOM_PART + r")")
    for ctx in _CONTEXTES
]
_ENTRE_RE = re.compile(
    r"\b(?:ENTRE|Entre)\s*:?\s*\n?\s*"
    r"((?:[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+\s+)*[A-ZÀ-ÖØ-ÞŸ][A-ZÀ-ÖØ-ÞŸ'\-]+)"
)
_FULLCAPS_RE = re.compile(
    r"\b([A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]{1,}(?:\s+[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+)?"
    r"\s+[A-ZÀ-ÖØ-ÞŸ]{2,}(?:[\-\s][A-ZÀ-ÖØ-ÞŸ]{2,})*)\b"
)
_NOT_FIRSTNAME: set[str] = {
    "Code", "Article", "Loi", "Decret", "Arrete", "Ordonnance", "Jugement",
    "Arret", "Decision", "Audience", "Tribunal", "Cour", "Chambre", "Section",
    "Titre", "Chapitre", "Livre", "Partie", "Annexe", "Alinea", "Paragraphe",
    "Monsieur", "Madame", "Maitre", "Docteur", "Professeur",
    "Vu", "Attendu", "Considerant", "Statuant", "Ordonne", "Condamne", "Rejette",
    "Republique", "Francaise", "Etat", "Ministre", "Prefet", "Maire",
    "Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Aout", "Septembre", "Octobre", "Novembre", "Decembre",
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
    "Paris", "Lyon", "Marseille", "Bordeaux", "Lille", "Nice", "Toulouse",
    "Nantes", "Strasbourg", "Rennes", "Montpellier",
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def find_person_names(text: str) -> list[RawMatch]:
    out: list[RawMatch] = []

    # 1. Noms précédés d'une civilité ou d'un rôle procédural
    for pattern in _NAME_PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(1)
            if not name or len(name.strip()) < 2 or _is_stopword(name):
                continue
            out.append(RawMatch(start=m.start(1), end=m.end(1), text=name, category="PERSONNE"))

    # 2. Pattern "ENTRE : Prénom NOM"
    for m in _ENTRE_RE.finditer(text):
        name = m.group(1)
        if not name or len(name.strip()) < 3 or _is_stopword(name):
            continue
        out.append(RawMatch(start=m.start(1), end=m.end(1), text=name, category="PERSONNE"))

    # 3. Séquences Prénom NOM (majuscule mixte)
    for m in _FULLCAPS_RE.finditer(text):
        name = m.group(1)
        if not name or len(name.strip()) < 4 or _is_stopword(name):
            continue
        words = name.split()
        first_lower = next(
            (w for w in words if re.match(r"^[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ]", w)), None
        )
        has_upper = any(re.match(r"^[A-ZÀ-ÖØ-ÞŸ]{2,}(?:[-\s][A-ZÀ-ÖØ-ÞŸ]{2,})*$", w) for w in words)
        if not first_lower or not has_upper:
            continue
        if _strip_accents(first_lower) in _NOT_FIRSTNAME:
            continue
        upper_words = [w for w in words if re.match(r"^[A-ZÀ-ÖØ-ÞŸ]{2,}", w)]
        if upper_words and all(len(w) <= 2 for w in upper_words):
            continue
        out.append(RawMatch(start=m.start(1), end=m.end(1), text=name, category="PERSONNE"))

    return out


# ═══════════════════════════════════════════════════════════════════════
#  Avocats
# ═══════════════════════════════════════════════════════════════════════

_AVOCAT_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(?:Ma[iî]tre|Me)\s+((?:[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+\s+)*[A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ'\-]+)"
    ),
    re.compile(
        r"(?:avocat|avocate|conseil)\s*:?\s*"
        r"((?:[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+\s+)*[A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ'\-]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:repr[ée]sent[ée]e?\s+par\s+)(?:Me|Ma[iî]tre)\s+"
        r"((?:[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+\s+)*[A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ'\-]+)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:inscrite?\s+au\s+)?[Bb]arreau\s+d[e']\s*([A-ZÀ-ÿ][A-Za-zÀ-ÿ\-' ]{1,30})"),
]


def find_avocats(text: str) -> list[RawMatch]:
    out: list[RawMatch] = []
    for pattern in _AVOCAT_PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(1)
            if not name or len(name.strip()) < 2 or _is_stopword(name):
                continue
            out.append(RawMatch(start=m.start(1), end=m.end(1), text=name, category="AVOCAT"))
    return out


# ═══════════════════════════════════════════════════════════════════════
#  Magistrats
# ═══════════════════════════════════════════════════════════════════════

_MAGISTRAT_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(?:Pr[ée]sident(?:e)?|Conseiller(?:[eè]re)?|Juge|Vice-[Pp]r[ée]sident(?:e)?"
        r"|Procureur(?:e)?|Substitut|Greffier(?:[eè]re)?|Premier(?:e)?\s+Pr[ée]sident(?:e)?)"
        r"\s*:?\s*((?:[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+\s+)*[A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ'\-]+)"
    ),
    re.compile(
        r"(?:compos[ée]e?\s+de\s+)(?:(?:Mmes?|Mrs?|MM\.)\s+)?"
        r"((?:[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+\s+)*[A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ'\-]+)"
    ),
]


def find_magistrats(text: str) -> list[RawMatch]:
    out: list[RawMatch] = []
    for pattern in _MAGISTRAT_PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(1)
            if not name or len(name.strip()) < 2 or _is_stopword(name):
                continue
            out.append(RawMatch(start=m.start(1), end=m.end(1), text=name, category="MAGISTRAT"))
    return out


# ═══════════════════════════════════════════════════════════════════════
#  Lieux (naissance, domicile, nationalité)
# ═══════════════════════════════════════════════════════════════════════

_LIEU_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(?:n[ée]{1,2}\s+[àa]\s+)((?:[A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ\-' ]+)(?:\s+\(\d{2,5}\))?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:demeurant\s+[àa]\s+|domicili[ée]e?\s+[àa]\s+|r[ée]sidant\s+[àa]\s+)"
        r"((?:[A-ZÀ-ÖØ-ÞŸ][A-Za-zÀ-ÿ\-' ]+)(?:\s+\(\d{2,5}\))?)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:de\s+nationalit[ée]\s+)([A-Za-zÀ-ÿ]+)", re.IGNORECASE),
]


def find_lieux(text: str) -> list[RawMatch]:
    out: list[RawMatch] = []
    for pattern in _LIEU_PATTERNS:
        for m in pattern.finditer(text):
            lieu = m.group(1)
            if not lieu or len(lieu.strip()) < 2:
                continue
            out.append(RawMatch(start=m.start(1), end=m.end(1), text=lieu.strip(), category="LIEU"))
    return out
