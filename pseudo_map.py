from __future__ import annotations


class PseudoMap:
    """Table de correspondance pseudonyme ↔ texte original, cohérente sur tout le corpus."""

    def __init__(self) -> None:
        self._norm_to_pseudo: dict[str, str] = {}   # texte normalisé → pseudonyme
        self._pseudo_to_orig: dict[str, str] = {}   # pseudonyme → texte original
        self._counters: dict[str, int] = {}

    # ── Public ──────────────────────────────────────────────────────────

    def assign(self, text: str, category: str) -> str:
        """Retourne le pseudonyme pour text/category, en le créant si nécessaire."""
        key = self._normalize(text)
        if key in self._norm_to_pseudo:
            return self._norm_to_pseudo[key]
        n = self._counters.get(category, 0) + 1
        self._counters[category] = n
        pseudo = f"{category}_{n:03d}"
        self._norm_to_pseudo[key] = pseudo
        self._pseudo_to_orig[pseudo] = text
        return pseudo

    def to_dict(self) -> dict[str, str]:
        """Retourne {pseudonyme: texte_original} pour export JSON."""
        return dict(self._pseudo_to_orig)

    # ── Internal ─────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().split())
