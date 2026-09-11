"""APK signing-certificate verification.

Pins each app to a known-good certificate SHA-256 fingerprint (recorded in
data/known_signatures.json) and refuses to continue if a freshly downloaded
APK's certificate doesn't match that pin - this is what stops a
compromised/rogue mirror from ever reaching the patch step undetected.

Why androguard *and* cryptography, not one or the other: the hard part of
this problem is locating and extracting the signer certificate(s) from the
APK's v1/v2/v3 signing block(s), which is an Android-specific binary
container format - that's what androguard understands. What comes back is
then just an X.509 certificate, and hashing its DER encoding is
cryptography's job. androguard actually already depends on and uses
cryptography for that half internally, so using both together (rather than
reimplementing APK signing-block parsing by hand on top of cryptography
alone) is the natural fit, not a compromise between the two options.

androguard's own certificate return type has changed across major versions
(asn1crypto objects, then pyasn1, now cryptography.x509.Certificate) -
`_cert_der_bytes` normalizes whatever comes back down to raw DER bytes
before hashing, rather than depending on a specific attribute name, so this
keeps working across androguard upgrades.
"""

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from androguard.core.apk import APK
from cryptography.hazmat.primitives.serialization import Encoding

from .. import log
from ..settings import settings


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            log.warn(f"Could not read/parse {path}, treating as empty.")
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _cert_der_bytes(cert) -> bytes:
    """Normalize a certificate object from APK.get_certificates() down to
    raw DER bytes, regardless of which X.509 backend that androguard
    happens to use internally."""
    if isinstance(cert, bytes | bytearray):
        return bytes(cert)
    if hasattr(cert, "public_bytes"):  # cryptography.x509.Certificate (current androguard)
        return cert.public_bytes(Encoding.DER)
    if hasattr(cert, "dump"):  # asn1crypto.x509.Certificate (older androguard)
        return cert.dump()
    raise TypeError(f"Unrecognized certificate object from androguard: {type(cert)!r}")


def get_apk_certificate_fingerprints(apk_path: str) -> list[str]:
    apk = APK(apk_path)
    certs = apk.get_certificates()

    if not certs:
        raise Exception(f"androguard found no signing certificate in {apk_path} - is it actually signed?")

    return [hashlib.sha256(_cert_der_bytes(cert)).hexdigest() for cert in certs]


def _resolve_verifiable_apk(path: str) -> tuple[str, str | None]:
    if not zipfile.is_zipfile(path):
        if path.lower().endswith(".apk"):
            return path, None
        raise Exception(
            f"{Path(path).name} is neither a single .apk nor a ZIP-based bundle (.apkm/.xapk) - cannot verify."
        )

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
    if settings.skip_signature_verify:
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

    known = _load_json(settings.known_signatures_path)
    pinned = known.get(app_name)

    if pinned is None:
        pending = _load_json(settings.pending_signatures_path)
        already_pending = pending.get(app_name) == fingerprints[0]
        pending[app_name] = fingerprints[0]
        _save_json(settings.pending_signatures_path, pending)

        raise Exception(
            f"No pinned signature for {app_name} - APK NOT patched/published.\n"
            f"   Computed fingerprint {'was already' if already_pending else 'has been'} recorded in "
            f"data/pending_signatures.json: {fingerprints[0]}\n"
            f"   Verify this manually against the developer's official source (Play Store listing, official "
            f"website, etc.), then add it to data/known_signatures.json. Only then will this app be patchable."
        )

    if pinned not in fingerprints:
        raise Exception(
            f"SIGNATURE MISMATCH: expected certificate fingerprint for {app_name} is "
            f"{pinned}, but the downloaded APK's certificate is {fingerprints}. "
            f"This may indicate the APK came from an unexpected/untrusted source. "
            f"Stopping for safety."
        )

    log.success(f"Signature verified: {app_name} ({pinned})")
