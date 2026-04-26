# PyPI Publishing Setup

This repository contains four publishable packages:

- `ayuna-core`
- `ayuna-creds`
- `ayuna-secrets`
- `ayuna-dostore`

`ayuna-creds` depends on `ayuna-core`, and both `ayuna-secrets` and `ayuna-dostore` depend on `ayuna-creds`. Publish in this order:

1. `ayuna-core`
2. `ayuna-creds`
3. `ayuna-secrets`
4. `ayuna-dostore`

## GitHub Actions artifact

Workflow: `.github/workflows/publish-pypi.yml`

This workflow:

- builds wheel + sdist for each package
- publishes to PyPI or TestPyPI using Trusted Publishing (OIDC)
- supports publishing a single package or all packages
- preserves dependency order when publishing all

## One-time setup in PyPI and TestPyPI

For each project (`ayuna-core`, `ayuna-creds`, `ayuna-secrets`, `ayuna-dostore`) configure a Trusted Publisher in:

- `https://pypi.org/manage/project/<project>/settings/publishing/`
- `https://test.pypi.org/manage/project/<project>/settings/publishing/`

Use:

- **Owner**: `<your-github-org-or-user>`
- **Repository name**: `ayuna-pykit`
- **Workflow name**: `publish-pypi.yml`
- **Environment name**: `pypi` (for PyPI) and `testpypi` (for TestPyPI)

Also create matching GitHub environments in repo settings:

- `pypi`
- `testpypi`

## Manual publish with GitHub Actions

Run workflow `Publish Python Packages` and choose:

- `package`: `all` or one package
- `repository`: `pypi` or `testpypi`

### Actions UI quick steps

1. Open GitHub repo `ayuna-pykit`.
2. Go to **Actions** -> **Publish Python Packages**.
3. Click **Run workflow**.
4. Select:
   - `package`: `all`, `ayuna-core`, `ayuna-creds`, `ayuna-secrets`, or `ayuna-dostore`
   - `repository`: `testpypi` (recommended first) or `pypi`
5. Click **Run workflow** to start publishing.

Tip: publish to `testpypi` first to validate packaging and dependencies before publishing the same versions to `pypi`.

## Local publish helper script

Script: `scripts/publish_pypi.sh`

Requirements:

- `uv`
- `twine` (`uv tool install twine`)
- valid PyPI credentials configured for twine (for example in `~/.pypirc` or `TWINE_*` env vars)

Usage:

```bash
./scripts/publish_pypi.sh pypi
./scripts/publish_pypi.sh testpypi
```
