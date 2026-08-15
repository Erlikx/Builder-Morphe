import os
import re
import subprocess
from pathlib import Path

from .. import log


def patch_apk(
    desktop: str,
    patches: str,
    apk: str,
    exclude: list[str] | None = None,
    enable: list[str] | None = None,
    arch: str = "arm64-v8a",
) -> str:
    log.patch(f"Patching APK & stripping unused architectures ({arch} only)...")

    ks_path = os.environ.get("KS_PATH")
    ks_password = os.environ.get("KS_PASSWORD")
    ks_alias = os.environ.get("KS_ALIAS")
    key_password = os.environ.get("KEY_PASSWORD")

    cmd = ["java", "-jar", desktop, "patch", "--patches", patches]

    if arch:
        cmd += ["--striplibs", arch]

    if ks_path and Path(ks_path).exists() and ks_password and ks_alias and key_password:
        log.lock("Custom keystore detected! Signing with your private key...")
        cmd += [
            "--keystore", ks_path,
            "--keystore-password", ks_password,
            "--keystore-entry-alias", ks_alias,
            "--keystore-entry-password", key_password,
        ]
    else:
        log.warn("Custom keystore credentials missing or file not found. Falling back to default Morphe testkey.")

    for p in (exclude or []):
        cmd += ["--disable", p]

    for p in (enable or []):
        cmd += ["--enable", p]

    cmd.append(apk)

    log.step(f"Executing command: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    output_lines = []
    for line in process.stdout:
        print(log.colorize_patch_line(line), end="", flush=True)
        output_lines.append(line)

    process.wait()
    output = "".join(output_lines)

    if "Applying 0 patches" in output:
        raise RuntimeError("Applying 0 patches. No compatible patch found or version not supported.")

    if process.returncode != 0:
        raise RuntimeError(f"Patch failed (exit {process.returncode}):\n{output}")

    match = re.search(r"INFO:\s+Saved to\s+([^\r\n]+\.apk)", output, re.IGNORECASE)
    if not match:
        raise RuntimeError(f"Cannot find patched APK path in output:\n{output}")

    patched_apk = match.group(1).strip()

    if not Path(patched_apk).exists():
        raise RuntimeError(f"Patched APK does not exist:\n{patched_apk}")

    log.success("Patch done")
    log.saved(f"Output: {patched_apk}")

    return patched_apk
