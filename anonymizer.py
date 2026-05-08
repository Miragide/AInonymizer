"""
Port Python de src/lib/anonymizer.ts — pipeline d'anonymisation en 4 passes.
"""
from __future__ import annotations

from dataclasses import dataclass

from juritools import (
    cross_reference_physico_morale,
    find_orthographic_variants,
    flag_doubtful_entities,
    mark_professionals_disabled,
    propagate_multi_occurrences,
    reclassify_dates,
    trim_particles,
)
from pseudo_map import PseudoMap
from regex_fr import (
    RawMatch,
    find_avocats,
    find_juridictions,
    find_lieux,
    find_magistrats,
    find_person_names,
    find_societes,
    find_structured_pii,
)


@dataclass
class Entity:
    start: int
    end: int
    text: str
    category: str
    pseudonym: str
    enabled: bool


# Priorité de déduplication (score plus haut = gagne en cas de chevauchement)
_PRIORITY: dict[str, int] = {
    "DATE_NAISSANCE": 10,
    "AVOCAT": 9, "MAGISTRAT": 9,
    "JURIDICTION": 8,
    "PERSONNE_MORALE": 7, "NUM_DOSSIER": 7,
    "NIR": 6, "IBAN": 6, "SIREN": 6, "PLAQUE": 6,
    "EMAIL": 5, "TEL": 5,
    "ADRESSE": 4, "LIEU": 4,
    "PERSONNE": 3,
    "DATE": 2,
}


def _dedupe(matches: list[RawMatch]) -> list[RawMatch]:
    """Supprime les chevauchements : conserve l'entité la plus prioritaire / la plus longue."""
    sorted_m = sorted(
        matches,
        key=lambda m: (m.start, -_PRIORITY.get(m.category, 0), -(m.end - m.start)),
    )
    result: list[RawMatch] = []
    last_end = -1
    for m in sorted_m:
        if m.start >= last_end:
            result.append(m)
            last_end = m.end
    return result


def analyze(text: str, pseudo_map: PseudoMap) -> list[Entity]:
    """
    Analyse le texte et retourne la liste des entités avec leurs pseudonymes.
    pseudo_map est partagé entre tous les documents du corpus pour garantir
    la cohérence cross-document (même entité → même pseudonyme).
    """
    # ── Passe 1 : détection regex ──────────────────────────────────────
    raw: list[RawMatch] = [
        *find_structured_pii(text),
        *find_juridictions(text),
        *find_societes(text),
        *find_avocats(text),
        *find_magistrats(text),
        *find_person_names(text),
        *find_lieux(text),
    ]

    # ── Passe 2 : post-traitement juritools ───────────────────────────
    raw = reclassify_dates(text, raw)
    raw = flag_doubtful_entities(raw)
    raw = [*raw, *cross_reference_physico_morale(raw)]
    raw = [*raw, *propagate_multi_occurrences(text, raw)]
    raw = [*raw, *find_orthographic_variants(text, raw)]
    raw = trim_particles(text, raw)

    # ── Passe 3 : déduplication ───────────────────────────────────────
    deduped = _dedupe(raw)

    # ── Passe 4 : assignation des pseudonymes ─────────────────────────
    with_status = mark_professionals_disabled(deduped)
    entities = [
        Entity(
            start=m.start, end=m.end,
            text=m.text, category=m.category,
            pseudonym=pseudo_map.assign(m.text, m.category),
            enabled=enabled,
        )
        for m, enabled in with_status
    ]
    entities.sort(key=lambda e: e.start)
    return entities


def apply_pseudonyms(text: str, entities: list[Entity]) -> str:
    """Remplace les entités actives par leurs pseudonymes dans le texte."""
    enabled = sorted((e for e in entities if e.enabled), key=lambda e: e.start)
    parts: list[str] = []
    pos = 0
    for e in enabled:
        if e.start >= pos:
            parts.append(text[pos : e.start])
            parts.append(f"[{e.pseudonym}]")
            pos = e.end
    parts.append(text[pos:])
    return "".join(parts)
