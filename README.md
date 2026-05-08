# AInonymizer

Pseudonymiseur local **100 % RGPD** : retirez les données personnelles de vos documents avant de les soumettre à un LLM, sans qu'aucune donnée ne quitte votre machine.

## Pourquoi AInonymizer ?

Les LLM (ChatGPT, Claude, Gemini…) sont de puissants outils d'analyse — mais traiter des données clients, des contrats ou des dossiers RH avec ces services expose votre entreprise aux risques RGPD.

AInonymizer résout ce problème : il pseudonymise automatiquement vos documents **en local**, et vous travaillez ensuite avec l'IA sur la version anonymisée en toute sérénité.

**Cas d'usage typiques :**
- Analyse de contrats, CGV, avenants par un LLM
- Synthèse de dossiers clients ou fiches RH
- Revue de documents médicaux ou assurantiels
- Ingestion de données dans un RAG (Retrieval-Augmented Generation)
- Préparation de tout document contenant des données personnelles avant traitement IA

## Fonctionnement

1. AInonymizer détecte les données personnelles dans vos PDF, DOCX ou Markdown
2. Il les remplace par des pseudonymes cohérents : `[PERSONNE_001]`, `[EMAIL_001]`, `[ADRESSE_002]`…
3. Il génère la table de correspondance pour pouvoir réinjecter les vraies valeurs après traitement IA

La pseudonymisation est **cohérente sur tout le corpus** : la même entité reçoit toujours le même pseudonyme, y compris sur plusieurs documents traités en lot.

### Flux de travail recommandé

```
Documents originaux (contrats, fiches clients…)
        ↓  AInonymizer (local, aucun envoi réseau)
Documents pseudonymisés  ──→  LLM (ChatGPT, Claude…)  ──→  Résultat IA
        ↓                                                         ↓
  mapping.json  ←───────────────────────── Réinjection des vraies valeurs
```

### Données détectées

| Catégorie | Exemples |
|---|---|
| `PERSONNE` | Jean DUPONT, Marie Martin |
| `EMAIL` | jean.martin@exemple.fr |
| `TEL` | 06 12 34 56 78 |
| `NIR` | numéro de sécurité sociale |
| `IBAN` | FR76 3000 6000 ... |
| `SIREN` | 552 032 534 |
| `PLAQUE` | AB-123-CD |
| `DATE_NAISSANCE` | né le 15/03/1985 |
| `ADRESSE` | 12 rue de la Paix 75001 Paris |
| `LIEU` | domicilié à Lyon |
| `PERSONNE_MORALE` | SAS TechCorp, SARL Durand & Fils |
| `AVOCAT` | Maître Sophie DURAND |
| `MAGISTRAT` | Président Martin |
| `JURIDICTION` | Tribunal judiciaire de Paris |
| `NUM_DOSSIER` | RG n°24/05123 |

> Les avocats et magistrats sont détectés mais **désactivés par défaut** (conformité CNIL 01-057) — ils apparaissent dans le mapping mais pas dans le texte pseudonymisé.

## Installation

### Option A — Exécutable Windows (sans Python ni Git)

Téléchargez `ainonymizer.exe` depuis la page [Releases](../../releases), placez-le dans le dossier contenant vos fichiers et double-cliquez.

### Option B — Python

**Prérequis** : Python 3.10+

```bash
pip install -r requirements.txt
```

## Utilisation

1. Placez vos fichiers **PDF, DOCX ou MD** dans le même dossier que `ainonymizer.py` (ou `ainonymizer.exe`)
2. Lancez :

```bash
# Python
python ainonymizer.py

# Exécutable Windows
ainonymizer.exe
```

3. Récupérez les fichiers anonymisés dans le sous-dossier `output/` :

```
output/
  rapport_client_anonymise.md    ← texte pseudonymisé, prêt pour le LLM
  rapport_client_mapping.json    ← table pseudonyme → valeur originale
  corpus_mapping.json            ← table globale du corpus
```

### Exemple de sortie console

```
AInonymizer — 2 fichier(s) trouvé(s)

  rapport_q1.pdf
    12 entités (ADRESSE:1, DATE_NAISSANCE:1, EMAIL:1, IBAN:1, NIR:1, PERSONNE:3, SIREN:1, TEL:1)
  contrat_client.docx
    5 entités (PERSONNE:2, PERSONNE_MORALE:1, ADRESSE:1, DATE:1)

✓ Sortie : output/
  17 entité(s) pseudonymisée(s) au total
  Table globale : corpus_mapping.json
```

### Exemple de texte pseudonymisé

```
[PERSONNE_001] ([PERSONNE_MORALE_001]) a signé le contrat le [DATE_001].
Son adresse de facturation est [ADRESSE_001], email : [EMAIL_001].
Titulaire du compte [IBAN_001], SIREN [SIREN_001].
```

## Tests

```bash
python test_ainonymizer.py
```

## Architecture

```
ainonymizer.py    — point d'entrée : découverte fichiers, orchestration, sortie MD + JSON
anonymizer.py     — pipeline 4 passes (détection → post-traitement → déduplication → pseudonymisation)
regex_fr.py       — patterns regex + checksums (IBAN, NIR, SIREN) pour le français
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
- Détection basée sur des règles (pas de ML) : peut produire des faux positifs sur des termes ambigus
- Optimisé pour les textes en français
