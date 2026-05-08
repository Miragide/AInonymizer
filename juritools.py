"""
Port Python de src/lib/juritools.ts — post-traitement déterministe
inspiré du package juritools de la Cour de cassation.
"""
from __future__ import annotations

import re
import unicodedata

from regex_fr import RawMatch

# ═══════════════════════════════════════════════════════════════════════
#  1. Propagation multi-occurrences
#     Si un texte est détecté comme entité, propager à toutes les
#     occurrences identiques dans le document.
# ═══════════════════════════════════════════════════════════════════════

def propagate_multi_occurrences(text: str, matches: list[RawMatch]) -> list[RawMatch]:
    seen_keys: set[str] = set()
    by_text: dict[str, tuple[str, str]] = {}  # key → (category, original_text)

    for m in matches:
        key = f"{m.category}::{m.text.lower()}"
        if key not in seen_keys:
            seen_keys.add(key)
            by_text[key] = (m.category, m.text)

    existing = {f"{m.start}:{m.end}" for m in matches}
    text_lower = text.lower()
    added: list[RawMatch] = []

    for category, needle in by_text.values():
        needle_lower = needle.lower()
        pos = 0
        while True:
            pos = text_lower.find(needle_lower, pos)
            if pos == -1:
                break
            key = f"{pos}:{pos + len(needle)}"
            if key not in existing:
                existing.add(key)
                added.append(RawMatch(
                    start=pos,
                    end=pos + len(needle),
                    text=text[pos:pos + len(needle)],
                    category=category,
                ))
            pos += 1

    return added


# ═══════════════════════════════════════════════════════════════════════
#  2. Cross-reference physique / morale
#     Extrait les noms de personnes physiques enchâssés dans les noms
#     de personnes morales.
# ═══════════════════════════════════════════════════════════════════════

def cross_reference_physico_morale(matches: list[RawMatch]) -> list[RawMatch]:
    person_names = [
        m.text for m in matches
        if m.category in ("PERSONNE", "AVOCAT", "MAGISTRAT")
    ]
    societes = [m for m in matches if m.category == "PERSONNE_MORALE"]
    added: list[RawMatch] = []

    for soc in societes:
        for name in person_names:
            if len(name) < 3:
                continue
            idx = soc.text.lower().find(name.lower())
            if idx == -1:
                continue
            abs_start = soc.start + idx
            abs_end = abs_start + len(name)
            if abs_start == soc.start and abs_end == soc.end:
                continue
            added.append(RawMatch(
                start=abs_start,
                end=abs_end,
                text=soc.text[idx:idx + len(name)],
                category="PERSONNE",
            ))

    return added


# ═══════════════════════════════════════════════════════════════════════
#  3. Variantes orthographiques (Levenshtein ≤ 2)
#     Détecte les variantes proches des noms déjà identifiés.
# ═══════════════════════════════════════════════════════════════════════

try:
    from rapidfuzz.distance import Levenshtein as _Lev

    def _lev_dist(a: str, b: str) -> int:
        d = _Lev.distance(a, b, score_cutoff=2)
        return d if d is not None else 3
