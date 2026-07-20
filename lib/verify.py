import json
import os
import re
import shutil
import subprocess
from pathlib import Path

_SIG_FILE = Path(os.getenv("KNOWN_SIGNATURES_PATH", Path.cwd() / "known_signatures.json"))
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


def _load_known() -> dict:
    if _SIG_FILE.exists():
        try:
            return json.loads(_SIG_FILE.read_text())
        except Exception:
            print(f"⚠️ {_SIG_FILE} okunamadı/bozuk, boş kabul ediliyor.")
    return {}


def _save_known(data: dict) -> None:
    _SIG_FILE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def verify_apk_signature(apk_path: str, app_name: str) -> None:
    """
    İndirilen (henüz patchlenmemiş) APK'nın imza sertifikası parmak izini
    daha önce kaydedilmiş (pinned) değerle karşılaştırır.

    - İlk çalıştırmada: parmak izi hesaplanır, known_signatures.json'a
      kaydedilir (trust-on-first-use) ve bariz bir uyarı basılır. Bu ilk
      kayıt OTOMATİK GÜVENLİ DEMEK DEĞİLDİR — geliştiricinin resmi
      kaynağıyla (Play Store girişi, resmi web sitesi vb.) elle
      karşılaştırılmalıdır.
    - Sonraki çalıştırmalarda: hesaplanan parmak izi kayıtlı değerle
      eşleşmezse işlem güvenlik nedeniyle DURDURULUR (olası tedarik
      zinciri saldırısı / beklenmedik kaynaktan gelen sahte APK).

    SKIP_SIGNATURE_VERIFY=1 ortam değişkeni ile (yalnızca yerel/geliştirme
    amaçlı) bu kontrol atlanabilir.
    """
    if os.getenv("SKIP_SIGNATURE_VERIFY") == "1":
        print(f"⚠️ SKIP_SIGNATURE_VERIFY=1: {app_name} için imza doğrulaması atlanıyor.")
        return

    print(f"🔏 İmza doğrulanıyor: {app_name} ({Path(apk_path).name})")
    fingerprints = get_apk_certificate_fingerprints(apk_path)
    known = _load_known()
    pinned = known.get(app_name)

    if pinned is None:
        known[app_name] = fingerprints[0]
        _save_known(known)
        print(
            f"🆕 {app_name} için imza ilk kez görüldü ve kaydedildi: {fingerprints[0]}\n"
            f"   ⚠️ Bu parmak izini geliştiricinin resmi kaynağıyla elle karşılaştırıp "
            f"doğrulamadan bu APK'ya güvenme. Doğruladıktan sonra known_signatures.json "
            f"dosyasını commit'le, böylece sonraki çalıştırmalar buna göre korunur."
        )
        return

    if pinned not in fingerprints:
        raise Exception(
            f"🚨 İMZA UYUŞMAZLIĞI: {app_name} için beklenen sertifika parmak izi "
            f"{pinned}, indirilen APK'nın sertifikası ise {fingerprints}. "
            f"Bu, APK'nın beklenmedik/güvenilmeyen bir kaynaktan geldiğini gösterebilir. "
            f"İşlem güvenlik nedeniyle durduruldu."
        )

    print(f"✅ İmza doğrulandı: {app_name} ({pinned})")
