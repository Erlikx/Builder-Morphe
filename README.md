# Builder-Morphe

A GitHub Actions pipeline that downloads Android APKs, patches them (ReVanced-style, via a `morphe-desktop` CLI jar), re-signs them with your own release key, and publishes all of them together as a single GitHub Release. Everything runs on GitHub-hosted runners — no local machine required.

## Table of Contents

- [How It Works](#how-it-works)
- [Setup](#setup)
- [Running It](#running-it)
- [Verifying a Downloaded APK](#verifying-a-downloaded-apk)
- [Supported Apps](#supported-apps)
- [Adding a New App](#adding-a-new-app)
- [Project Structure](#project-structure)
- [CI (Lint & Test)](#ci-lint--test)
- [Configuration Reference](#configuration-reference)

## How It Works

One workflow, `.github/workflows/patch.yml`, runs as four jobs:

1. **`prepare`** — installs dependencies, freezes `requirements-lock.txt`, computes a release tag/name for this run (`prepare_release.py`), and pushes the lockfile if it changed.
2. **`patch`** — a matrix job, one runner per app (see [Supported Apps](#supported-apps)), running in parallel. Each runner downloads that app's original APK (from APKMirror via a real, fingerprint-resistant Firefox browser, or directly from a GitHub release), verifies its signing certificate against a pinned fingerprint, patches it with the matching patch bundle, re-signs it with your keystore, and uploads it as a build artifact.
3. **`finalize`** — downloads every artifact the matrix produced, matches each file back to its app, builds one release description (with per-app version numbers and collapsible patch-source changelogs), creates a single GitHub Release with every APK attached, uploads MicroG/PotHelper companions if YouTube or YT Music was patched, deletes older releases, and sends a Discord/Telegram/Apprise notification.
4. **`cleanup`** — deletes old workflow runs to keep the Actions tab tidy.

The workflow only runs when you trigger it manually (`workflow_dispatch`) — there's no schedule configured. See [Running It](#running-it) to add one if you want automatic runs.

A **separate** workflow, `.github/workflows/lint.yml`, runs `ruff`, `mypy`, and `pytest` on every push to `main` and on every pull request.

## Setup

### 1. Fork or use this repo

Push it to your own GitHub account/org — the workflow needs write access to create releases and commit signature records.

### 2. Repository permissions

**Settings → Actions → General → Workflow permissions** → select **"Read and write permissions"**. Without this, the `GITHUB_TOKEN` the workflow uses can't push commits, create releases, or upload artifacts.

### 3. Required secrets

**Settings → Secrets and variables → Actions → New repository secret.**

| Secret | Required | Purpose |
|---|---|---|
| `KEYSTORE_BASE64` | Yes, for your own signing key | Your Android signing keystore (`.jks`/`.keystore`), base64-encoded. Generate one with `keytool -genkeypair -v -keystore release.keystore -alias <your-alias> -keyalg RSA -keysize 2048 -validity 10000`, then `base64 -i release.keystore \| tr -d '\n'` and paste the output as the secret value. |
| `KEYSTORE_PASSWORD` | Yes, alongside the above | The keystore's password. |
| `KEY_ALIAS` | Yes, alongside the above | The `-alias` you used when generating the keystore. |
| `KEY_PASSWORD` | Yes, alongside the above | The key entry's password (often the same as `KEYSTORE_PASSWORD`). |
| `DISCORD_WEBHOOK_URL` | No | Discord webhook URL for a run-summary notification. |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | No | Telegram bot token + chat ID, same purpose. |
| `APPRISE_URLS` | No | Any other [Apprise](https://github.com/caronc/apprise#supported-notifications)-supported target(s) (Slack, ntfy, Matrix, email, …), space/comma/newline-separated. |

`GITHUB_TOKEN` itself is provided automatically by GitHub Actions — you don't create it.

**If you skip the four `KEYSTORE_*` secrets**, `core/apk/patcher.py` falls back to signing with the patcher tool's own shared default ("Morphe testkey") instead of failing — useful to try the pipeline quickly, but every fork that does this produces APKs signed with the *same* shared key, which isn't meaningfully "yours." Set your own keystore before you rely on this for real.

### 4. First run: pending signatures

The first time a given app runs, `data/known_signatures.json` won't have an entry for it yet, so `core/apk/verify.py` deliberately fails that app and records the certificate fingerprint it saw in `data/pending_signatures.json` instead (auto-committed by `commit_signature.py`). This is expected. Verify that fingerprint against an official source for that app (its Play Store listing, the developer's own site, etc.), then move it into `data/known_signatures.json` under the app's `name` key (see the existing entries for the format) and re-run. This is the pipeline protecting itself from ever patching an APK from an unexpected/compromised source without you noticing.

## Running It

**Actions tab → "Patch" workflow → Run workflow.** It processes every app in `core/config.py`'s `PROCESS_ORDER`.

To patch a single app instead of all of them, either run it locally (`TARGET_APP=youtube python main.py`, with the same env vars the workflow sets — see [Configuration Reference](#configuration-reference)) or temporarily edit the `matrix.app` list in `patch.yml`.

To run on a schedule instead of only by hand, add a `schedule:` trigger under `on:` in `patch.yml`, e.g.:

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * *"
```

## Verifying a Downloaded APK

Every APK in the Releases tab is a modified build — not the original developer's file — so its signature is necessarily different from the app you'd get off the Play Store. Two ways to confirm a given file genuinely came from *this* pipeline and hasn't been swapped or tampered with:

### Method 1 — GitHub Artifact Attestation (recommended)

The `patch` job's last step (`actions/attest`) generates a signed, Sigstore-backed attestation for every APK it produces, proving it was built by this exact workflow run in this exact repo. Verify it with the [GitHub CLI](https://cli.github.com/):

```bash
gh attestation verify YouTube-<version>.apk --owner <your-github-username-or-org>
```

A successful verification confirms the file was built by a GitHub Actions run in your repo — no manual fingerprint bookkeeping needed, and it can't be spoofed by re-uploading a different file under the same name.

### Method 2 — Signing certificate fingerprint

Every APK is signed with the same key (yours, if you set up `KEYSTORE_BASE64` — see [Setup](#setup)), so every release's APKs should all share one consistent SHA-256 certificate fingerprint. Check it with `apksigner` (bundled with the Android SDK build-tools) or `keytool`:

```bash
apksigner verify --print-certs YouTube-<version>.apk
# or
keytool -printcert -jarfile YouTube-<version>.apk
```

Look for the `SHA-256` line under the certificate. Compare it against the value you record after your first successful run — it should stay identical release after release, for every app, as long as you keep using the same keystore secrets. A file with a different fingerprint did not come from your pipeline.

> Fill in your own fingerprint once you have it, so downloaders don't have to dig through workflow logs:
>
> **Expected signing certificate SHA-256:** `<paste yours here after your first run>`

Note this is a *different* fingerprint from the ones in `data/known_signatures.json` — those pin each app's **original**, pre-patch developer certificate (checked internally, before patching starts) so a compromised mirror can't slip in a malicious source file. The fingerprint above is your **own** re-signing key, checked on the **final**, patched file.

One practical consequence of re-signing: Android refuses to install an update over an app signed with a different key. If you ever change keystores, users have to uninstall the old APK first.

## Supported Apps

Each row is one entry in `core/config.py`'s `PROCESS_ORDER` — the key used for `TARGET_APP` and in `data/known_signatures.json`. Several rows patch the *same* underlying app from a different patch source (e.g. `tiktok` vs `tiktok-hxreborn`); these are intentionally separate, independently downloaded and patched variants, not duplicates.

| Key | Package | Source | Patch source(s) |
|---|---|---|---|
| `youtube` | `com.google.android.youtube` | APKMirror | 🟢 Morphe |
| `youtube-music` | `com.google.android.apps.youtube.music` | APKMirror | 🟢 Morphe |
| `reddit` | `com.reddit.frontpage` | APKMirror | 🟢 Morphe |
| `reddit-adobo` | `com.reddit.frontpage` | APKMirror | 🥘 Adobo |
| `twitter` | `com.twitter.android` | APKMirror | ✖️ Piko |
| `twitter-x` | `com.twitter.android` | APKMirror | 🆕 Piko NewX, 🟢 Morphe |
| `instagram` | `com.instagram.android` | GitHub | ✖️ Piko |
| `gboard` | `com.google.android.inputmethod.latin` | APKMirror | ⌨️ JasonWu Gboard |
| `speedtest` | `org.zwanoo.android.speedtest` | GitHub | ⚡ Rushiranpise, 🟢 Morphe |
| `brave` | `com.brave.browser` | APKMirror | 🦁 dh6k |
| `proton-vpn` | `ch.protonvpn.android` | APKMirror | 🍃 hoo-dles |
| `tiktok` | `com.zhiliaoapp.musically` | APKMirror | 🎵 TikTok Patches, 🟢 Morphe |
| `tiktok-hxreborn` | `com.zhiliaoapp.musically` | APKMirror | 🔥 hxreborn TikTok, 🟢 Morphe |
| `warp` | `com.cloudflare.onedotonedotonedotone` | APKMirror | ⚡ Rushiranpise |
| `inshot` | `com.camerasideas.instashot` | APKMirror | 🎬 Hooman's Patches |
| `google-photos` | `com.google.android.apps.photos` | APKMirror | ⚡ Rushiranpise |
| `inure-github` | `app.simple.inure` | GitHub | ⚡ Rushiranpise |
| `inure-play` | `app.simple.inure.play` | GitHub | ⚡ Rushiranpise |
| `proton-pass` | `proton.android.pass` | APKMirror | ⚡ Rushiranpise |
| `notesnook` | `com.streetwriters.notesnook` | APKMirror | 🔥 hxreborn |
| `termius` | `com.server.auditor.ssh.client` | APKMirror | ⚡ Rushiranpise |

"APKMirror" means the app is scraped from apkmirror.com through a real (Camoufox-driven) Firefox browser; "GitHub" means it's downloaded directly from a GitHub release (`core/sources/github_apk.py`'s `APP_TAGS`/`DIRECT_REPOS`), which is faster and doesn't need a browser at all.

## Adding a New App

1. Add an entry to `APPS_CONFIG` in `core/config.py` (package name, patch source(s), CPU arch, icon URL; `exclude`/`enable`/`force_version`/`force_build` as needed — see the existing entries).
2. Add its key to `PROCESS_ORDER`.
3. If it downloads via APKMirror, add it to `APKMIRROR_APPS` and give it an entry in `core/sources/apkmirror.py`'s `APP_SITES` (the org/app slug APKMirror uses in its URLs). Otherwise, add it to `core/sources/github_apk.py`'s `APP_TAGS` or `DIRECT_REPOS`.
4. Add it to the `matrix.app` list in `.github/workflows/patch.yml`.
5. `python -c "from core.validate import validate_config; validate_config()"` catches most config mistakes (missing `PROCESS_ORDER`/`APKMIRROR_APPS`/`APP_SITES`/`APP_TAGS` entries) before you push.
6. Run it once — it will fail on purpose with a pending-signature message. Follow [First run: pending signatures](#4-first-run-pending-signatures) to pin its certificate, then run again.

## Project Structure

### Root scripts

| File | Purpose |
|---|---|
| `main.py` | The `patch` job's entry point. For one app: works out which version to fetch (a forced version, the patcher CLI's own `list-versions` output, or APKMirror's latest listing), downloads it, verifies its certificate, patches it, and copies the result into `dist/`. Also fetches the shared `morphe-desktop` patcher jar and every distinct patch bundle the selected apps need, once, before processing any app. Exits non-zero if any app failed, after attempting all of them. |
| `prepare_release.py` | Runs in the `prepare` job. Computes a release tag/name for this run and writes them as step outputs (`release_tag`, `release_name`) for the later jobs to consume. |
| `finalize_release.py` | Runs in the `finalize` job. Scans the downloaded artifacts directory, matches each `.apk` filename back to an app (`match_asset`), builds the release body (icons, versions, per-source collapsible changelogs), creates the GitHub Release, uploads every matched APK plus MicroG/PotHelper if relevant, deletes older releases, and sends the notification. |
| `commit_signature.py` | Runs at the end of every `patch` matrix job (`if: always()`). Commits any new entries that app's run added to `data/known_signatures.json` / `data/pending_signatures.json` straight back to `main`, retrying on push conflicts since multiple matrix jobs commit in parallel. |

### `core/` — shared library

| File | Purpose |
|---|---|
| `config.py` | The declarative app catalog: `APPS_CONFIG` (per-app package, patch source(s), arch, icon, patch flags), `PROCESS_ORDER` (which apps run and in what order), `APKMIRROR_APPS` (which app *names* download via APKMirror), `PATCH_SOURCES` (owner/repo/label for every patch-bundle GitHub repo used), `DISPLAY_NAMES`, and helpers (`patch_sources_for`, `get_release_naming` — picks a human display name and, if two config entries share one, disambiguates the release filename with the patch source's owner). |
| `settings.py` | One `pydantic-settings` `Settings` class declaring every environment variable the pipeline reads, case-insensitively (see [Configuration Reference](#configuration-reference)). |
| `log.py` | Leveled, colored console logging (`log.step`, `log.info`, `log.warn`, `log.notice`, `log.success`, `log.error`, …), a `NOTICE` level for expected/self-recovering events (retries, cooldowns) that stay out of GitHub's Warning annotations, GitHub Actions annotation output for real warnings/errors, and `patch_line()`, which classifies and re-colors the patcher CLI's own raw output line by line. |
| `retry.py` | Shared `tenacity` wait-strategy and `before_sleep` helpers used by every retry loop in the codebase, so backoff behavior and logging are consistent everywhere instead of hand-rolled per call site. |
| `http.py` | One shared `curl_cffi` session factory (`new_session`), configured to impersonate a current Firefox TLS/HTTP fingerprint. |
| `patch_tools.py` | `download_latest_github_asset()` — fetch a GitHub repo's latest (or latest prerelease) release, pick the asset matching a predicate, and resumably download it with retries. Used for the patcher jar, every patch bundle, and the MicroG/PotHelper companions. |
| `release.py` | Thin GitHub Releases REST API wrapper: create a release, list/delete releases and tags, upload an asset (replacing one of the same name if present), and the MicroG/PotHelper companion-upload helpers. |
| `notify.py` | Sends the end-of-run summary through `apprise` to whichever of Discord/Telegram/Apprise-URL targets are configured; also builds the summary/all-failed message text. |
| `validate.py` | `validate_config()` — cross-checks `core/config.py` for internal consistency (every `PROCESS_ORDER` entry has an `APPS_CONFIG` entry and vice versa, every `patch_source` exists in `PATCH_SOURCES`, every APKMirror/GitHub app has a matching source-module entry) and raises one exception listing everything wrong at once. |

### `core/apk/` — APK-level operations

| File | Purpose |
|---|---|
| `patcher.py` | Builds and runs the `java -jar morphe-desktop.jar patch …` command (patches, arch stripping, `--disable`/`--enable` flags, and keystore signing args if configured, else a warning and the tool's default test key), streams its output line by line through `log.patch_line`, and parses the resulting patched-APK path out of that output. |
| `verify.py` | Pre-patch signature pinning. Extracts the signing certificate(s) from a downloaded APK (unwrapping `.apkm`/`.xapk` bundles to their `base.apk` first if needed) via `androguard`, hashes them with `cryptography`, and compares against `data/known_signatures.json`. No pinned entry → records the fingerprint to `data/pending_signatures.json` and fails loudly. Mismatch → fails loudly ("this may indicate the APK came from an unexpected/untrusted source"). Can be bypassed with `SKIP_SIGNATURE_VERIFY=1` (not recommended). |
| `versions.py` | Parses the patcher CLI's `list-versions` output into `{version, patches}` entries, picks the best one (`pick_latest_version` — most compatible patches, then highest version number), and converts a version string into the dash-separated form APKMirror uses in its URLs. |

### `core/sources/` — where APKs come from

| File | Purpose |
|---|---|
| `apkmirror.py` | Downloads apps from apkmirror.com using a real, fingerprint-resistant Firefox (Camoufox) — launched once and reused across apps. Resolves an app + version to the right APKMirror URL (`APP_SITES` holds each app's org/slug), handles Cloudflare challenge pages and rate-limit cooldowns, navigates the variant/download-confirm page flow, and downloads the file. Clicking is done by reading the download button's own `href` and navigating there directly (`page.goto`) rather than simulating a mouse click, which sidesteps both deceptive ad overlays and layout quirks that a real click can be fooled by. Ad blocking is left enabled (Camoufox's bundled uBlock Origin, with its default ad/privacy filter set) rather than disabled, since it's what keeps those ad overlays from rendering in the first place. |
| `github_apk.py` | Downloads apps that are mirrored as a direct GitHub release asset instead — `APP_TAGS`/`DIRECT_REPOS` map an app to the repo to pull from. Plain HTTP via `core/http.py`, no browser involved. |

### `.github/workflows/`

| File | Purpose |
|---|---|
| `patch.yml` | The pipeline itself — `prepare` → `patch` (matrix) → `finalize` → `cleanup`, as described in [How It Works](#how-it-works). |
| `lint.yml` | Runs `ruff check`, `ruff format --check`, `mypy`, and `pytest` on every push to `main` and every pull request. |
| `dependabot.yml` | Weekly automated PRs for GitHub Actions version bumps. |

### `data/`

| File | Purpose |
|---|---|
| `known_signatures.json` | App name → pinned SHA-256 fingerprint of that app's **original**, pre-patch signing certificate. Edited by hand after manually verifying a new app's fingerprint (see [First run: pending signatures](#4-first-run-pending-signatures)). |
| `pending_signatures.json` | Same shape, auto-populated with fingerprints seen for apps that have no entry in `known_signatures.json` yet. Not trusted for anything — it's a to-review queue. |

### Other files

| File | Purpose |
|---|---|
| `pyproject.toml` | `ruff` (line length 115, `E`/`F`/`I`/`UP`/`B`/`SIM` rule sets), `mypy`, and `pytest` configuration. |
| `requirements.txt` | Direct, unpinned dependencies. |
| `requirements-dev.txt` | The above plus `pytest`, `pytest-asyncio`, `ruff`, `mypy`. |
| `requirements-lock.txt` | Full pinned dependency tree (`pip freeze`), regenerated and committed automatically by the `prepare` job on every run. |
| `tests/` | `pytest` unit tests for `core/retry.py`, `core/validate.py`, `core/apk/versions.py`, and `finalize_release.py`'s asset-matching logic. |
| `.gitignore` | Excludes `__pycache__`, virtualenvs, downloaded APKs, `.env` files, and `diagnostics/`. |

## CI (Lint & Test)

`.github/workflows/lint.yml` runs on every push to `main` and every PR:

```bash
ruff check .
ruff format --check .
mypy core main.py prepare_release.py finalize_release.py commit_signature.py
pytest -v
```

Run the same commands locally (`pip install -r requirements-dev.txt` first) before pushing.

## Configuration Reference

Every environment variable `core/settings.py` reads (matched case-insensitively). The `patch.yml`/`lint.yml` column shows how the live workflow supplies it; anything not listed there is either optional or only needed for a local run.

| Variable | Used by | Notes |
|---|---|---|
| `GITHUB_TOKEN` | `finalize_release.py`, `core/release.py`, `commit_signature.py`'s git push, `camoufox fetch` | Provided automatically by Actions (`secrets.GITHUB_TOKEN`); also passed to the Camoufox fetch step specifically to raise its GitHub API rate limit from 60/hour (unauthenticated) to 5,000/hour. |
| `GITHUB_REPOSITORY` | `core/release.py` | `owner/repo`, set automatically by Actions as `github.repository`. |
| `TARGET_APP` | `main.py` | An app key to process just that one app; `all` (default) processes every key in `PROCESS_ORDER`. The `patch` job sets this to `matrix.app`. |
| `KS_PATH` | `core/apk/patcher.py` | Path to the decoded keystore file; the workflow sets this to `Panemi.keystore` (where the "Setup Keystore" step decodes `KEYSTORE_BASE64` to). |
| `KS_PASSWORD` | `core/apk/patcher.py` | From the `KEYSTORE_PASSWORD` secret. |
| `KS_ALIAS` | `core/apk/patcher.py` | From the `KEY_ALIAS` secret. |
| `KEY_PASSWORD` | `core/apk/patcher.py` | From the `KEY_PASSWORD` secret. |
| `SKIP_SIGNATURE_VERIFY` | `core/apk/verify.py` | Set to skip the pre-patch certificate pin check entirely. Not set by the workflow; local-use escape hatch only. |
| `KNOWN_SIGNATURES_PATH` / `PENDING_SIGNATURES_PATH` | `core/apk/verify.py` | Default to `data/known_signatures.json` / `data/pending_signatures.json`; override only for local testing against a different file. |
| `DISCORD_WEBHOOK_URL` | `core/notify.py` | Optional. |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | `core/notify.py` | Optional, used together. |
| `APPRISE_URLS` | `core/notify.py` | Optional, any other Apprise target(s). |
| `RELEASE_TAG` / `RELEASE_NAME` | `finalize_release.py` | Set by the `finalize` job from `prepare`'s step outputs; required for that script to run at all. |
| `ARTIFACTS_DIR` | `finalize_release.py` | Where downloaded artifacts land; the workflow sets this to `artifacts`. |
| `NO_COLOR` | `core/log.py` | Set (to anything, including empty) to disable colored console output, per the [no-color.org](https://no-color.org) convention. |
| `GITHUB_ACTIONS` | `core/log.py` | Set automatically by Actions; switches on GitHub Actions annotation output for warnings/errors. |
