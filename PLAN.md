# Could This Meeting Be an Email? — Build Plan

Read with [BRIEF.md](BRIEF.md) and [TECH_REQUIREMENTS.md](TECH_REQUIREMENTS.md).

**Owner tags:** **[You]** = needs you (judgment, labeling, accounts, pushing) · **[Claude]** = I can do it · **[Both]** = I draft, you decide or edit.
**Convention (from Neighborly):** Claude never commits or pushes. You do both, and pushing to `main` deploys.
**Your time:** about 9–12 hours in total, mostly in P1 (rubric) and P2 (labeling and writing the test set).

---

## P0 — Setup

- [ ] **[You]** Pick the repo name and subdomain (e.g. `meeting-or-email` / `meeting.amandapatricks.com`)
- [ ] **[You]** Create the empty GitHub repo under `Andy-PMP` and add it as `origin`
- [ ] **[You]** Get a Claude API key, set a monthly spend limit (e.g. $20) in the Claude Console, and store the key as a user environment variable:
  ```powershell
  [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
  # then open a new terminal / restart VS Code and check (prints True, not the key):
  [bool]$env:ANTHROPIC_API_KEY
  ```
- [ ] **[Claude]** Repo layout per TECH_REQUIREMENTS §4; `.gitignore` (Neighborly's + `.env*`, `web/public/models/`, `web/public/ort/`)
- [ ] **[Claude]** Python venv and dependencies. Test-install onnxruntime/tokenizers on 3.14 and fall back to 3.13 if needed:
  ```powershell
  py -3.14 -m venv .venv
  .\.venv\Scripts\python -m pip install -r pipeline\requirements.txt
  ```
- [ ] **[Claude]** `pyproject.toml` (ruff + pytest), root `package.json` workspaces, Astro scaffold in `web/` copied from Neighborly (layout, theme toggle, contrast test), Vitest + Playwright config
- [ ] **[Claude]** CI workflows: `pipeline.yml`, `web.yml`, `deploy.yml` (Neighborly's shape)
- [ ] **[Claude]** `CLAUDE.md` (commands, data contract, conventions) and `README.md` (credits/licenses section)

**Done when:** `.\.venv\Scripts\python -m pytest`, `.\.venv\Scripts\ruff check pipeline`, `npm test` and `npm run build` all pass on the skeleton. CI is green on your first push, and `$env:ANTHROPIC_API_KEY` is visible in a new terminal.

---

## P1 — Rubric + data generation

- [ ] **[Claude]** `docs/rubric.md` template: signals, tie-break rules, and slots for 3 examples per class
- [ ] **[You]** Write the rubric (about 1 hour). Give special attention to what separates `shorter` from the other two
- [ ] **[Claude]** Spec grid + seeded sampler → `data/specs.jsonl`; prompt `pipeline/prompts/generate_v1.md`; `generate.py` (Batches, structured output, raw cache, cost report); `dedup.py`; `validate.py`; tests
- [ ] **[Claude]** Dry run of 4 specs × 5 = 20 invites:
  ```powershell
  .\.venv\Scripts\python pipeline\generate.py --limit 4
  .\.venv\Scripts\python pipeline\sample.py -n 20
  ```
- [ ] **[You]** Read the 20 and approve the style, or ask for prompt or spec changes (repeat until it feels right)
- [ ] **[Claude]** Full run (~160 requests → ~800 invites), dedup, validate, distribution report

**Done when:** `data/invites.jsonl` has at least 750 unique invites. The distribution report shows every spec value represented. Actual API cost is logged in `docs/model-report.md`. You've skimmed 30 random invites and approved them.

---

## P2 — Labeling + test set (mostly you)

- [ ] **[Claude]** `label.py` (keys `1/2/3 s d n u q`, resumable, rubric cheat-sheet, `--relabel 0.1`) + tests
- [ ] **[You]** **Write the test set before labeling,** so the generated invites don't shape your writing:
  - about 75 invites by hand (25 per class), in your own voice and varied
  - use realistic but invented names and companies, and label each one as you write it
  - put them in `data/test/test_invites.jsonl`. I can give you a spreadsheet-to-JSONL helper if that's easier
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

- [ ] **[Claude]** `features.py` (tokenizer from `tokenize_spec.json` + structure features), `embed.py` (onnxruntime, mean-pool, chunking), `train.py` with stratified 5-fold CV
- [ ] **[Claude]** Pick the embedding candidate by CV (MiniLM unless bge wins by ≥ 3 macro-F1 points)
- [ ] **[Claude]** Freeze both models, then run `evaluate.py` on the test set once → `data/eval.json`
- [ ] **[Claude]** `docs/model-report.md`: CV and test metrics with CIs, McNemar's test, confusion matrices, sizes, error analysis
- [ ] **[You]** Choose the model to ship. The report recommends one; a statistical tie defaults to the linear model

**Done when:** both models have CV and test metrics with CIs in `eval.json`, the report is written, and you've recorded the shipping model in `CLAUDE.md`.

---

## P4 — Export + in-browser inference

- [ ] **[Claude]** `export.py` → `models/linear.json`, `models/embed_head.json`, `data/fixtures.json`
- [ ] **[Claude]** TypeScript `tokenize`, `features`, `linear`, `explain` in `web/src/lib/` + parity tests against the fixtures
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
- [ ] **[Claude]** Highlight design: 3 accessible class colors plus a non-color cue; a legend; keyboard and screen-reader text for each highlight
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
