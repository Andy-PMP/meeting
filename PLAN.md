# Could This Meeting Be an Email? — Build Plan

Read with [BRIEF.md](BRIEF.md) and [TECH_REQUIREMENTS.md](TECH_REQUIREMENTS.md).

**Owner tags:** **[You]** = needs you (judgment, labeling, accounts, pushing) · **[Claude]** = I can do it · **[Both]** = I draft, you decide or edit.
**Convention (from Neighborly):** Claude never commits or pushes. You do both, and pushing to `main` deploys.
**Your time:** about 9–12 hours in total, mostly in P1 (rubric) and P2 (labeling and writing the test set).

---

## P0 — Setup

- [x] **[You]** Pick the repo name and subdomain: `Andy-PMP/meeting` / `meeting.amandapatricks.com`
- [x] **[You]** Create the empty GitHub repo under `Andy-PMP` and add it as `origin`
- [x] **[You]** Done early: Pages source = GitHub Actions, CNAME, HTTPS (the P7 deploy steps)
- [x] **[You]** Get a Claude API key, set a monthly spend limit (e.g. $20) in the Claude Console, and store the key as a user environment variable:
  ```powershell
  [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
  # then open a new terminal / restart VS Code and check (prints True, not the key):
  [bool]$env:ANTHROPIC_API_KEY
  ```
