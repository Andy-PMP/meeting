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

# data (P1)
.\.venv\Scripts\python pipeline\specs.py                # data\specs.jsonl (800, fixed seed; refuses if generations exist)
.\.venv\Scripts\python pipeline\generate.py --dry-run   # prompt preview + cost estimate, no API
.\.venv\Scripts\python pipeline\generate.py --limit 4   # first 4 bundles = 20 invites (costs money)
.\.venv\Scripts\python pipeline\generate.py             # everything not cached (resumes an interrupted batch)
.\.venv\Scripts\python pipeline\generate.py --rebuild   # no API: rebuild invites.jsonl from data\raw
.\.venv\Scripts\python pipeline\sample.py --first 20    # review (-n N random, --all → pipeline\.cache\review.txt, --hints, --cleaned = what the model sees)
.\.venv\Scripts\python pipeline\report.py               # docs\data-report.md: coverage, word counts, spend
.\.venv\Scripts\python pipeline\validate.py             # schema, references, test/train leakage (also in CI)

# labeling + test set (P2)
.\.venv\Scripts\python pipeline\label.py                # one keypress per invite, resumable (1/2/3 d s n u q)
.\.venv\Scripts\python pipeline\label.py --id inv_0042  # redo one
.\.venv\Scripts\python pipeline\label.py --relabel 0.1  # blind 10% second pass (≥5 days later) → Cohen's kappa
.\.venv\Scripts\python pipeline\import_test.py          # data\test\test_invites.txt → test_invites.jsonl (+ dup/leak check)

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
- Generation: 5 specs per request ("bundle" `b0001`…), one invite per spec; invite id mirrors spec id (`spec_0042` → `inv_0042`). `data/raw/` holds every response plus its request hash and is committed, which makes the dataset reproducible without re-calling the API. Prompt changes go in a new `prompts/generate_vN.md` + `PROMPT_VERSION` bump (only changed requests regenerate). Replaced responses move to `data/raw/superseded/` (never deleted), so history and the spend figure stay complete. Current: `generate_v2`, 860 invites (800 main + 60 Zoom-format `spec_0801`… from `specs.all_specs()`, separate seed), $3.69 total. `specs.py` refuses to rewrite specs if any existing spec would change. Never delete `data/raw/_pending.json` while a batch is running: it's how an interrupted run resumes without paying twice.
- Boilerplate: models and similarity checks (dedup, leakage) always read `clean.mask_boilerplate(text)`; people (labeler, review, the site's display) see the original. Masking blanks characters to spaces, so length and offsets are preserved: never change that. Rules live in `pipeline/clean_rules.json`, shared with the future `web/src/lib/clean.ts`: keep them to a Python/JS-compatible regex subset (no inline flags, no lookbehind; Python compiles with `IGNORECASE | ASCII`). Keep `Subject:`/`To:`/`Attendees:`/`When:`/`Date:` lines. They're content.
- Don't show `gen_hint` (the verdict asked of the generator) in labeling or default review output; labels must be blind.
- The test set (`data/test/`) is owner-written and must never be used for training or tuning. `evaluate.py` runs once per frozen model. Its source of truth is `data/test/test_invites.txt` (`=== <label>` blocks, optional `note:` line); `import_test.py` assigns `test_001`… in file order, so new invites go at the end. Rows are exactly `{id, text, label, note}`.
- Labels: `data/labels.jsonl` is append-only (undo may drop the row it just wrote); for the same id and pass, the last row wins. Pass 2 is the blind consistency check.
- Front end: logic in pure, unit-tested modules in `web/src/lib/`; browser-only glue in `web/src/scripts/`; shared chrome in `web/src/layouts/Layout.astro` and `web/src/components/`. Colour tokens live in three blocks in `global.css` (light, dark-by-device, dark-by-toggle), and `contrast.test.ts` enforces WCAG AA on all of them.
- **Never commit or push.** The owner does both (pushing to main deploys the live site). Leave changes in the working tree and suggest a commit message.
