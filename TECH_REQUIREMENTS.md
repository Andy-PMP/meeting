# Could This Meeting Be an Email? — Technical Requirements

Companion to [BRIEF.md](BRIEF.md) and [PLAN.md](PLAN.md). This doc answers the brief's open questions and is the reference for building the project.

## Decisions at a glance

| Question | Decision |
|---|---|
| Hosting | Own subdomain (name chosen in P0, e.g. `meeting.amandapatricks.com`), new GitHub repo, same setup as Neighborly: Astro + TypeScript, GitHub Pages "Actions" source, Namecheap CNAME, entry in the portfolio repo |
| Labels | `keep` (Keep the meeting) · `shorter` (Make it shorter) · `email` (This is an email) |
| Dataset | ~800 Claude-generated invites → ~600 owner-labeled for training · ~75 owner-written test invites |
| Generator | `claude-opus-5-5`, effort `low`, structured JSON output, Message Batches API (50% off), about $5 total |
| Baseline | Shared regex tokenizer → TF-IDF word 1–2-grams + binned "structure" features → multinomial logistic regression |
| Embedding model | `all-MiniLM-L6-v2` (Apache-2.0, ~23 MB quantized) vs `bge-small-en-v1.5` (MIT, ~34 MB) + logistic regression head |
| Explanations | Linear model: exact per-phrase weight contributions. Embedding model: occlusion (remove each line or clause, measure the score change) |
| Export | Linear model as JSON (no ML runtime in the browser). Embedding model as a pinned, self-hosted ONNX file run with Transformers.js, plus the head as JSON |
| Model choice | Ship the model with the higher test macro-F1. If the difference isn't statistically meaningful, call it a tie publicly and ship the smaller linear model by default |
| Privacy | All inference runs on-device in a Web Worker. Every asset is self-hosted. A CSP blocks any outbound connection, and an automated test enforces it |

## Data flow

```
specs (seeded) → generate (Claude Batches, cached) → dedup → label (CLI) ─┐
                                        owner-written test set ─────────────┤
                                                                            ▼
                     train (5-fold CV on train only) → evaluate (test set, once) → export → web app
                                                                            └→ eval.json → eval page
```

## 1. Components

### 1.1 Data generation — `pipeline/generate.py`

- **Spec grid.** Each invite comes from a spec sampled with a fixed seed. Dimensions:
  - meeting type (status sync, decision, brainstorm, 1:1, kickoff, retro, all-hands, "quick chat", vendor demo, …)
  - industry or org type
  - tone (corporate, casual, passive-aggressive, overly enthusiastic)
  - length (one line, short, long)
  - vagueness (clear agenda / fuzzy / none)
  - attendee bucket (1–3, 4–8, 9–20, 20+) and duration (15/30/45/60/90/120 min)
  - messiness: typos, forwarded chains, emoji, ALL CAPS, pasted calendar boilerplate, dial-in junk, bullet soup
  - `gen_hint`: the label "flavor" we ask for, used only to keep the classes roughly balanced
- **`gen_hint` is never a training label.** You label everything blind. The eval page reports, as a curiosity, how often your label matched the hint.
- **Prompt.** Versioned template at `pipeline/prompts/generate_v1.md`. Changing it means creating `_v2`. Each call carries 5 different specs and returns one invite per spec, as JSON through structured outputs (`output_config.format`). Every invite keeps exact metadata, and the model varies the 5 against each other.
- **Model and cost.**
  - `claude-opus-5-5` at effort `low`, sent via the Message Batches API (50% off).
  - Opus 5.5 doesn't accept `temperature`, so variety comes from the specs and not from sampling randomness. That is better for reproducibility anyway.
  - Estimate: ~160 requests, about $5. `claude-haiku-5-5` would cost about 1/40th as much if you'd rather. That's your call; Opus is the default because invite quality matters.
