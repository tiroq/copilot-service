# Release guide

## Automated release (GitHub Actions)

Go to **Actions → Release → Run workflow** in the GitHub UI:

1. Choose **bump type**: `patch`, `minor`, or `major`.
2. Optionally fill **release notes** (one bullet per line).
3. Optionally tick **Dry run** to preview the next version without making any changes.
4. Click **Run workflow**.

The workflow will:
- Calculate the next version from `pyproject.toml`.
- Update `pyproject.toml` and `CHANGELOG.md`.
- Run `compileall`, `pytest`, `build`, and `twine check`.
- Commit with message `release: vX.Y.Z`.
- Push the commit and create/push the annotated tag `vX.Y.Z`.

The existing `publish.yml` workflow triggers on every `v*.*.*` tag push and will
automatically publish `copilot-caas` to PyPI via Trusted Publishing.

### Dry run

Dry run prints the calculated next version, planned tag, and planned CHANGELOG section
without touching any file, committing, or pushing:

```
Actions → Release → Run workflow
  bump: patch
  dry_run: ✓
```

### Normal patch release

```
Actions → Release → Run workflow
  bump: patch
  notes: "- Fixed X.\n- Improved Y."
  dry_run: (unchecked)
```

---

## Manual release (local fallback)

Use this if the Actions workflow is unavailable.

```bash
# 1. Validate everything is green
python -m compileall src tests
python -m pytest -q
python -m build
python -m twine check dist/*

# 2. Bump version in pyproject.toml manually, then update CHANGELOG.md

# 3. Commit and tag
git add pyproject.toml CHANGELOG.md
git commit -m "release: vX.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# 4. Push
git push origin main
git push origin vX.Y.Z
```

Pushing the tag triggers `publish.yml` which publishes to PyPI.

---

## PyPI environment setup (Trusted Publishing)

The `publish.yml` workflow uses OIDC Trusted Publishing — no API token needed.

Required GitHub environment: `pypi`  
Required PyPI project: `copilot-caas`  
Configure Trusted Publishing at: <https://pypi.org/manage/project/copilot-caas/settings/publishing/>

Publisher settings:
- Owner: `tiroq`
- Repository: `copilot-service`
- Workflow filename: `publish.yml`
- Environment name: `pypi`
