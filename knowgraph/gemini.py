"""Native Gemini transport; keys stay in headers and provider errors are sanitized."""

from urllib.parse import quote

import httpx
from openai import APIConnectionError, APITimeoutError

GEMINI_NATIVE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(Exception):
    def __init__(self, status: int, reason: str = ""):
        self.status = status
        self.reason = (
            reason
            if reason
            in {
                "API_KEY_INVALID",
                "API_KEY_EXPIRED",
                "API_KEY_SERVICE_BLOCKED",
                "BILLING_DISABLED",
                "SERVICE_DISABLED",
            }
            else ""
        )
        super().__init__(f"Gemini HTTP {status}")


class GeminiClient:
    def __init__(self, api_key: str, transport=None):
        self.http = httpx.Client(headers={"x-goog-api-key": api_key}, transport=transport)

    def generate(self, model: str, payload: dict, timeout: float) -> dict:
        url = f"{GEMINI_NATIVE_URL}/models/{quote(model.removeprefix('models/'), safe='')}:generateContent"
        try:
            response = self.http.post(url, json=payload, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise APITimeoutError(request=exc.request) from None
        except httpx.RequestError as exc:
            raise APIConnectionError(request=exc.request) from None
        if response.is_error:
            reason = ""
            try:
                error = response.json().get("error", {})
                for detail in error.get("details", []):
                    if isinstance(detail, dict) and detail.get("reason"):
                        reason = detail["reason"]
                        break
            except (ValueError, AttributeError, TypeError):
                pass
            raise GeminiError(response.status_code, reason)
        return response.json()

    def close(self):
        self.http.close()
