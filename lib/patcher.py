import subprocess
import os
import logging
import asyncio

class MorphePatchEngine:
    """
    Morphe Desktop / Piko Java CLI yamalama sürücüsü.
    Performans için sadece arm64-v8a kütüphanelerini tutar (--striplibs arm64-v8a)
    ve hızlı DEX birleştirme modunu kullanır.
    """
    def __init__(self, jar_path="morphe-desktop-1.11.0-all.jar", keystore_path="Panemi.keystore"):
        self.jar_path = jar_path
        self.keystore_path = keystore_path

    async def apply_patches(self, apk_path, patch_file, arch="arm64-v8a"):
        out_dir = os.path.dirname(apk_path) or "."
        base_name = os.path.basename(apk_path).replace(".apk", "")
        output_apk = os.path.join(out_dir, f"{base_name}-patched.apk")

        cmd = [
            "java", "-jar", self.jar_path,
            "patch",
            "--patches", patch_file,
            "--striplibs", arch,
            "--keystore", self.keystore_path,
            "--keystore-password", os.getenv("KS_PASSWORD", "secret"),
            "--keystore-entry-alias", os.getenv("KS_ALIAS", "key0"),
            "--keystore-entry-password", os.getenv("KEY_PASSWORD", "secret"),
            "-o", output_apk,
            apk_path
        ]

        logging.info(f"🛠️ Yamalama komutu çalıştırılıyor: {apk_path}")
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            return output_apk
        else:
            raise RuntimeError(f"Yamalama başarısız oldu: {stderr.decode()}")
