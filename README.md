# Invoice Extraction System

A privacy-first rebuild of the Invoice Extraction System (IES). The pipeline is
template-independent and deliberately limits the role of the local Qwen model:

```text
validated document
  -> page rendering and preprocessing
  -> PaddleOCR with coordinates/confidence
  -> layout reconstruction
  -> deterministic normalization and correction
  -> field candidates and compact evidence
  -> Qwen schema mapping only
  -> arithmetic/business validation and confidence scoring
```

FastParser is not part of this architecture. Real invoices, OCR output, extracted
records, credentials, logs, databases, and model weights are excluded from Git.

## Development

Python 3.10-3.12 is supported. The machine currently has Python 3.10.11; Ollama
must be installed separately before the local mapping stage can run. For this
16 GB RAM, CPU-first machine, the default is the compact non-thinking
`qwen3:4b-instruct-2507-q4_K_M` model. The model receives only bounded candidate
evidence and uses a 4K runtime context, despite supporting a much larger maximum.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

Install the heavier OCR dependencies only on a machine that will run PaddleOCR:

```powershell
python -m pip install -e ".[ocr,dev]"
```

## Confidential GitHub workflow

1. Create a **private** repository with no generated starter files.
2. Commit source code and sanitized synthetic fixtures only.
3. Connect the local repository using SSH or GitHub CLI.
4. Enable secret scanning, dependency alerts, and branch protection.
5. Keep real runtime data outside this repository and back it up separately with encryption.

`.gitignore` is a guardrail, not a security boundary. Before every push, inspect
`git status` and the staged diff. Never commit real invoice samples, even briefly;
removing them in a later commit does not remove them from Git history.
