# Could This Meeting Be an Email?

Browser-only text classifier for the portfolio: paste a meeting invite, get **Keep the meeting / Make it shorter / This is an email** with the phrases that drove the score highlighted. Brief: [BRIEF.md](BRIEF.md). Design: [TECH_REQUIREMENTS.md](TECH_REQUIREMENTS.md). Phases and gates: [PLAN.md](PLAN.md) (keep its checkboxes current).

## Decisions
- Stack copied from Neighborly (`..\nearby`): Astro 7 + TypeScript, no UI framework, Vitest; Python venv for data/training. Plus Playwright + axe for e2e/privacy/a11y.
- Live at **https://meeting.amandapatricks.com**: GitHub repo `Andy-PMP/meeting`, Pages source "GitHub Actions", Namecheap CNAME `meeting` → `andy-pmp.github.io`, HTTPS on. `.github/workflows/deploy.yml` deploys `web/dist` on every push to main, gated on Vitest + build + Playwright. No `base` (subdomain root).
- Labels, in this fixed order everywhere (weight-matrix rows): `keep`, `shorter`, `email` (`pipeline/labels.py`).
- Generation: Claude API (`claude-opus-5-5`, Message Batches, structured outputs). Key only from the `ANTHROPIC_API_KEY` user env var; never read from or written to files, never logged. The installed SDK is **anthropic 2.x**: check its current API before writing `generate.py` rather than relying on older patterns.
- Privacy: no request may leave the origin. Enforced by the CSP in `web/astro.config.mjs` (`security.csp`, Astro hashes inline scripts/styles: never add `'unsafe-inline'`, inline `style=` attributes or external URLs) and by `web/e2e/privacy.spec.ts`. Pasted text is never stored, put in a URL, or included in share text. Only `meeting:theme` goes to localStorage.
- Python 3.14 venv works with every ML dependency (onnxruntime 1.31 checked in P0).

## Environment
Windows 11. **Use PowerShell syntax for every command.** Python venv at `.venv` (Python 3.14).

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -r pipeline\requirements.txt
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff check pipeline
.\.venv\Scripts\ruff format --check pipeline

# web (run from the repo root; npm workspaces forward to web/)
npm install                                   # once
npx -w web playwright install chromium        # once, for e2e
npm run dev          # http://localhost:4321/
npm test             # Vitest
npm run build        # astro check + static build into web\dist
npm run e2e          # Playwright against web\dist (build first), served on :4322
npm run preview      # serve web\dist at http://localhost:4321/
```
Windows PowerShell 5.1 drops `--` when passing args through npm, so run e.g. `npx -w web astro preview --port X` directly.

## Conventions
- Pipeline scripts run as `python pipeline\<script>.py` and import each other as top-level modules (`from paths import ...`). Shared paths live in `pipeline/paths.py`.
- Never hand-edit generated files in `data/` or `models/`; rerun the script.
- The test set (`data/test/`) is owner-written and must never be used for training or tuning. `evaluate.py` runs once per frozen model.
- Front end: logic in pure, unit-tested modules in `web/src/lib/`; browser-only glue in `web/src/scripts/`; shared chrome in `web/src/layouts/Layout.astro` and `web/src/components/`. Colour tokens live in three blocks in `global.css` (light, dark-by-device, dark-by-toggle), and `contrast.test.ts` enforces WCAG AA on all of them.
- **Never commit or push.** The owner does both (pushing to main deploys the live site). Leave changes in the working tree and suggest a commit message.
