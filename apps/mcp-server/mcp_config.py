import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    serper_api_key: str
    serper_base_url: str

    jina_api_key: str
    jina_base_url: str

    llm_api_key: str
    llm_base_url: str
    llm_model: str

    summary_llm_api_key: str
    summary_llm_base_url: str
    summary_llm_model: str
    summary_llm_mode: str  # "sdk" or "direct"

    port: int

    @classmethod
    def from_env(cls) -> "Config":
        serper_api_key = os.environ.get("SERPER_API_KEY", "")
        serper_base_url = os.environ.get("SERPER_BASE_URL", "https://google.serper.dev")

        jina_api_key = os.environ.get("JINA_API_KEY", "")
        jina_base_url = os.environ.get("JINA_BASE_URL", "https://r.jina.ai")

        llm_api_key = os.environ.get("LLM_API_KEY", "")
        llm_base_url = os.environ.get("LLM_BASE_URL", "")
        llm_model = os.environ.get("LLM_MODEL", "")

        summary_llm_api_key = os.environ.get("SUMMARY_LLM_API_KEY") or llm_api_key
        summary_llm_base_url = os.environ.get("SUMMARY_LLM_BASE_URL") or llm_base_url
        summary_llm_model = os.environ.get("SUMMARY_LLM_MODEL") or llm_model

        if summary_llm_base_url.endswith("/chat/completions"):
            summary_llm_mode = "direct"
        else:
            summary_llm_mode = "sdk"

        port = int(os.environ.get("PORT", "8000"))

        config = cls(
            serper_api_key=serper_api_key,
            serper_base_url=serper_base_url,
            jina_api_key=jina_api_key,
            jina_base_url=jina_base_url,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            summary_llm_api_key=summary_llm_api_key,
            summary_llm_base_url=summary_llm_base_url,
            summary_llm_model=summary_llm_model,
            summary_llm_mode=summary_llm_mode,
            port=port,
        )
        config.validate()
        return config

    def validate(self):
        if not self.serper_api_key:
            raise ValueError("SERPER_API_KEY is required")
        if not self.jina_api_key:
            raise ValueError("JINA_API_KEY is required")
        if not self.llm_api_key:
            raise ValueError("LLM_API_KEY is required")
        if not self.llm_base_url:
            raise ValueError("LLM_BASE_URL is required")
        if not self.llm_model:
            raise ValueError("LLM_MODEL is required")
