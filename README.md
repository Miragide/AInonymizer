# Siegfried — Pseudonymiseur local de documents juridiques

Outil de pseudonymisation **100 % local** pour les documents juridiques français (PDF, DOCX, Markdown). Aucune donnée ne quitte votre machine.

## Fonctionnement

Siegfried détecte et remplace automatiquement les données personnelles par des pseudonymes cohérents (`[PERSONNE_001]`, `[ADRESSE_002]`, etc.) sur l'ensemble d'un corpus.

### Catégories détectées

| Catégorie | Exemples |
|---|---|
| `PERSONNE` | Monsieur Jean DUPONT |
| `AVOCAT` | Maître Sophie DURAND |
| `MAGISTRAT` | Président Martin |
| `PERSONNE_MORALE` | SAS TechCorp |
| `JURIDICTION` | Tribunal judiciaire de Paris |
| `EMAIL` | jean.martin@exemple.fr |
| `TEL` | 06 12 34 56 78 |
| `NIR` | numéro de sécurité sociale |
| `IBAN` | FR76 3000 6000 ... |
| `SIREN` | 552 032 534 |
| `PLAQUE` | AB-123-CD |
| `DATE_NAISSANCE` | né le 15/03/1985 |
| `ADRESSE` | 12 rue de la Paix 75001 Paris |
| `LIEU` | domicilié à Lyon |
| `NUM_DOSSIER` | RG n°24/05123 |

Les avocats et magistrats sont détectés mais **désactivés par défaut** (conformité CNIL 01-057).

## Installation

### Option A — Exécutable Windows (pas besoin de Python)

Téléchargez `siegfried.exe` depuis la page [Releases](../../releases) et placez-le dans le dossier contenant vos fichiers.

### Option B — Python

**Prérequis** : Python 3.10+

```bash
pip install -r requirements.txt
```

## Utilisation

1. Placez vos fichiers **PDF, DOCX ou MD** dans le même dossier que `siegfried.py` (ou `siegfried.exe`)
2. Lancez :

```bash
# Python
python siegfried.py

# Exécutable Windows
siegfried.exe
```

3. Les résultats apparaissent dans le sous-dossier `output/` :

```
output/
  mon_document_anonymise.md   ← texte pseudonymisé (format LLM-friendly)
  mon_document_mapping.json   ← table pseudonyme → valeur originale
  corpus_mapping.json         ← table globale du corpus
```

### Exemple de sortie

```
Siegfried — 2 fichier(s) trouvé(s)

  jugement.pdf
    12 entités (ADRESSE:1, DATE_NAISSANCE:1, EMAIL:1, IBAN:1, NIR:1, PERSONNE:3, SIREN:1, TEL:1)
  contrat.docx
    5 entités (PERSONNE:2, PERSONNE_MORALE:1, ADRESSE:1, DATE:1)

✓ Sortie : C:\...\output\
  17 entité(s) pseudonymisée(s) au total
  Table globale : corpus_mapping.json
```

Le texte pseudonymisé ressemble à :

```
[PERSONNE_001] a assigné [PERSONNE_002] devant le Tribunal judiciaire de Paris
le 10/01/2024. Représenté par [AVOCAT_001], barreau de Paris.
```

## Tests

```bash
python test_siegfried.py
```

## Architecture

```
siegfried.py      — point d'entrée, orchestration
anonymizer.py     — pipeline 4 passes (détection → post-traitement → déduplication → pseudonymisation)
regex_fr.py       — expressions régulières + checksums (IBAN, NIR, SIREN)
juritools.py      — post-traitements déterministes (propagation, variantes, reclassification dates)
pseudo_map.py     — table de correspondance cohérente sur tout le corpus
extractor.py      — extraction texte (PDF via MuPDF, DOCX via python-docx)
```

## Dépendances

- [pymupdf](https://pymupdf.readthedocs.io/) — lecture PDF (MuPDF, sans OCR)
- [python-docx](https://python-docx.readthedocs.io/) — lecture DOCX
- [rapidfuzz](https://github.com/maxbachmann/RapidFuzz) — distance de Levenshtein (variantes orthographiques)

## Limitations

- PDF scannés (images) non supportés — le texte doit être sélectionnable
- Détection basée sur des règles (pas de ML) : peut produire des faux positifs ou manquer des entités atypiques
- Optimisé pour les documents juridiques français
