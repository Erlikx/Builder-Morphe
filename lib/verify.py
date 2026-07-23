import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

_SIG_FILE = Path(os.getenv("KNOWN_SIGNATURES_PATH", Path.cwd() / "known_signatures.json"))
_PENDING_FILE = Path(os.getenv("PENDING_SIGNATURES_PATH", Path.cwd() / "pending_signatures.json"))
_DIGEST_RE = re.compile(r"certificate SHA-256 digest:\s*([0-9a-fA-F:]+)")


def _find_apksigner() -> str | None:
    """Locate the apksigner binary (Android SDK build-tools)."""
    env_path = os.getenv("APKSIGNER_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    found = shutil.which("apksigner")
    if found:
        return found

    android_home = os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT")
    if android_home:
        build_tools_dir = Path(android_home) / "build-tools"
        if build_tools_dir.is_dir():
            for version_dir in sorted(build_tools_dir.iterdir(), reverse=True):
                candidate = version_dir / "apksigner"
                if candidate.exists():
                    return str(candidate)

    return None


def get_apk_certificate_fingerprints(apk_path: str) -> list[str]:
    """
    Runs `apksigner verify --print-certs` against the APK and returns the
    SHA-256 fingerprints of all signer certificates found (covers v1/v2/v3/v4
    signing schemes — apksigner is the canonical tool for this, unlike
    `keytool` which only understands the legacy v1/JAR signature).
    """
    apksigner = _find_apksigner()
    if not apksigner:
        raise Exception(
            "apksigner bulunamadı. Android SDK build-tools PATH'te olmalı, ya da "
            "APKSIGNER_PATH / ANDROID_HOME ortam değişkenlerinden biri ayarlanmalı "
            "(workflow'da 'android-actions/setup-android' + "
            "'sdkmanager \"build-tools;35.0.0\"' ile kurulabilir)."
        )

    result = subprocess.run(
        [apksigner, "verify", "--print-certs", "-v", str(apk_path)],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        raise Exception(
            f"apksigner imza doğrulaması BAŞARISIZ ({Path(apk_path).name}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    fingerprints = []
    for match in _DIGEST_RE.finditer(result.stdout):
        fp = match.group(1).replace(":", "").lower()
        if fp not in fingerprints:
            fingerprints.append(fp)

    if not fingerprints:
        raise Exception(
            f"apksigner çıktısında sertifika parmak izi bulunamadı ({Path(apk_path).name}):\n"
            f"{result.stdout}"
        )

    return fingerprints


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            print(f"⚠️ {path} okunamadı/bozuk, boş kabul ediliyor.")
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _resolve_verifiable_apk(path: str) -> tuple[str, str | None]:
    """
    .apkm / .xapk gibi split-APK bundle'ları aslında birer ZIP arşividir.
    İçindeki base.apk, Android App Bundle kuralı gereği TÜM split'lerle
    aynı imza sertifikasını taşımak zorundadır - yani base.apk'yı
    doğrulamak, bundle'ın tamamını doğrulamakla eşdeğerdir.

    Zaten tekil bir .apk ise olduğu gibi döner (temp_dir=None).
    Bundle ise base.apk'yı geçici bir klasöre çıkarır ve o klasörün
    yolunu (çağıran taraf işini bitirince silsin diye) döner.
    """
    if path.lower().endswith(".apk"):
        return path, None

    if not zipfile.is_zipfile(path):
        raise Exception(
            f"{Path(path).name} ne tekil bir .apk ne de ZIP tabanlı bir bundle (.apkm/.xapk) - doğrulanamıyor."
        )

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        candidates = [n for n in names if n.split("/")[-1] == "base.apk"]
        if not candidates:
            candidates = [n for n in names if n.endswith(".apk")]
        if not candidates:
            raise Exception(f"{Path(path).name} içinde doğrulanabilecek bir .apk bulunamadı.")

        base_name = candidates[0]
        temp_dir = tempfile.mkdtemp(prefix="apkm_verify_")
        extracted_path = zf.extract(base_name, temp_dir)
        return extracted_path, temp_dir


def verify_apk_signature(apk_path: str, app_name: str) -> None:
    """
    İndirilen (henüz patchlenmemiş) APK'nın (veya .apkm/.xapk bundle'ının
    içindeki base.apk'nın) imza sertifikası parmak izini known_signatures.json
    içinde ONAYLI (pinned) olarak kayıtlı değerle karşılaştırır.

    - known_signatures.json'da bir kayıt VARSA: parmak izi eşleşmezse işlem
      güvenlik nedeniyle DURDURULUR (olası tedarik zinciri saldırısı /
      beklenmedik kaynaktan gelen sahte APK).
    - known_signatures.json'da bir kayıt YOKSA: APK artık otomatik olarak
      güvenilip yamalanıp yayınlanmıyor. Hesaplanan parmak izi
      pending_signatures.json'a yazılır ve işlem bu uygulama için
      DURDURULUR. Bu parmak izini geliştiricinin resmi kaynağıyla
      (Play Store girişi, resmi web sitesi vb.) elle karşılaştırıp
      doğruladıktan sonra known_signatures.json'a taşıman gerekir - ancak
      o zaman bu uygulama yamalanabilir hale gelir.

    SKIP_SIGNATURE_VERIFY=1 ortam değişkeni ile (yalnızca yerel/geliştirme
    amaçlı) bu kontrol tamamen atlanabilir.
    """
    if os.getenv("SKIP_SIGNATURE_VERIFY") == "1":
        print(f"⚠️ SKIP_SIGNATURE_VERIFY=1: {app_name} için imza doğrulaması atlanıyor.")
        return

    print(f"🔏 İmza doğrulanıyor: {app_name} ({Path(apk_path).name})")

    verifiable_path, temp_dir = _resolve_verifiable_apk(apk_path)
    try:
        if temp_dir:
            print(f"   ↳ Bundle tespit edildi, base.apk çıkarılıp doğrulanıyor: {Path(verifiable_path).name}")
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
            f"🚫 {app_name} için onaylı (pinned) bir imza kaydı yok - APK YAMALANMADI/YAYINLANMADI.\n"
            f"   Hesaplanan parmak izi pending_signatures.json'a "
            f"{'zaten kayıtlıydı' if already_pending else 'kaydedildi'}: {fingerprints[0]}\n"
            f"   Bunu geliştiricinin resmi kaynağıyla (Play Store girişi, resmi web sitesi vb.) "
            f"ELLE karşılaştırıp doğrula, sonra known_signatures.json'a ekle. "
            f"Ancak o zaman bu uygulama yamalanabilir."
        )

    if pinned not in fingerprints:
        raise Exception(
            f"🚨 İMZA UYUŞMAZLIĞI: {app_name} için beklenen sertifika parmak izi "
            f"{pinned}, indirilen APK'nın sertifikası ise {fingerprints}. "
            f"Bu, APK'nın beklenmedik/güvenilmeyen bir kaynaktan geldiğini gösterebilir. "
            f"İşlem güvenlik nedeniyle durduruldu."
        )

    print(f"✅ İmza doğrulandı: {app_name} ({pinned})")
