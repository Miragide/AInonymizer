# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run tests (no external dependencies beyond the project's own)
python test_ainonymizer.py

# Run AInonymizer on all PDF/DOCX/MD files in input/
python ainonymizer.py

# Install dependencies
pip install -r requirements.txt

# Build Windows executable
python -m PyInstaller --onefile --name ainonymizer ainonymizer.py
```

## Architecture

**AInonymizer** is a local, rule-based pseudonymizer for French-language documents containing RGPD-sensitive data. It processes PDF, DOCX, and Markdown files through a 4-pass pipeline and outputs anonymized Markdown + JSON mapping files, ready for LLM consumption.

### Pipeline (anonymizer.py)

Four passes in sequence:

1. **Regex detection** (`regex_fr.py`) — finds PII using compiled patterns + checksums (Luhn for SIREN, mod-97 for IBAN, key validation for NIR)
2. **Post-processing** (`juritools.py`) — reclassifies dates (procedural vs. birth/death), propagates multi-occurrences, finds orthographic variants (Levenshtein ≤ 2), trims particles, cross-references physical/legal persons
3. **Deduplication** (`anonymizer.py:_dedupe`) — resolves overlaps by priority score + span length
4. **Pseudonym assignment** (`pseudo_map.py`) — maps normalized text → `CATEGORY_NNN`, consistent across the whole corpus

### Key design decisions

- **`PseudoMap`** is shared across all documents in a run, guaranteeing cross-document consistency (same entity → same pseudonym).
- Avocats and magistrats are detected but **disabled by default** (`enabled=False`) per CNIL deliberation 01-057 — they appear in the mapping JSON but are not replaced in the output text.
- `ainonymizer.py` scans the `input/` subdirectory for files to process (non-recursive). When bundled with PyInstaller (`sys.frozen`), it uses `sys.executable` to locate the root directory instead of `__file__`. Both `input/` and `output/` are gitignored (content only) — they may contain real PII.
- The `output/` directory is gitignored — it may contain real PII from production use.
- The `input/` directory is gitignored (contents only, `.gitkeep` tracked) — drop documents to process there.

### Module responsibilities

| File | Role |
|---|---|
| `ainonymizer.py` | Entry point: file discovery, orchestration, Markdown + JSON output |
| `anonymizer.py` | Pipeline orchestration, `Entity` dataclass, deduplication |
| `regex_fr.py` | All regex patterns and checksum validators; defines `RawMatch` |
| `juritools.py` | Deterministic post-processing passes |
| `pseudo_map.py` | Cross-document pseudonym table |
| `extractor.py` | Text extraction from PDF (MuPDF/fitz), DOCX (python-docx), MD |

### Adding a new PII category

1. Add detection logic in `regex_fr.py` (new pattern in `_STRUCTURED` or a new `find_*` function)
2. Export the new function and call it in `anonymizer.py:analyze()`
3. Add the priority score to `_PRIORITY` in `anonymizer.py`
4. Add a test case in `test_ainonymizer.py`
