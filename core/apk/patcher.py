import re
import subprocess
from pathlib import Path

from .. import log
from ..settings import settings


def _redact(cmd: list[str], secrets: set[str]) -> list[str]:
    return ["***" if part in secrets else part for part in cmd]


def patch_apk(
    desktop: str,
    patches: list[str],
    apk: str,
    exclude: list[str] | None = None,
    enable: list[str] | None = None,
    arch: str = "arm64-v8a",
) -> str:
    log.patch(f"Patching APK & stripping unused architectures ({arch} only)...")

    ks_path = settings.ks_path
    ks_password = settings.ks_password.get_secret_value() if settings.ks_password else None
    ks_alias = settings.ks_alias
    key_password = settings.key_password.get_secret_value() if settings.key_password else None

    cmd = ["java", "-jar", desktop, "patch"]

    for p in patches:
        cmd += ["--patches", p]

    if arch:
        cmd += ["--striplibs", arch]

    if ks_path and ks_path.exists() and ks_password and ks_alias and key_password:
        log.lock("Custom keystore detected! Signing with your private key...")
        cmd += [
            "--keystore",
            str(ks_path),
            "--keystore-password",
            ks_password,
            "--keystore-entry-alias",
            ks_alias,
            "--keystore-entry-password",
            key_password,
        ]
    else:
        log.warn("Custom keystore credentials missing or file not found. Falling back to default Morphe testkey.")

    for p in exclude or []:
        cmd += ["--disable", p]

    for p in enable or []:
        cmd += ["--enable", p]

    cmd.append(apk)

    secret_values = {v for v in (ks_password, key_password) if v}
    log.step(f"Executing command: {' '.join(_redact(cmd, secret_values))}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None  # guaranteed by stdout=subprocess.PIPE above

    output_lines = []
    for line in process.stdout:
        log.patch_line(line)
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
