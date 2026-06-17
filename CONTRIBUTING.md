# Contributing to DocIntel

Thanks for your interest! This is part of a 6-project portfolio by Yacine Seybou Siddo.

## Development setup
```bash
git clone https://github.com/Yacine-ai-tech/DocIntel.git && cd DocIntel
cp .env.example .env            # fill in keys (never commit .env)
pip install -r requirements.txt
pytest                          # run the test suite
uvicorn api:app --reload --port 8001                        # run locally
```
Or with Docker: `docker compose -f docker-compose.dev.yml up --build`.

## Workflow
- Branch off **`develop`** (the active branch); open PRs against `develop`.
- `master` is the released/default branch — it tracks `develop` once CI is green.
- Keep changes focused; match the surrounding code style.
- **Add/keep tests passing** — CI (GitHub Actions, `.github/workflows/ci.yml`) runs `pytest` on every push/PR and must be green.
- Never commit secrets (`.env`, keys). `.env.example` documents the required variables.

## Reporting issues
Open a GitHub issue with steps to reproduce, expected vs actual behavior, and environment details.

## License
By contributing you agree your contributions are licensed under the project's [MIT License](LICENSE).
