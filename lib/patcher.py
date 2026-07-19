import os
import subprocess
import shlex

def patch_apk(desktop: str, patches: str, apk: str, extra_args: str = "", arch: str = "arm64-v8a") -> str:
    ks_path = os.environ.get("KS_PATH")
    ks_password = os.environ.get("KS_PASSWORD")
    ks_alias = os.environ.get("KS_ALIAS")
    key_password = os.environ.get("KEY_PASSWORD")

    cmd = ["java", "-jar", desktop, "patch", "--patches", patches]
    
    if arch:
        cmd.extend(["--striplibs", arch])
        
    if ks_path and os.path.exists(ks_path) and ks_password and ks_alias and key_password:
        cmd.extend([
            "--keystore", ks_path,
            "--keystore-password", ks_password,
            "--keystore-entry-alias", ks_alias,
            "--keystore-entry-password", key_password
        ])
        
    if extra_args.strip():
        cmd.extend(shlex.split(extra_args.strip()))
        
    cmd.append(apk)

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = res.stdout + "\n" + res.stderr
        if "Applying 0 patches" in output:
            raise Exception("Applying 0 patches")
        
        import re
        match = re.search(r'(?i)INFO:\s+Saved to\s+([^\r\n]+\.apk)', output)
        if not match:
            raise Exception("Cannot find patched APK path in output")
        
        patched_apk = match.group(1).strip()
        if not os.path.exists(patched_apk):
            raise Exception("Patched APK does not exist")
            
        return patched_apk
    except subprocess.CalledProcessError as e:
        output = e.stdout + "\n" + e.stderr
        if "Applying 0 patches" in output:
            raise Exception("Applying 0 patches")
        raise Exception(f"Patch failed: {e.stderr}")
