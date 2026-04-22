from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── MVP ───────────────────────────────────────────────────────────────────
    resend_api_key: str = ""
    openai_api_key: str = ""
    webhook_secret: str = ""
    db_url: str = "sqlite:///./outreach.db"
    from_email: str = "outreach@longevityintime.org"
    openai_model: str = "gpt-4o"

    # ── Preprint / arXiv ─────────────────────────────────────────────────────
    arxiv_username: str = ""
    arxiv_password: str = ""

    # ── USPTO (patent prior art) ─────────────────────────────────────────────
    uspto_api_key: str = ""

    # ── FDA ESG NextGen ──────────────────────────────────────────────────────
    fda_client_id: str = ""
    fda_client_secret: str = ""


settings = Settings()
