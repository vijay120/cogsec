# Personal Cognitive Security System

A personal practice framework for cognitive resilience, happiness, and effective goal execution.

## What This Is

Cognitive security at the individual level: protecting and optimizing how you think, feel, and act. Not institutional defense against disinformation — personal defense against the forces (internal and external) that erode clarity, happiness, and effectiveness.

## Structure

All content lives under `docs/` (the MkDocs source). `mkdocs.yml` and this README sit at the repo root.

```
cogsec/
├── docs/                        # MkDocs source — the single source of truth
│   ├── index.md                 # Site home page
│   ├── wiki/                    # Knowledge base — the "why" behind each practice
│   │   ├── 01-perception.md     # Layer 1: What gets in
│   │   ├── 02-processing.md     # Layer 2: How you think
│   │   ├── 03-output.md         # Layer 3: What you do
│   │   ├── 04-social.md         # Layer 4: Building your cognitive environment
│   │   ├── 05-ai-threats.md     # Layer 5: Defending against synthetic manipulation
│   │   └── 06-desire.md         # Layer 6: Freedom from compulsion (desire & aversion)
│   ├── practice/                # The "how" — daily systems
│   │   ├── daily-checklist.md   # Morning + evening routine
│   │   ├── weekly-review.md     # Weekly reflection template
│   │   └── cbt-journal.md       # CBT journaling template
│   └── tracker/                 # Progress tracking
│       └── tracker.md           # Weekly scoring system
├── mkdocs.yml                   # Site + navigation config
├── .github/workflows/deploy.yml # Auto-deploy to GitHub Pages on push to main
└── README.md                    # This file
```

## Local Preview

```bash
python3 -m venv .venv
.venv/bin/pip install mkdocs-material
.venv/bin/mkdocs serve      # http://127.0.0.1:8000
```

## Deployment

Pushing to `main` triggers the GitHub Actions workflow, which runs `mkdocs gh-deploy`
and publishes the built site to the `gh-pages` branch. Live at
<https://vijay120.github.io/cogsec/>.

## Quick Start

1. Read the wiki pages (20 min total)
2. Start with the daily checklist
3. Add one practice per week — don't try everything at once
4. Do the weekly review every Sunday
5. Track progress in the tracker

## Sharing

All files are Markdown — paste directly into Notion, Obsidian, or any wiki tool. The daily checklist and CBT journal work as Notion database templates.

## Evidence Base

Every practice included has replicated research support. The wiki pages cite key studies. Nothing here is self-help fluff.
