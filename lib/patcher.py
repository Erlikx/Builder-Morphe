import subprocess
import os
import re
import logging
import shlex

logger = logging.getLogger(__name__)

def patch_apk(desktop, patches, apk, extra_args="", arch="arm64-v8a"):
    logger.info(f"\n🛠️ Patching APK & Stripping unused architectures ({arch} only)...\n")

    ks_path = os.environ.get("KS_PATH")
    ks_password = os.environ.get("KS_PASSWORD")
    ks_alias = os.environ.get("KS_ALIAS")
    key_password = os.environ.get("KEY_PASSWORD")

    cmd = [
        "java", "-jar", desktop,
        "patch",
        "--patches", patches
    ]

    if arch:
        cmd.extend(["--striplibs", arch])

    if ks_path and os.path.exists(ks_path) and ks_password and ks_alias and key_password:
        logger.info("🔑 Custom keystore detected! Signing with your private key...")
        cmd.extend([
            "--keystore", ks_path,
            "--keystore-password", ks_password,
            "--keystore-entry-alias", ks_alias,
            "--keystore-entry-password", key_password
        ])
    else:
        logger.info("⚠️ Custom keystore credentials missing or file not found. Falling back to default Morphe testkey.")

    if extra_args and extra_args.strip():
        cmd.extend(shlex.split(extra_args))

    cmd.append(apk)

    logger.info(f"🖥️ EXECUTING COMMAND: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        output = result.stdout + result.stderr
        logger.info(output)

        if "Applying 0 patches" in output:
            raise Exception("Applying 0 patches. Uyumlu yama bulunamadı veya sürüm desteklenmiyor.")

        match = re.search(r"INFO:\s+Saved to\s+([^\r\n]+\.apk)", output, re.IGNORECASE)
        if not match:
            raise Exception(f"Cannot find patched APK path in output:\n{output}")

        patched_apk = match.group(1).strip()
        if not os.path.exists(patched_apk):
            raise Exception(f"Patched APK does not exist:\n{patched_apk}")

        logger.info("\n✅ Patch done")
        logger.info(f"📦 Output: {patched_apk}")
        return patched_apk

    except subprocess.TimeoutExpired:
        raise Exception("Patch process timed out")
    except Exception as e:
        raise Exception(f"Patch failed: {str(e)}")
