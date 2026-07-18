# Contributing

Thank you for your interest in contributing!

## ⚠️ Licensing & Contributions
This project is licensed under the **AGPL-3.0**. By contributing, you agree that your code will be released under the AGPL-3.0. For commercial licensing, refer to `COMMERCIAL.md`.

## Local Development
1. Fork the repository.
2. Clone your fork locally.
3. Install dependencies (`pip install -e .` or similar).

## Testing
We separate tests into `unit` and `integration`.
- **Unit tests** do NOT require any API keys or database connections.
- **Integration tests** require valid keys.

Run unit tests without API keys using:
```bash
pytest -m "unit"
```