except ImportError:
    def _lev_dist(a: str, b: str) -> int:
        la, lb = len(a), len(b)
        if la == 0:
            return lb
        if lb == 0:
            return la
        if abs(la - lb) > 2:
            return 3
        prev = list(range(lb + 1))
        for i in range(1, la + 1):
            curr = [i] + [0] * lb
            for j in range(1, lb + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
            prev = curr
        return prev[lb]


_CANDIDATE_RE = re.compile(
    r"\b[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+(?:\s+[A-ZÀ-ÖØ-ÞŸ][a-zà-ÿ'\-]+)*\b"
)


def find_orthographic_variants(text: str, matches: list[RawMatch]) -> list[RawMatch]:
    person_names = [m.text for m in matches if m.category == "PERSONNE"]
    if not person_names:
        return []

    unique = list({n.lower() for n in person_names if len(n) >= 4})
    if not unique:
        return []

    # Buckets par longueur pour éviter O(n²) complet
    by_len: dict[int, list[str]] = {}
    for n in unique:
        by_len.setdefault(len(n), []).append(n)

    existing = {f"{m.start}:{m.end}" for m in matches}
    seen: set[str] = set()
    added: list[RawMatch] = []

    for m in _CANDIDATE_RE.finditer(text):
        cand = m.group(0)
        if len(cand) < 4:
            continue
        cand_low = cand.lower()

        matched = False
        for delta in range(-2, 3):
            if matched:
                break
            bucket = by_len.get(len(cand_low) + delta)
            if not bucket:
                continue
            for known in bucket:
                if cand_low == known:
                    matched = True
                    break
                # Rejet rapide : premier caractère doit coïncider
                if cand_low[0] != known[0]:
                    continue
                if 0 < _lev_dist(cand_low, known) <= 2:
                    matched = True
                    break

        if not matched or cand_low in unique:
            continue

        pos_key = f"{m.start()}:{m.end()}"
        if pos_key in existing:
            continue
        dedup = f"{cand_low}::{m.start()}"
        if dedup in seen:
            continue

        seen.add(dedup)
        existing.add(pos_key)
        added.append(RawMatch(start=m.start(), end=m.end(), text=cand, category="PERSONNE"))

    return added


# ═══════════════════════════════════════════════════════════════════════
#  4. Reclassification des dates (procédurales vs sensibles)
# ═══════════════════════════════════════════════════════════════════════

_PROC_CTX = re.compile(
    r"(?:audience\s+du|arr[eê]t\s+du|rendu\s+le|prononc[ée]\s+le"
    r"|pourvoi\s+form[ée]\s+le|signifi[ée]\s+le|notifi[ée]\s+le"
    r"|enregistr[ée]\s+le|d[ée]pos[ée]\s+le|re[çc]u\s+le|dat[ée]\s+du"
    r"|en\s+date\s+du"
    r"|du\s+(?:\d{1,2}\s+)?(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet"
    r"|ao[uû]t|septembre|octobre|novembre|d[ée]cembre))\s*$",
    re.IGNORECASE,
)
_BIRTH_CTX = re.compile(
    r"(?:n[ée]{1,2}\s+le|date\s+de\s+naissance|[âa]g[ée]{1,2}\s+de)\s*$",
    re.IGNORECASE,
)
_DEATH_CTX = re.compile(
    r"(?:d[ée]c[ée]d[ée]{1,2}\s+le|date\s+(?:du\s+)?d[ée]c[èe]s)\s*$",
    re.IGNORECASE,
)


def reclassify_dates(text: str, matches: list[RawMatch]) -> list[RawMatch]:
    result: list[RawMatch] = []
    for m in matches:
        if m.category != "DATE":
            result.append(m)
            continue
        ctx = text[max(0, m.start - 60) : m.start]
        if _BIRTH_CTX.search(ctx) or _DEATH_CTX.search(ctx):
            result.append(RawMatch(m.start, m.end, m.text, "DATE_NAISSANCE"))
        elif _PROC_CTX.search(ctx):
            pass  # date procédurale → supprimée
        else:
            result.append(m)
    return result


# ═══════════════════════════════════════════════════════════════════════
#  5. Entités douteuses (noms trop courts)
# ═══════════════════════════════════════════════════════════════════════

def flag_doubtful_entities(matches: list[RawMatch]) -> list[RawMatch]:
    result: list[RawMatch] = []
    for m in matches:
        if m.category in ("PERSONNE", "AVOCAT", "MAGISTRAT"):
            words = m.text.strip().split()
            if len(words) == 1 and len(words[0]) <= 2:
                continue
        result.append(m)
    return result


# ═══════════════════════════════════════════════════════════════════════
#  6. Distinction professionnels / parties (CNIL 01-057)
#     Avocats et magistrats : détectés mais désactivés par défaut.
# ═══════════════════════════════════════════════════════════════════════

def mark_professionals_disabled(
    matches: list[RawMatch],
) -> list[tuple[RawMatch, bool]]:
    return [(m, m.category not in ("AVOCAT", "MAGISTRAT")) for m in matches]


# ═══════════════════════════════════════════════════════════════════════
#  7. Particules grammaticales
#     Rogne les articles / prépositions / pronoms en tête et en queue
#     des entités détectées.
# ═══════════════════════════════════════════════════════════════════════

_PARTICLES: set[str] = {
    "le", "la", "les", "l", "un", "une", "des",
    "de", "du", "d", "a", "au", "aux",
    "en", "par", "pour", "sur", "sous", "dans",
    "avec", "sans", "chez", "vers", "depuis", "entre",
    "et", "ou", "mais", "ni", "car", "or", "donc",
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "me", "te", "se", "lui", "leur", "y",
    "ce", "cet", "cette", "ces",
    "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
    "notre", "votre", "nos", "vos", "leurs",
    "que", "qui", "quoi", "dont",
}
_STRUCTURED_CATS: set[str] = {
    "EMAIL", "IBAN", "NIR", "SIREN", "TEL", "PLAQUE",
    "NUM_DOSSIER", "DATE", "DATE_NAISSANCE",
}
_HEAD_RE = re.compile(r"^([A-Za-zÀ-ÿ]+['’]?)[\s,]+")
_TAIL_RE = re.compile(r"[\s,]+([A-Za-zÀ-ÿ]+['’]?)$")


def _is_particle(word: str) -> bool:
    cleaned = word.replace("'", "").replace("’", "").strip()
    if not cleaned:
        return False
    norm = "".join(
        c for c in unicodedata.normalize("NFD", cleaned.lower())
        if unicodedata.category(c) != "Mn"
    )
    return norm in _PARTICLES


def trim_particles(text: str, matches: list[RawMatch]) -> list[RawMatch]:
    result: list[RawMatch] = []

    for m in matches:
        if m.category in _STRUCTURED_CATS:
            result.append(m)
            continue

        start, end = m.start, m.end
        current = text[start:end]

        # Rognage en tête
        changed = True
        while changed and start < end:
            changed = False
            head = _HEAD_RE.match(current)
            if head and _is_particle(head.group(1)):
                start += len(head.group(0))
                current = text[start:end]
                changed = True

        # Rognage en queue
        changed = True
        while changed and start < end:
            changed = False
            tail = _TAIL_RE.search(current)
            if tail and _is_particle(tail.group(1)):
                end -= len(tail.group(0))
                current = text[start:end]
                changed = True

        trimmed = current.strip()
        if not trimmed or len(trimmed) < 2:
            continue
        if " " not in trimmed and _is_particle(trimmed):
            continue

        lead = len(current) - len(current.lstrip())
        trail = len(current) - len(current.rstrip())
        result.append(RawMatch(
            start=start + lead,
            end=end - trail,
            text=trimmed,
            category=m.category,
        ))

    return result
