import os
import subprocess
from pathlib import Path

def patch_apk(desktop_jar, patches_mpp, apk_path, config, app_name, display_name, out_dir):
    cmd = [
        "java", "-jar", str(desktop_jar), "patch",
        "--patches", str(patches_mpp),
        "--striplibs", "arm64-v8a"
    ]
    
    ks_path = os.environ.get("KS_PATH")
    if ks_path and Path(ks_path).exists():
        cmd.extend([
            "--keystore", ks_path,
            "--keystore-password", os.environ.get("KS_PASSWORD", ""),
            "--keystore-entry-alias", os.environ.get("KS_ALIAS", ""),
            "--keystore-entry-password", os.environ.get("KEY_PASSWORD", "")
        ])
    
    for ex in config.get("exclude", []):
        cmd.extend(["--disable", ex])
    for en in config.get("enable", []):
        cmd.extend(["--enable", en])
        
    cmd.append(str(apk_path))
    
    try:
        print(f"🖥️ EXECUTING COMMAND: java -jar morphe-desktop ... {apk_path.name}")
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            if "Saved to" in line:
                patched_apk = Path(line.split("Saved to")[-1].strip())
                final_name = f"{display_name}-latest.apk"
                final_path = out_dir / final_name
                patched_apk.rename(final_path)
                print(f"✅ Patch done -> {final_name}")
                return final_path
    except subprocess.CalledProcessError as e:
        if "Applying 0 patches" in e.stdout or "Applying 0 patches" in e.stderr:
            print("❌ Uyumlu yama bulunamadı.")
        else:
            print(f"❌ Patch failed:\n{e.stdout}\n{e.stderr}")
    return None