- **Reproducibility.** Raw API responses are cached in `data/raw/<bundle_id>.json` and committed, along with the hash of the exact request. Re-running the script never calls the API for specs that already have a cached response. A run is defined by four things: the seed, `specs.jsonl`, the prompt version, and the cached responses.
- **Failures.** Errored, expired and `stop_reason == "refusal"` results are logged and retried once, then skipped. The script prints token usage and cost after each run.
- **API key.**
  - The script reads `ANTHROPIC_API_KEY` from the environment only, and never logs or writes it. There are no `.env` files, and `.env*` is in `.gitignore` anyway.
  - Set it once as a Windows user environment variable (see PLAN.md P0).
  - Set a monthly spend limit in the Claude Console.

### 1.2 Boilerplate masking, dedup and validation — `pipeline/clean.py`, `pipeline/dedup.py`, `pipeline/validate.py`

- **Boilerplate masking: the models and similarity checks never see meeting boilerplate.**
  - `mask_boilerplate(text)` blanks Teams/Zoom/Meet/Webex join blocks, dial-in and phone strings, meeting IDs, passcodes and PINs, URLs and `[link]` placeholders, rule lines, forward separators, and `From:`/`Sent:`/`Cc:` header lines.
  - It **keeps** `Subject:`, `To:`/`Attendees:` lists (the attendee count is a rubric signal), `When:`/`Date:` times, agenda lines (even between rule lines), forward notes and quoted replies, and in-text location mentions like "Room 4B / Teams".
  - Why: in invites with a full Teams block, the block is a median 44% of the text. Without masking it would dominate TF-IDF, use up the embedding model's ~256-token window, invite shortcut learning from your labels, and draw highlights onto "Click here to join". Real visitors will also paste Zoom/Meet/Webex blocks the synthetic data barely covers.
  - Masked characters become spaces and newlines stay, so **output length = input length** and every offset maps straight back to the original text, for highlights (§1.8). Masking repeats until stable, so it's idempotent.
  - Rules live in `pipeline/clean_rules.json`, shared with `web/src/lib/clean.ts` (P4). They're a regex subset that behaves the same in Python (`re.IGNORECASE | re.ASCII`) and JavaScript (`i` flag): no inline flags, no lookbehind.
  - People (labeler, review output, the site's text display) always see the original. `sample.py --cleaned` shows what the model sees, and `report.py` reports how much was masked (currently 311 of 800 invites, median 12% of their characters).
- Normalize each invite (mask boilerplate, lowercase, collapse whitespace, strip punctuation), then drop exact duplicates by hash.
- Then drop near-duplicates: TF-IDF on character 3–5-grams, removing any pair with cosine similarity ≥ 0.9. This uses scikit-learn, so there's no extra dependency.
- The same function checks for test-vs-train leakage. Any test invite with a near-duplicate in the training set fails validation.
- `validate.py` checks schemas, unique IDs, the label enum, class balance, and that every labeled ID exists. It runs in CI.

### 1.3 Rubric — `docs/rubric.md` (you write this; P1 includes a template)

The rubric lists the signals that matter:
- Is a decision needed?
- Is there real discussion, or just status updates?
- Is the attendee count proportionate?
- Does the duration fit the agenda?
- Is there an agenda at all?

It also gives tie-break rules, especially for the fuzzy middle class `shorter` (e.g. "a real decision, but 60 min for 2 agenda items → shorter"). It ends with 3 worked examples per class.

### 1.4 Labeling — `pipeline/label.py`

- **Keyboard CLI built with `rich`.** It shows the invite in a panel with a one-line rubric cheat-sheet.
  - Keys: `1` keep · `2` shorter · `3` email · `s` skip · `d` discard (broken or offensive) · `n` add a note · `u` undo · `q` quit.
- **Resumable and append-only.** Each keypress appends one line to `data/labels.jsonl`. When an ID appears more than once, the last line wins. Expect about 30 seconds per invite, so ~600 invites take about 5 hours in sessions of ~100.
- **Self-consistency check.** At least 5 days after your first pass, `label.py --relabel 0.1` shows a random 10% again, blind. Cohen's kappa between the passes goes on the eval page. The target is ≥ 0.7.

### 1.5 Training — `pipeline/train.py`

- **Input:** both models, and the structure-feature parser, read `mask_boilerplate(text)` (§1.2), never the raw text.
- **Hyperparameters** come only from stratified 5-fold cross-validation on the training set. The test set is never touched during training.
- **Structure features** (shared by both models). A small regex-parsed, binned set:
  - duration bucket, with an explicit **unknown** bucket. Zoom invites state only a start time, and 63 of the main 800 give no duration (mostly one-line titles), so the 60-invite Zoom supplement (`spec_0801`…) covers full invites without one
  - attendee-count bucket, with an explicit **unknown** bucket. A third of the invites state no count or list (Zoom never does), so "not stated" must not read as "small". Counted from explicit numbers, attendee lists, or names given a job; "whole team" / "all staff" is its own bucket
  - has an agenda (bulleted or numbered lines)
  - has decision words ("decide", "approve", "sign off")
  - has status words ("update", "sync", "check-in")
  - has a question mark

  They're one-hot encoded, so they're trivial to mirror in TypeScript and easy to turn into reasons ("12 people for 15 minutes of updates").
- **Model A (baseline):**
  - A custom regex tokenizer: lowercase, keep numbers and times like `30min` and `2pm` as tokens, specified in `pipeline/features_spec.json` (with the structure-feature patterns) so TypeScript can implement it identically.
  - `TfidfVectorizer(tokenizer=…, ngram_range=(1,2), sublinear_tf=True, min_df=2, max_features≈5000)`, combined with the structure features.
  - `LogisticRegression` (multinomial), with `C` chosen by CV.
- **Model B (embedding):**
  - Embeddings come from the exact quantized ONNX file the browser will load. Python runs it with `onnxruntime` + `tokenizers`, then applies numpy mean pooling and L2 normalization. That's about 20 lines of code.
  - No PyTorch, so the venv stays small, and Python and browser embeddings match by construction.
  - The 384-dimensional embedding is combined with the structure features and fed to `LogisticRegression`.
- **Picking the embedding model.**
  - Candidates: `Xenova/all-MiniLM-L6-v2` (q8, ~23 MB, 256-token limit) and `Xenova/bge-small-en-v1.5` (q8, ~34 MB, 512 tokens).
  - Ship MiniLM unless bge beats it by ≥ 3 macro-F1 points in CV. (Result: MiniLM, 0.548 vs 0.530.)
  - Pinned commits and pooling live in `pipeline/embed_models.json`. **MiniLM uses mean pooling, BGE uses the [CLS] token**; the browser must match whichever ships.
  - Invites over the token limit are split into chunks and their embeddings averaged.

### 1.6 Evaluation — `pipeline/evaluate.py`

- Each model is evaluated on the test set once, after its hyperparameters are frozen. The script refuses to run again on a changed model unless you pass `--i-know`, which is logged in `eval.json`.
- **Metrics.**
  - Primary: macro-F1, because it treats the fuzzy `shorter` class fairly.
  - Also reported: accuracy, per-class precision/recall/F1, the confusion matrix, and bootstrap 95% confidence intervals (1,000 resamples).
- **Comparison.** McNemar's test between the two models. With only ~75 test invites, if the result isn't significant (p ≥ 0.05) the eval page says it's a tie, and you choose (default: the linear model, since it's smaller and its explanations are exact).
- **Boilerplate invariance.** Append Zoom, Google Meet, Webex and Teams blocks (formats the training data barely covers) to every test invite, and report how often the prediction flips, with and without masking. The target with masking is ~0 flips. It's a cheap robustness result for the eval page.
- **Output.** `data/eval.json` holds metrics for both models, CV scores, kappa, class counts, and every test mistake (text, true label, predicted label, probabilities). You pick the funny ones for the gallery by listing their IDs in `pipeline/featured_mistakes.txt`.

