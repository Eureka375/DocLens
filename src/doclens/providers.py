"""Request profiles for configurable Chat Completions services; no credentials."""

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    profile: str = "auto"

    def parameters(self, endpoint: str, output_tokens: int) -> dict:
        if self.profile not in {"auto", "compatible", "json", "deepseek"}:
            raise ValueError("不支持的 AI 请求格式。")
        deepseek = self.profile == "deepseek" or (
            self.profile == "auto" and urlsplit(endpoint).hostname == "api.deepseek.com")
        parameters = {"max_tokens" if deepseek else "max_completion_tokens": output_tokens}
        if deepseek:
            parameters["thinking"] = {"type": "disabled"}
        if deepseek or self.profile == "json":
            parameters["response_format"] = {"type": "json_object"}
        return parameters
