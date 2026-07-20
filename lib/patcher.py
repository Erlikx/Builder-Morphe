import os
import re
import subprocess
from pathlib import Path

def patch_apk(desktop_jar: str, patches_mpp: str, apk_path: str, extra_args: str = "", arch: str = "arm64-v8a") -> str:
    print(f"\n🛠️ Patching APK & Stripping unused architectures ({arch} only)...\n")

    ks_path = os.getenv("KS_PATH")
    ks_password = os.getenv("KEYSTORE_PASSWORD")
    ks_alias = os.getenv("KEY_ALIAS")
    key_password = os.getenv("KEY_PASSWORD")

    cmd = [
        "java", "-jar", str(desktop_jar), "patch",
        "--patches", str(patches_mpp)
    ]

    if arch:
        cmd.extend(["--striplibs", arch])

    if ks_path and Path(ks_path).exists() and ks_password and ks_alias and key_password:
        print("🔑 Custom keystore detected! Signing with your private key...")
        cmd.extend([
            "--keystore", ks_path,
            "--keystore-password", ks_password,
            "--keystore-entry-alias", ks_alias,
            "--keystore-entry-password", key_password
        ])
    else:
        print("⚠️ Custom keystore credentials missing or file not found. Falling back to default Morphe testkey.")

    if extra_args.strip():
        import shlex
        cmd.extend(shlex.split(extra_args.strip()))

    cmd.append(str(apk_path))

    _SENSITIVE_FLAGS = {"--keystore-password", "--keystore-entry-password"}
    safe_cmd = []
    mask_next = False
    for part in cmd:
        if mask_next:
            safe_cmd.append("****")
            mask_next = False
        else:
            safe_cmd.append(part)
        if part in _SENSITIVE_FLAGS:
            mask_next = True
    print(f"🖥️ EXECUTING: {' '.join(safe_cmd)}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            env={**os.environ, "JAVA_TOOL_OPTIONS": "-Dfile.encoding=UTF8"}
        )
        print(result.stdout)

        if "Applying 0 patches" in result.stdout or "Applying 0 patches" in result.stderr:
            raise Exception("Applying 0 patches. Uyumlu yama bulunamadı veya sürüm desteklenmiyor.")

        match = re.search(r"INFO:\s+Saved to\s+([^\r\n]+\.apk)", result.stdout, re.IGNORECASE)
        if not match:
            raise Exception(f"Cannot find patched APK path in output:\n{result.stdout}")

        patched_apk = match.group(1).strip()
        if not Path(patched_apk).exists():
            raise Exception(f"Patched APK does not exist:\n{patched_apk}")

        print("\n✅ Patch done")
        print(f"📦 Output: {patched_apk}")
        return patched_apk

    except subprocess.CalledProcessError as e:
        if "Applying 0 patches" in e.stdout or "Applying 0 patches" in e.stderr:
            raise Exception("Applying 0 patches. Uyumlu yama bulunamadı veya sürüm desteklenmiyor.")
        raise Exception(f"Patch failed: {e.stderr or e.stdout or str(e)}")
