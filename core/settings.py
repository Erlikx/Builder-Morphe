"""Centralized runtime configuration, backed by pydantic-settings.

Every environment variable the pipeline reads is declared here once, with
its type and default, instead of being scattered as ad-hoc os.environ.get()
calls across a dozen modules. Env vars are matched case-insensitively
(KS_PATH, ks_path, Ks_Path all bind to `ks_path`), so every existing GitHub
Actions secret/env name keeps working unchanged.

One shared `settings` singleton is imported by both the core/ library code
and the top-level scripts (main.py, finalize_release.py, prepare_release.py,
commit_signature.py) - and those scripts each only need a subset of these
fields, so nothing here is a required field. Anything that's truly required
for a given entrypoint (e.g. RELEASE_TAG for finalize_release.py) is checked
explicitly at the point of use instead, the same way the original code did
with plain os.environ lookups.
"""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- GitHub API access -------------------------------------------------
    github_token: SecretStr = SecretStr("")
    github_repository: str = ""

    # --- main.py / commit_signature.py -------------------------------------
    target_app: str = "all"

    # --- Custom signing keystore (core/apk/patcher.py) ----------------------
    ks_path: Path | None = None
    ks_password: SecretStr | None = None
    ks_alias: str | None = None
    key_password: SecretStr | None = None

    # --- Signature pinning (core/apk/verify.py) -----------------------------
    skip_signature_verify: bool = False
    known_signatures_path: Path = Field(default_factory=lambda: Path.cwd() / "data" / "known_signatures.json")
    pending_signatures_path: Path = Field(default_factory=lambda: Path.cwd() / "data" / "pending_signatures.json")

    # --- Notifications (core/notify.py) -------------------------------------
    discord_webhook_url: SecretStr = SecretStr("")
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""
    # Any additional apprise:// service URL(s) - Slack, ntfy, Matrix, email,
    # anything from https://github.com/caronc/apprise#supported-notifications
    # - separated by whitespace, a comma, or newlines. Optional; no code
    # change is ever needed to add a new notification target through this.
    apprise_urls: SecretStr = SecretStr("")

    # --- Logging (core/log.py) ----------------------------------------------
    # NO_COLOR: presence (any value, including empty) disables color, per the
    # https://no-color.org convention, so this stays a raw optional string
    # rather than a bool - that's the only way to tell "set but empty" apart
    # from "not set at all".
    no_color: str | None = None
    github_actions: bool = False

    # --- finalize_release.py -------------------------------------------------
    release_tag: str | None = None
    release_name: str | None = None
    artifacts_dir: Path = Path("artifacts")


settings = Settings()