- [x] **[Claude]** Repo layout per TECH_REQUIREMENTS §4; `.gitignore` (Neighborly's + `.env*`, `web/public/models/`, `web/public/ort/`)
- [x] **[Claude]** Python venv and dependencies. All install on 3.14 (onnxruntime 1.31, anthropic 2.0), so no fallback is needed:
  ```powershell
  py -3.14 -m venv .venv
  .\.venv\Scripts\python -m pip install -r pipeline\requirements.txt
  ```
- [x] **[Claude]** `pyproject.toml` (ruff + pytest), root `package.json` workspaces, Astro scaffold in `web/` copied from Neighborly (layout, theme toggle, contrast test), Vitest + Playwright config
- [x] **[Claude]** Strict CSP via Astro `security.csp` + Playwright privacy/axe test (checked by injecting an external image: the test fails as it should)
- [x] **[Claude]** CI workflows: `pipeline.yml`, `web.yml`, `deploy.yml` (Neighborly's shape; deploy also gated on Playwright)
- [x] **[Claude]** `CLAUDE.md` (commands, conventions) and `README.md` (credits/licenses section)
- [ ] **[You]** Commit and push; check that all three workflows go green and the placeholder page loads on the subdomain

**Done when:** `.\.venv\Scripts\python -m pytest`, `.\.venv\Scripts\ruff check pipeline`, `npm test` and `npm run build` all pass on the skeleton. CI is green on your first push, and `$env:ANTHROPIC_API_KEY` is visible in a new terminal.

---

## P1 — Rubric + data generation

- [x] **[Claude]** `docs/rubric.md` template: signals, tie-break rules, and slots for 3 examples per class
- [ ] **[You]** Write the rubric (about 1 hour). Give special attention to what separates `shorter` from the other two
- [x] **[Claude]** Spec grid + seeded sampler → `data/specs.jsonl`; prompt `pipeline/prompts/generate_v1.md`; `generate.py` (Batches, structured output, raw cache, cost report); `dedup.py`; `validate.py`; `sample.py`; `report.py`; tests (34)
- [x] **[Claude]** Dry run of 4 requests × 5 = 20 invites ($0.08, all valid):
  ```powershell
  .\.venv\Scripts\python pipeline\generate.py --limit 4
  .\.venv\Scripts\python pipeline\sample.py -n 20
  ```
- [x] **[You]** Read the 20 in `pipeline\.cache\review.txt` and approve the style
- [x] **[Claude]** From my own review: a per-spec random cast of names + project/client name (the model reuses favorites like "Priya", "Halvorsen"), and sector-appropriate org names → prompt `generate_v2`
- [x] **[Claude]** Full run: 160 requests → 800 invites, 0 duplicates, 0 validation errors, every spec value represented (`docs/data-report.md`). One response came back with 1 of 5 invites; validation caught it and the automatic retry fixed it. **Total API spend $3.36** (165 requests including the trial; replaced responses kept in `data/raw/superseded/`)
- [x] **[You]** Skim the 30 random invites in `pipeline\.cache\review30.txt` (hints hidden) and approve
- [x] **[You]** Finish `docs/rubric.md`. Ready for labeling

**P1 complete.**

**Done when:** `data/invites.jsonl` has at least 750 unique invites. The distribution report shows every spec value represented. Actual API cost is logged in `docs/data-report.md`. You've skimmed 30 random invites and approved them.

---

## P2 — Labeling + test set (mostly you)

- [x] **[Claude]** `label.py` (keys `1/2/3 s d n u q`, resumable, rubric cheat-sheet, running label mix + time left, `--id`, `--relabel 0.1` with kappa) + `import_test.py` (write test invites as plain text) + tests (49 total)
- [x] **[Claude]** Boilerplate masking (`clean.py` + shared `clean_rules.json`): join blocks, dial-ins, passcodes, links and forward headers are blanked, length-preserving, before every similarity check (dedup, leakage) and later every model. Checked on all 800 invites (311 affected, no false positives among masked lines; dataset unchanged). `sample.py --cleaned`, report section, tests (60 total)
- [x] **[Claude]** Zoom supplement: 60 Zoom-format invites (`spec_0801`–`0860`, start time only, no attendee list), since Zoom invites state no duration and the main set barely covered Zoom. Main 800 specs byte-identical; $0.33 → **total spend $3.69, 860 invites**. Masking rules extended for Zoom (invitation line, local numbers, SIP/H.323, room addresses), Outlook "Original Message/Appointment" separators, and, from your real-format test invites, Google Calendar invite emails, Webex and new-Teams wording; 0 leftovers, 0 false positives (69 tests)
- [x] **[You]** Rubric: working sessions, and skip the duration/attendee rows when an invite doesn't say
- [x] **[You]** **Write the test set before labeling,** so the generated invites don't shape your writing. Done: **67 invites (25 keep / 17 shorter / 25 email)**, real-world formats (Outlook, Google Calendar emails, Zoom, Webex, Slack), mirrored pairs across labels, rule cases tagged `rule`, traps tagged `trap`; imported, 0 duplicates, 0 leaks:
  - about 75 invites by hand (25 per class), in your own voice and varied
  - use realistic but invented names and companies, and label each one as you write it
  - write them in `data/test/test_invites.txt` (`=== keep` header, optional `note:` line, then the invite), then run `.\.venv\Scripts\python pipeline\import_test.py`
- [ ] **[You]** Label ~600 invites in sessions of ~100 (about 5 hours total):
  ```powershell
  .\.venv\Scripts\python pipeline\label.py
  ```
- [ ] **[You]** At least 5 days after finishing, run the blind relabel pass:
  ```powershell
  .\.venv\Scripts\python pipeline\label.py --relabel 0.1
  ```
- [ ] **[Claude]** Validate: class balance, leakage check (no test near-duplicate in train), Cohen's kappa

**Done when:**
- at least 550 labeled, non-discarded training invites, with each class at 20% or more
- at least 60 test invites, with at least 15 per class
- the leakage check passes
- kappa is at least 0.7 (if it's lower, we revise the rubric together and you relabel only the disagreements)

---

## P3 — Train and compare models

- [x] **[Claude]** `features.py` (tokenizer + structure features with explicit "unknown" buckets, from `features_spec.json`), `embed.py` (pinned quantized ONNX via onnxruntime; MiniLM mean-pool, BGE CLS-pool; 256/512-token windows averaged), `train.py` with repeated stratified 5-fold CV (3 shuffles). All read `mask_boilerplate(text)`. 109 tests
- [x] **[Claude]** Pick the embedding candidate by CV → **MiniLM** (0.548 vs BGE 0.530 macro-F1). CV so far: **linear 0.591** (acc 60.6%) beats MiniLM by ~4 points; structure features add +2.8 (linear) / +5.8 (MiniLM). Shorter is hardest (F1 0.52). See `docs/model-report.md`
- [ ] **[You]** Blind relabel pass on or after 31 Oct (`label.py --relabel 0.1`) → kappa. If < 0.7, review the disagreements and retrain (seconds)
- [ ] **[Claude]** Freeze both models, then run `evaluate.py` on the test set once → `data/eval.json`
- [ ] **[Claude]** Boilerplate-invariance check: append Zoom/Meet/Webex/Teams blocks to every test invite and report the prediction flip rate with and without masking
- [ ] **[Claude]** `docs/model-report.md`: CV and test metrics with CIs, McNemar's test, confusion matrices, sizes, error analysis
- [ ] **[You]** Choose the model to ship. The report recommends one; a statistical tie defaults to the linear model

**Done when:** both models have CV and test metrics with CIs in `eval.json`, the report is written, and you've recorded the shipping model in `CLAUDE.md`.

---

## P4 — Export + in-browser inference

- [ ] **[Claude]** `export.py` → `models/linear.json`, `models/embed_head.json`, `data/fixtures.json`
- [ ] **[Claude]** TypeScript `clean`, `tokenize`, `features`, `linear`, `explain` in `web/src/lib/` + parity tests against the fixtures (masking must match Python character for character)
- [ ] **[Claude]** If the embedding model ships, do these first to retire the riskiest unknowns:
  - `fetch-model.mjs` (pinned revision + sha256), self-hosted ONNX and wasm
  - Transformers.js in a worker, with the CSP from TECH_REQUIREMENTS §6
  - a bare test page proving it all works
  - occlusion explanations
- [ ] **[Claude]** Measure bundle sizes and cold/warm latency against TECH_REQUIREMENTS §7

**Done when:**
- parity tests pass in CI
- the bare page classifies correctly with the network turned off after the first load (DevTools → Offline)
- every §7 size and latency target is met, or a gap is written down along with your OK to accept it

---

## P5 — Web UI with highlights

- [ ] **[Claude]** Main page: textarea, Rate it, verdict + probability bar, highlighted invite, reasons, Try an example, Share verdict, privacy banner
- [ ] **[Claude]** Highlight design: 3 accessible class colors plus a non-color cue; a legend; keyboard and screen-reader text for each highlight; masked boilerplate shown dimmed ("ignored: dial-in details")
- [ ] **[Both]** Copy: verdict lines, reason templates, the ~8 sample invites (I draft, you edit for voice)
- [ ] **[Claude]** Playwright end-to-end + **privacy test** + axe scan in CI
- [ ] **[You]** Play-test with 10 of your own (invented or anonymized) invites:
  ```powershell
  npm run dev    # http://localhost:4321/
  ```

**Done when:** Playwright end-to-end, privacy and axe tests are green in CI, and you've signed off on tone and on how the highlights look in light and dark mode.

---

## P6 — Eval page + case study

- [ ] **[Claude]** `/how-it-was-built/eval/` generated from `eval.json`: metrics, confusion-matrix SVG, model comparison, kappa, data card, mistakes gallery
- [ ] **[You]** Pick 6–10 funny mistakes (add their IDs to `pipeline\featured_mistakes.txt`)
- [ ] **[Claude]** Draft `docs/case-study.md`: problem → rubric → data → labeling → models → evaluation → privacy-first deployment → limitations → next steps
- [ ] **[You]** Edit the case study in your voice. Add the project-management angle (scoping, the rubric as acceptance criteria, phase gates)

**Done when:** both pages render from committed data with no hand-typed numbers, and you've approved the final text.

---

## P7 — Polish, accessibility, deploy

- [ ] **[Claude]**
  - accessibility: axe clean on all pages, keyboard-only pass, 320 px layout, reduced motion, contrast test across themes
  - meta: favicon, OG image + tags, 404 page
  - checks: Lighthouse run against the §7 targets, README credits and licenses
- [ ] **[Claude]** Portfolio entry text for the `amandapatricks.com` repo (`src/content/projects/<name>.md`, same format as `neighborly.md`)
- [ ] **[You]** Screen-reader check (NVDA or Narrator) and a real phone check
- [ ] **[You]** Deploy:
  - GitHub repo → Settings → Pages → Source: **GitHub Actions**
  - Namecheap: add a CNAME record `<subdomain>` → `andy-pmp.github.io`
  - Pages → Custom domain → `<subdomain>.amandapatricks.com`, then tick **Enforce HTTPS** once the certificate is ready
  - push to `main`, then add and push the portfolio entry

**Done when:** the site is live over HTTPS on the subdomain, the privacy test and Lighthouse targets pass against the live URL, and the portfolio links to it.