### 1.7 Export — `pipeline/export.py`

- **`models/linear.json`:** `{version, labels, tokenizer, vocab: {term: index}, idf: [...], structure: {...spec}, coef: [[...]×3], intercept: [3]}`.
  - Floats are rounded to 5 significant digits. Expect ≤ 150 KB gzipped.
- **`models/embed_head.json`:** `{version, labels, model: {id, revision, file, sha256}, structure, coef: [[...]×3], intercept}`.
- **ONNX weights stay out of git.**
  - `web/scripts/fetch-model.mjs` downloads the pinned Hugging Face revision, checks its sha256, and places it in `web/public/models/`. The same script copies the onnxruntime-web `.wasm` files into `web/public/ort/`.
  - It runs before `dev`/`build` (like Neighborly's `sync-data`) and in CI.
- **`data/fixtures.json`:** ~40 inputs, including edge cases (empty text, emoji, 5,000 characters, non-English), with the expected probabilities and top contributions from Python. TypeScript tests must reproduce them.

### 1.8 Web app — `web/` (Astro + TypeScript, no UI framework)

- **Main page.**
  - A large textarea, a Rate it button, and Try an example (cycles through ~8 bundled sample invites).
  - Result: a big verdict, a 3-segment probability bar, the invite redisplayed with highlights, and 3–5 reasons.
  - A Share verdict button copies, for example, *"My meeting got 'This is an email' (87%) 📧 → URL"*. It never includes the pasted text.
- **Privacy banner** near the input: *"Runs entirely in your browser. Nothing you paste leaves your device."* It links to the How it works section.
- **Inference runs in a Web Worker** so the UI stays responsive.
- **Masking first:** `web/src/lib/clean.ts` applies `pipeline/clean_rules.json` before tokenizing. Because masking preserves length, tokenizer offsets on the masked text are also offsets in the pasted text, and highlights land in the right place. Masked spans are shown dimmed with a quiet "ignored: dial-in details" label.
- **Code layout** follows Neighborly: pure logic in `web/src/lib/` (`clean`, `tokenize`, `features`, `linear`, `embed`, `explain`, `spans`, `reasons`, `share`), each with Vitest tests. Browser glue goes in `web/src/scripts/`, shared chrome in `web/src/layouts/Layout.astro`, and Neighborly's theme toggle and contrast test are reused.
- **Linear-model explanations.**
  - For the predicted class *k*, each n-gram *j* contributes `x_j · (w_k,j − mean over other classes of w_c,j)`.
  - A bigram's contribution is split evenly across its two tokens, then summed per character span using the tokenizer's offsets.
  - Adjacent tokens that push the same way merge into phrases.
  - Color shows which class the phrase pushes toward (3 accessible hues, plus an icon or underline style so meaning doesn't rely on color alone). Intensity shows magnitude.
  - Reasons: the top 3 phrases and any active structure features, rendered through friendly templates (*"'quick sync' — status-update language"*, *"20+ attendees"*).
- **Embedding-model explanations (occlusion).**
  - Split the invite into lines or clauses (at most 25 segments), re-embed it once with each segment removed (one batched pass), and highlight each segment by how much its removal lowers the predicted class's probability.
  - This is faithful to the shipped model by construction. Reasons come the same way as for the linear model.
- **Explanations always come from the model that produced the verdict.** We never show linear-model highlights next to an embedding-model verdict.

### 1.9 Eval page and case study

- **`/how-it-was-built/eval/`** is generated from `data/eval.json` at build time:
  - headline metrics with confidence intervals, and a per-class table
  - the confusion matrix (inline SVG, labeled cells, so it reads without color)
  - the model comparison table (size, speed, macro-F1, McNemar result) and kappa
  - a data card: synthetic + hand-labeled disclosure, counts per class, how the test set was written
  - the funny-mistakes gallery
- **`/case-study/`** is rendered from `docs/case-study.md`, the same pattern as Neighborly's `docs/how-it-works.md`. Narrative: problem → rubric → data → labeling → models → evaluation → deployment → what I'd do next.

## 2. Libraries

| Library | Why | License |
|---|---|---|
| **Python** (venv, 3.14; fall back to 3.13 if a wheel is missing) | | |
| scikit-learn | TF-IDF, logistic regression, CV, metrics | BSD-3 |
| numpy | Pooling, bootstrap, export math | BSD-3 |
| anthropic | Official SDK for generation (batches, structured outputs) | MIT |
| onnxruntime | Runs the same ONNX embedding model as the browser; no PyTorch | MIT |
| tokenizers | Same tokenizer files Transformers.js uses | Apache-2.0 |
| huggingface_hub | Pinned-revision model download | Apache-2.0 |
| rich | Readable, keyboard-driven labeling CLI | MIT |
| pytest · ruff | Tests and lint/format, same as Neighborly | MIT · MIT |
| **Web** | | |
| astro · typescript | Same stack as Neighborly; static output for GitHub Pages | MIT · Apache-2.0 |
| @huggingface/transformers (v3) | Browser ONNX inference + tokenizer (only if the embedding model ships); bundles onnxruntime-web (MIT) | Apache-2.0 |
| vitest | Unit and parity tests, same as Neighborly | MIT |
| @playwright/test | End-to-end and network-privacy tests in a real browser | Apache-2.0 |
| @axe-core/playwright | Automated accessibility checks | MPL-2.0 |
| **Models** | | |
| sentence-transformers/all-MiniLM-L6-v2 (Xenova ONNX) | 22M params, ~23 MB q8, fast | Apache-2.0 |
| BAAI/bge-small-en-v1.5 (Xenova ONNX) | 33M params, ~34 MB q8, usually more accurate | MIT |

Credits and licenses go in the README and the page footer, the same way Neighborly does it.

## 3. Data formats

All datasets are JSONL (one JSON object per line, UTF-8), so diffs stay readable and appends are safe. IDs are stable: `inv_000123` for generated invites, `test_001` for test invites.

| File | Shape | Committed |
|---|---|---|
| `data/specs.jsonl` | `{spec_id, seed, meeting_type, industry, tone, length, vagueness, attendees, duration_min, messiness: [...], gen_hint}` | yes |
| `data/raw/<spec_hash>.json` | Raw API response + usage | yes |
| `data/invites.jsonl` | `{id, text, source: "synthetic", spec_id, gen_model, prompt_version, created}` | yes |
| `data/labels.jsonl` | `{id, label: "keep"\|"shorter"\|"email"\|null, discarded: bool, note, pass: 1\|2, labeled_at}` | yes |
| `data/test/test_invites.jsonl` | `{id, text, label, note}`; written and labeled by you | yes |
| `data/eval.json` | Metrics, CV scores, kappa, mistakes | yes |
| `data/fixtures.json` | Parity fixtures for TypeScript tests | yes |
| `models/linear.json`, `models/embed_head.json` | Exported models | yes |
| `web/public/models/*.onnx`, `web/public/ort/*.wasm` | Fetched at build time | no |

## 4. Repo layout

```
more/                      (rename on GitHub in P0)
├─ BRIEF.md · TECH_REQUIREMENTS.md · PLAN.md · CLAUDE.md · README.md
├─ pyproject.toml          ruff + pytest config (copied from Neighborly)
├─ package.json            npm workspaces → web/
├─ pipeline/
│  ├─ requirements.txt · paths.py
│  ├─ generate.py · dedup.py · validate.py · label.py
│  ├─ features.py (tokenizer + structure features) · embed.py
│  ├─ train.py · evaluate.py · export.py · report.py
│  ├─ clean_rules.json · features_spec.json · embed_models.json · featured_mistakes.txt
│  ├─ prompts/generate_v1.md
│  ├─ tests/
│  └─ .cache/              (gitignored: downloaded ONNX for Python)
├─ data/                   (see §3)
├─ models/
├─ docs/  rubric.md · case-study.md · model-report.md
├─ web/
│  ├─ scripts/ fetch-model.mjs · sync-data.mjs
│  ├─ src/lib/ · src/scripts/ · src/pages/ · src/layouts/ · src/components/
│  ├─ public/
│  └─ e2e/                 Playwright tests
└─ .github/workflows/ pipeline.yml · web.yml · deploy.yml
```

## 5. Testing

| Layer | What | Tool |
|---|---|---|
| Pipeline | Tokenizer cases, structure-feature parsing, dedup thresholds, leakage check, deterministic spec sampling and CV splits, export schema, `validate.py` on real data | pytest (CI) |
| Parity | TypeScript boilerplate masking matches Python character for character on every fixture. TypeScript tokenizer, features and linear inference match `fixtures.json` to within 1e-6. Embedding (Node, onnxruntime-node) matches Python to within 1e-3, tagged slow | Vitest (CI) |
| Web logic | Span merging, highlight segments, reasons templates, share text (never contains input) | Vitest |
| End to end | Paste → verdict → highlights rendered; sample button; keyboard-only flow | Playwright |
| Privacy | Records every network request during paste + classify. Fails on any non-same-origin request, or any request URL or body containing the pasted text | Playwright (CI) |
| Accessibility | axe scan on every page; WCAG AA contrast on all theme tokens (Neighborly's `contrast.test.ts`) | Playwright + Vitest |

## 6. Privacy guarantees

1. **No network at inference.** All classification happens in a Web Worker on the user's device. No API exists to send the text to.
2. **Enforced by the browser.**
   - CSP meta tag: `default-src 'self'; connect-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data:`.
   - Even a bug or a compromised dependency can't send data to another origin.
3. **No third parties.**
   - No analytics, cookies, web fonts, CDNs, or Hugging Face Hub calls. Transformers.js is configured with `allowRemoteModels = false` and local `wasmPaths`.
   - GitHub Pages logs only standard request metadata for static files.
4. **No storage of input.** Pasted text is never written to localStorage or IndexedDB, or put in the URL. Only the theme preference is stored. The model file is cached by the browser like any other static asset.
5. **Sharing is opt-in and excludes the input.**
6. **Disclosed and tested.** Shown prominently on the page and explained on the case study. The Playwright privacy test runs in CI on every push.
7. **Dataset privacy.** All training and test data is synthetic or written by you. No real company invites. Generation-time prompts contain no personal data.

## 7. Performance targets

| Metric | Target |
|---|---|
| Page shell (HTML + CSS + JS, excluding models) | ≤ 150 KB gzipped |
| Linear model JSON | ≤ 150 KB gzipped; verdict + explanation < 50 ms |
| Embedding model total one-time download (model + ORT wasm) | ≤ 45 MB, starts when the textarea gets focus, progress bar shown, then browser-cached |
| First embedding verdict (cold, 50 Mbps, mid-range laptop) | ≤ 8 s including download |
| Warm embedding verdict + occlusion explanation | ≤ 700 ms single-threaded |
| Largest Contentful Paint (shell) | < 1.5 s on fast 4G |
| Lighthouse | Performance ≥ 90 · Accessibility 100 · Best practices ≥ 95 |

GitHub Pages can't send COOP/COEP headers, so onnxruntime-web runs single-threaded. The targets above assume that.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Models learn the generator's writing style, not the task | Test set written by hand, in a different voice; wide spec grid + messiness; honest disclosure and a "real-world caveats" section in the case study |
| `shorter` is subjective, so labels are noisy | Rubric with tie-breaks and examples; notes field; relabel pass + kappa; macro-F1 so the middle class counts |
| ~75 test items make the comparison noisy | Bootstrap CIs, McNemar's test, a pre-declared tie rule; don't overclaim |
| Test/train leakage | Test set written separately before looking at model results; near-duplicate check in `validate.py`; evaluate runs once per frozen model |
| Python and TypeScript preprocessing drift apart | One tokenizer spec file and one masking-rules file; parity fixtures in CI; Model B uses the identical ONNX file in both |
| Model keys on meeting boilerplate (Teams/Zoom blocks, dial-ins, forward headers) instead of content | `mask_boilerplate` before every model and similarity check; the boilerplate-invariance check in evaluation; masked spans visibly dimmed on the site |
| Embedding model too heavy or slow | q8 weights, lazy load, worker, progress UI; if loading fails, fall back to the linear model with a visible note; tie rule favors the linear model |
| 256-token limit truncates long invites | Chunk and average; documented |
| CSP or wasm or worker incompatibilities | Prove the self-hosted model + CSP early in P4 with a bare test page before building UI |
| API cost, refusals, rate limits | Batches, result cache, hard cap on request count, spend limit in Console, refusal and error handling |
| onnxruntime or tokenizers wheel missing for Python 3.14 | Fall back to a 3.13 venv (decided in P0 by a test install) |
| Odd or offensive generated text | Discard key in labeler; prompt sets a workplace-safe tone |
| Users paste sensitive real invites | That's the privacy design (§6); nothing leaves the device |
| The joke falls flat or reads as mean | You approve sample invites, verdict copy and reasons templates in P5 |
