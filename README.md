# Builder-Morphe

Downloads the latest version of each configured app, patches it with
Morphe/ReVanced-style patches, verifies and signs the result, and
publishes everything as a single GitHub Release. Runs entirely inside
GitHub Actions (`.github/workflows/patch.yml`).

## Project layout

```
.
├── main.py                 # patches one app - run once per matrix job
├── prepare_release.py      # validates config + computes the release tag (runs first)
├── finalize_release.py     # collects every patched APK and publishes the release (runs last)
├── commit_signature.py     # commits newly-learned/pending signatures back to data/
├── data/
│   ├── known_signatures.json    # pinned certificate fingerprints per app
│   └── pending_signatures.json  # fingerprints seen but not yet verified/pinned
└── core/
    ├── config.py             # app list, patch sources, process order - edit this to add/change an app
    ├── validate.py           # sanity-checks config.py at startup (called from prepare_release.py)
    ├── log.py                # colorized console output
    ├── notify.py             # optional Discord/Telegram release notifications
    ├── release.py            # GitHub Releases API (create/upload/delete)
    ├── retry.py              # shared retry/backoff math + async retry loop
    ├── patch_tools.py        # fetches morphe-desktop.jar + patch bundles from GitHub
    ├── sources/              # where a raw APK comes from - one module per source
    │   ├── apkmirror.py        # browser-automated APKMirror downloader
    │   └── github_apk.py       # GitHub-hosted APK mirror / direct upstream repo downloader
    └── apk/                  # things done to the APK itself once downloaded
        ├── verify.py           # checks the signing certificate against data/known_signatures.json
        ├── patcher.py          # runs morphe-desktop to apply patches
        └── versions.py         # version-string parsing/selection
```

## Adding a new app

1. Add an entry to `APPS_CONFIG` and `PROCESS_ORDER` in `core/config.py`.
2. If it's downloaded via APKMirror, add it to `APKMIRROR_APPS` and give
   it an entry in `core/sources/apkmirror.py`'s `APP_SITES`. Otherwise,
   give it an entry in `core/sources/github_apk.py`'s `APP_TAGS` or
   `DIRECT_REPOS`.
3. `prepare_release.py` runs `core/validate.py` before every release and
   fails fast with a clear message if any of the above is missing or
   inconsistent - before the patch matrix ever starts.

## Keeping dependencies current

- **GitHub Actions** (`checkout`, `setup-python`, etc.): watched weekly by
  Dependabot (`.github/dependabot.yml`), which opens a PR when a newer
  version is out.
- **Python packages** (`nodriver`, `httpx`): not watched by Dependabot on
  purpose. `requirements.txt` pins no version, so `pip install --upgrade`
  in the `prepare` job already installs the latest release of both on
  every run; the resolved versions get frozen to `requirements-lock.txt`
  and committed automatically.

