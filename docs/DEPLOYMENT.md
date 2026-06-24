# OrthoTwin Deployment Guide

This document explains what is automated in GitHub Actions and what you must configure manually.

## Automated in the Repository

| Feature | Workflow | Trigger |
|---|---|---|
| CI checks | `.github/workflows/ci.yml` | Every push and pull request |
| GitHub Pages website | `.github/workflows/pages.yml` | Push to `main` when `docs/site/` changes |
| Showcase release package | `.github/workflows/release.yml` | Push a version tag like `v1.0.1` |

## What You Must Do Manually

### 1. Enable GitHub Pages (one-time)

1. Open https://github.com/Sarthaksahu777/OrthoTwin/settings/pages
2. Under **Build and deployment**, set **Source** to **GitHub Actions**
3. Push this repository to `main` (or run the **Deploy GitHub Pages** workflow manually)
4. After the workflow succeeds, the site will be available at:

```text
https://sarthaksahu777.github.io/OrthoTwin/
```

The MRI browser demo page:

```text
https://sarthaksahu777.github.io/OrthoTwin/mri-viewer.html
```

### 2. Publish a GitHub Release Package (when ready)

From your local clone:

```powershell
git tag v1.0.1
git push origin v1.0.1
```

GitHub Actions will build `orthotwin-showcase.zip` and attach it to the release.

You can also run **Release Showcase Package** manually from the Actions tab to download the zip without creating a tag.

### 3. Run the Full MRI DICOM Browser Locally

The static GitHub Pages demo uses exported PNG slices only. The original Phase 1 app loads DICOM volumes with Streamlit.

1. Copy `app.py` from your local archive:

```text
ORTHOTWIN_INTERNAL_DO_NOT_UPLOAD/archive/app.py
```

2. Install Streamlit dependencies:

```powershell
pip install -r requirements-streamlit.txt
```

3. Obtain RSNA lumbar spine DICOM data and place it in either layout:

```text
train_images/<study_id>/<series_id>/*.dcm
```

or

```text
<study_id>/<series_id>/*.dcm
```

4. Point the app to:

- `data/raw/train.csv`
- `data/raw/train_series_descriptions.csv`

5. Run:

```powershell
streamlit run app.py
```

See `docs/README.md` for full MRI browser documentation.

### 4. Optional — Deploy Streamlit to Streamlit Community Cloud

1. Restore `app.py` to the public repository (or a separate demo repo)
2. Add `requirements-streamlit.txt` as the dependency file
3. Sign in at https://share.streamlit.io
4. Connect the GitHub repository and set the main file to `app.py`
5. Provide DICOM data through your own storage or keep the app local-only

Streamlit Cloud cannot host the 33 GB RSNA DICOM archive inside GitHub, so a hosted demo usually needs external data storage or a reduced public sample set.

## What Is Not Included in the Public Repo

- Raw DICOM collections (`train_images/`, large `.dcm` archives)
- Full Streamlit `app.py` source (archived locally)
- Private patient data or credentials

## Quick Links

- Repository: https://github.com/Sarthaksahu777/OrthoTwin
- MRI browser docs: `docs/README.md`
- Static website source: `docs/site/`
