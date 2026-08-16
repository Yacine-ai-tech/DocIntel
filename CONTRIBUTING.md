# Contributing

Thank you for your interest in contributing!

## ⚠️ Licensing & Contributions
This project is licensed under the **AGPL-3.0**. By contributing, you agree that your code will be released under the AGPL-3.0. For commercial licensing, refer to `COMMERCIAL.md`.

## Local Development
1. Fork the repository.
2. Clone your fork locally.
3. `python -m venv .venv && source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `cp .env.example .env` and fill in the keys for whichever routes you're working on.

## Testing
Most of the test suite (`tests/test_smoke.py`, `test_normalize.py`, `test_currency.py`,
`test_doc_merge.py`, `test_multipage.py`, `test_security_fixes.py`, `test_ai_pipeline_fixes.py`,
etc.) runs fully in-process against the FastAPI app object — no API keys or live services
required:

```bash
pytest tests/ -q --ignore=tests/test_exhaustive_api.py
```

`tests/test_exhaustive_api.py` is the exception: it's written to optionally run against a real
deployed instance via `TEST_BASE_URL` (see the module docstring), and is excluded above for that
reason — it still runs fine in-process with no env vars set, just against the app object
directly rather than a live URL.
