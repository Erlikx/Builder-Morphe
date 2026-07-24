"""
Matrix job'larından her biri kendi uygulamasının imza sonucunu commit'lemeye
çalışır. Job'lar PARALEL çalıştığı için aynı anda push çakışması (race
condition) olası. Bunu önlemek için:

  1. Bu job'ın ürettiği değer(ler)i hafızada sakla
  2. En güncel main'i çek (başka job'lar bu arada push etmiş olabilir)
  3. Metinsel git merge/rebase yerine SADECE kendi anahtarını en güncel
     JSON'a program içinde birleştir (çakışma riski sıfır)
  4. Push dene, çakışırsa (araya başka biri girdiyse) tekrar dene
"""
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

FILES = ["known_signatures.json", "pending_signatures.json"]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def main():
    app_key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TARGET_APP")
    if not app_key:
        print("APP_KEY belirtilmedi, çıkılıyor.")
        return

    # 1) Bu job'ın kendi ürettiği değerleri sakla (henüz commit'lenmemiş,
    #    yereldeki dosyalarda duruyor)
    local_values = {}
    for fname in FILES:
        data = load(Path(fname))
        if app_key in data:
            local_values[fname] = data[app_key]

    if not local_values:
        print(f"{app_key} için commit edilecek yeni bir imza kaydı yok.")
        return

    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])

    max_retries = 6
    for attempt in range(max_retries):
        run(["git", "fetch", "origin", "main"])
        run(["git", "reset", "--hard", "origin/main"])

        changed = False
        for fname, value in local_values.items():
            path = Path(fname)
            data = load(path)
            if data.get(app_key) != value:
                data[app_key] = value
                path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
                changed = True

        if not changed:
            print(f"{app_key} zaten güncel main'de mevcut, commit atlanıyor.")
            return

        run(["git", "add", *FILES])
        commit = run(["git", "commit", "-m", f"chore: update signature record for {app_key} [skip ci]"])
        if commit.returncode != 0:
            print("Commit edilecek gerçek bir değişiklik yok.")
            return

        push = run(["git", "push", "origin", "HEAD:main"])
        if push.returncode == 0:
            print(f"✅ {app_key} için imza kaydı commit'lendi.")
            return

        wait = random.uniform(2, 6) * (attempt + 1)
        print(f"⚠️ Push çakıştı (deneme {attempt + 1}/{max_retries}), {wait:.0f}s sonra tekrar denenecek...")
        time.sleep(wait)

    print(f"❌ {app_key} için imza kaydı commit'lenemedi (tüm denemeler tükendi).")
    sys.exit(1)


if __name__ == "__main__":
    main()
