# Could This Meeting Be an Email?

Paste a meeting invite or agenda and a text classifier rates it **Keep the meeting**, **Make it shorter**, or **This is an email**, highlighting the phrases that drove the score. Everything runs in your browser: nothing you paste leaves your device.

Live at https://meeting.amandapatricks.com (in progress).

A portfolio project showing the full machine learning lifecycle: rubric, synthetic dataset, hand labeling, training and comparing two models, evaluation on a hand-written test set, and in-browser deployment.

## Layout
- `pipeline/`: Python scripts for data generation, labeling, training, evaluation and export (commands in [CLAUDE.md](CLAUDE.md))
- `data/`: generated invites, labels, test set, evaluation results
- `models/`: exported models the site loads
- `web/`: the site (Astro + TypeScript)
- `docs/`: rubric, case study, model report

## Data disclosure
The training invites are synthetic, generated with Claude, and labeled by hand against a written rubric. The test set was written by hand. No real meeting invites are used.

## Credits and licenses
Filled in as dependencies and models are added (see TECH_REQUIREMENTS.md §2).
