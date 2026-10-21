# Could This Meeting Be an Email? — Project Brief

## Goal
A browser-based tool for my portfolio site: paste a meeting invite or agenda, and a text classifier I trained rates it as "Keep the meeting," "Make it shorter," or "This is an email," with the phrases that drove the score highlighted.

Purpose: show the full machine learning lifecycle (dataset, labeling, training, evaluation, deployment) in something funny and shareable that connects to my project management background.

## Decided
- **Three labels:** Keep the meeting / Make it shorter / This is an email.
- **Rubric-based labeling:** I'll write a rubric of signals (decision needed, real discussion vs. status updates, attendees, duration, agenda present). I do the labeling myself.
- **Dataset:** several hundred LLM-generated invites (one-time generation cost), varied in style, length, and vagueness, including deliberately messy ones. Plus a hand-written held-out test set of 50–100 invites the model never trains on. The site discloses that the data is synthetic and hand-labeled.
- **Models:** compare at least two:
  1. Word-frequency features (e.g., TF-IDF) + logistic regression — the interpretable baseline.
  2. A small sentence-embedding model + a simple classifier on top.
  Ship whichever wins on the test set, and show the comparison publicly.
- **Runs entirely in the browser:** no server, no API calls at inference time, and nothing the user pastes ever leaves their device. State this prominently on the page.
- **Explanations:** highlight the phrases that pushed the score and give a short list of reasons.
- **Evaluation page:** accuracy, per-class precision/recall, a confusion matrix, the model comparison, and a gallery of funny mistakes.
- **Case study page** on how I built it, for the portfolio.
- **Hosting:** my existing site (amandapatricks.com). My word game Neighborly lives at neighborly.amandapatricks.com, so reuse its stack and deployment setup if practical.

## Open questions for you to recommend on
- Exact feature setup for the baseline, and how to turn its weights into phrase highlights.
- Which small embedding model (must have a permissive license and be small enough to download in a browser quickly), and how to explain its predictions.
- How to export each model for in-browser inference (e.g., weights as JSON for the linear model; ONNX/Transformers.js for the embedding model).
- Dataset tooling: how I'll label efficiently (a simple labeling script or local UI), and the data format.
- How to generate the synthetic invites reproducibly (prompts, seeds, dedup), and where the API key lives (environment variable, never committed).
- Target download size and load time for the page.

## Your task
Do NOT build yet. Produce two files:
1. **TECH_REQUIREMENTS.md** — components (data generation, labeling, training, evaluation, export, web app, eval page), recommended libraries with one-line reasons and licenses, data formats, repo layout, testing approach, privacy guarantees, performance targets, and risks with mitigations.
2. **PLAN.md** — a phased plan with a checkbox list and a clear "done when" gate for each phase. Suggested shape (adjust if you'd structure it differently):
   P0 Setup · P1 Rubric + data generation · P2 Labeling + test set · P3 Train and compare models · P4 Export + in-browser inference · P5 Web UI with highlights · P6 Eval page + case study · P7 Polish, accessibility, deploy
   Mark which phases need me (writing the rubric, labeling) versus which you can do.

## Environment
Windows 11, PowerShell syntax for every command. Python venv for data and training.