# Contributing

This guide documents a few shared conventions to keep the repository organized and make collaboration easier. It is meant to provide consistency without prescribing how each contributor works.

## Repository Basics

**Analysis files** are Python scripts under `notebooks/`, numbered sequentially:
- `01_data_loading_and_exploration.py`
- `02_data_cleaning.py`

This repository uses `.py` files only, not `.ipynb` notebooks.

**Raw data** in `data/raw/` is immutable. Never edit raw files manually. All transformations happen in code.

**Processed data** is generated locally by running analysis scripts. Large generated datasets stay local and are not committed to Git. Small, stable reference data may be committed if the team decides it should be versioned.

To regenerate processed datasets, see `data/README.md`.

## Getting Started

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up datasets: Follow `data/README.md`
4. Run analysis scripts from the repo root

## Branches

Use a short, descriptive branch name related to your work. Examples:
- `feat/clean-preprocess-favorita`
- `docs/data-dictionary`
- `audit/ticket-7`

## Commits

Use clear commit messages that describe the change. Prefixes such as `feat:`, `fix:`, and `docs:` are encouraged for consistency:

```
feat: Implement Favorita sales cleaning

Added outlier flagging
Validated data integrity
Output: 3M rows, 7 columns
```

## Pull Requests

Pull requests should briefly explain what changed and should be reviewed by at least one other team member before merging.

## Credentials & Secrets

Never commit API keys, `.env` files, or credentials. Keep `kaggle.json` and similar files local and in `.gitignore`.

## Questions?

Refer to `data/README.md` for dataset questions or ask the team.
