import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .. import log

_SIG_FILE = Path(os.getenv("KNOWN_SIGNATURES_PATH", Path.cwd() / "data" / "known_signatures.json"))
_PENDING_FILE = Path(os.getenv("PENDING_SIGNATURES_PATH", Path.cwd() / "data" / "pending_signatures.json"))
_DIGEST_RE = re.compile(r"certificate SHA-256 digest:\s*([0-9a-fA-F:]+)")


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            log.warn(f"Could not read/parse {path}, treating as empty.")
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _find_apksigner() -> str:
    env_path = os.getenv("APKSIGNER_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    which = shutil.which("apksigner")
    if which:
        return which

    raise Exception("apksigner not found. Set APKSIGNER_PATH or ensure apksigner is on PATH.")


def get_apk_certificate_fingerprints(apk_path: str) -> list[str]:
    apksigner = _find_apksigner()

    result = subprocess.run(
        [apksigner, "verify", "-v", "--print-certs", apk_path],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise Exception(f"apksigner verify failed for {apk_path}:\n{result.stdout}\n{result.stderr}")

    fingerprints = []
    for match in _DIGEST_RE.finditer(result.stdout):
        fingerprints.append(match.group(1).replace(":", "").lower())

    if not fingerprints:
        raise Exception(f"Could not extract a certificate fingerprint from apksigner output for {apk_path}")

    return fingerprints


def _resolve_verifiable_apk(path: str) -> tuple[str, str | None]:
    if not zipfile.is_zipfile(path):
        if path.lower().endswith(".apk"):
            return path, None
        raise Exception(f"{Path(path).name} is neither a single .apk nor a ZIP-based bundle (.apkm/.xapk) - cannot verify.")

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

        if "AndroidManifest.xml" in names:
            return path, None

        candidates = [n for n in names if n.split("/")[-1] == "base.apk"]
        if not candidates:
            candidates = [n for n in names if n.endswith(".apk")]
        if not candidates:
            raise Exception(f"No verifiable .apk found inside {Path(path).name}.")

        base_name = candidates[0]
        temp_dir = tempfile.mkdtemp(prefix="apkm_verify_")
        extracted_path = zf.extract(base_name, temp_dir)
        return extracted_path, temp_dir


def verify_apk_signature(apk_path: str, app_name: str) -> None:
    if os.getenv("SKIP_SIGNATURE_VERIFY") == "1":
        log.warn(f"SKIP_SIGNATURE_VERIFY=1: skipping signature verification for {app_name}.")
        return

    log.lock(f"Verifying signature: {app_name} ({Path(apk_path).name})")

    verifiable_path, temp_dir = _resolve_verifiable_apk(apk_path)
    try:
        if temp_dir:
            log.info(f"   Bundle detected, extracting and verifying base.apk: {Path(verifiable_path).name}")
        fingerprints = get_apk_certificate_fingerprints(verifiable_path)
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

    known = _load_json(_SIG_FILE)
    pinned = known.get(app_name)

    if pinned is None:
        pending = _load_json(_PENDING_FILE)
        already_pending = pending.get(app_name) == fingerprints[0]
        pending[app_name] = fingerprints[0]
        _save_json(_PENDING_FILE, pending)

        raise Exception(
            f"No pinned signature for {app_name} - APK NOT patched/published.\n"
            f"   Computed fingerprint {'was already' if already_pending else 'has been'} recorded in data/pending_signatures.json: {fingerprints[0]}\n"
            f"   Verify this manually against the developer's official source (Play Store listing, official website, etc.), "
            f"then add it to data/known_signatures.json. Only then will this app be patchable."
        )

    if pinned not in fingerprints:
        raise Exception(
            f"SIGNATURE MISMATCH: expected certificate fingerprint for {app_name} is "
            f"{pinned}, but the downloaded APK's certificate is {fingerprints}. "
            f"This may indicate the APK came from an unexpected/untrusted source. "
            f"Stopping for safety."
        )

    log.success(f"Signature verified: {app_name} ({pinned})")
