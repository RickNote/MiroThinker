import asyncio
import json
import logging
from typing import Any, Dict, Optional

import httpx
import json_repair
from openai import AsyncOpenAI

from mcp_config import Config

logger = logging.getLogger("mirothinker")

EXTRACT_INFO_PROMPT = """You are given a piece of content and the requirement of information to extract. Your task is to extract the information specifically requested. Be precise and focus exclusively on the requested information.

INFORMATION TO EXTRACT:
{}

INSTRUCTIONS:
1. Extract the information relevant to the focus above.
2. If the exact information is not found, extract the most closely related details.
3. Be specific and include exact details when available.
4. Clearly organize the extracted information for easy understanding.
5. Do not include general summaries or unrelated content.

CONTENT TO ANALYZE:
{}

EXTRACTED INFORMATION:"""


class LLMClient:
    def __init__(self, config: Config):
        self.config = config

        self.main_client = AsyncOpenAI(
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
        )
        self.main_model = config.llm_model

        if config.summary_llm_mode == "sdk":
            self.summary_mode = "sdk"
            self.summary_client = AsyncOpenAI(
                api_key=config.summary_llm_api_key,
                base_url=config.summary_llm_base_url,
            )
            self.summary_model = config.summary_llm_model
        else:
            self.summary_mode = "direct"
            self.summary_url = config.summary_llm_base_url
            self.summary_model = config.summary_llm_model
            self.summary_api_key = config.summary_llm_api_key

    async def chat(
        self,
        messages: list,
        role: str = "main",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        max_retries: int = 5,
    ) -> str:
        retry_delays = [1, 2, 4, 8, 16][:max_retries]
        last_exception = None

        for attempt, delay in enumerate(retry_delays, 1):
            try:
                if role == "main":
                    response = await self._chat_main(messages, temperature, max_tokens)
                else:
                    response = await self._chat_summary(messages, temperature, max_tokens)

                if len(response) >= 50:
                    tail_50 = response[-50:]
                    repeat_count = response.count(tail_50)
                    if repeat_count > 5:
                        logger.info(f"Repeat detected, retrying (attempt {attempt})")
                        await asyncio.sleep(delay)
                        continue

                return response

            except Exception as e:
                last_exception = e
                if "context length" in str(e).lower() or "longer than the model's context" in str(e):
                    logger.info(f"Context length exceeded, retrying with truncated content (attempt {attempt})")
                    await asyncio.sleep(delay)
                    continue
                if attempt < len(retry_delays):
                    logger.info(f"LLM call failed, retrying in {delay}s (attempt {attempt}): {e}")
                    await asyncio.sleep(delay)
                    continue
                raise

        raise last_exception or Exception("LLM call failed after all retries")

    async def _chat_main(self, messages: list, temperature: float, max_tokens: int) -> str:
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        params = {
            "model": self.main_model,
            "messages": messages,
            "temperature": temperature,
        }

        if "gpt" in self.main_model.lower():
            params["max_completion_tokens"] = max_tokens
            if "gpt-5" in self.main_model.lower() or "gpt5" in self.main_model.lower():
                params["service_tier"] = "flex"
                params["reasoning_effort"] = "minimal"
        else:
            params["max_tokens"] = max_tokens

        response = await self.main_client.chat.completions.create(**params)
        return response.choices[0].message.content or ""

    async def _chat_summary(self, messages: list, temperature: float, max_tokens: int) -> str:
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        if self.summary_mode == "sdk":
            params = {
                "model": self.summary_model,
                "messages": messages,
                "temperature": temperature,
            }
            if "gpt" in self.summary_model.lower():
                params["max_completion_tokens"] = max_tokens
            else:
                params["max_tokens"] = max_tokens

            response = await self.summary_client.chat.completions.create(**params)
            return response.choices[0].message.content or ""
        else:
            return await self._chat_summary_direct(messages, temperature, max_tokens)

    async def _chat_summary_direct(
        self, messages: list, temperature: float, max_tokens: int
    ) -> str:
        if "gpt" in self.summary_model.lower():
            payload = {
                "model": self.summary_model,
                "max_completion_tokens": max_tokens,
                "messages": messages,
            }
            if "gpt-5" in self.summary_model.lower() or "gpt5" in self.summary_model.lower():
                payload["service_tier"] = "flex"
                payload["reasoning_effort"] = "minimal"
        else:
            payload = {
                "model": self.summary_model,
                "max_tokens": max_tokens,
                "messages": messages,
                "temperature": temperature,
            }

        headers = {"Content-Type": "application/json"}
        if self.summary_api_key:
            headers["Authorization"] = f"Bearer {self.summary_api_key}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.summary_url,
                headers=headers,
                json=payload,
                timeout=httpx.Timeout(None, connect=30, read=300),
            )
            response.raise_for_status()
            response_data = response.json()

            if "choices" in response_data and len(response_data["choices"]) > 0:
                return response_data["choices"][0]["message"]["content"] or ""
            elif "error" in response_data:
                raise Exception(f"LLM API error: {response_data['error']}")
            else:
                raise Exception(f"No valid response from LLM API: {response_data}")

    async def chat_json(
        self,
        messages: list,
        role: str = "main",
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> dict:
        if isinstance(messages, str):
            messages_copy = [{"role": "user", "content": messages}]
        else:
            messages_copy = []
            for msg in messages:
                if isinstance(msg, dict):
                    messages_copy.append(msg.copy())
                else:
                    messages_copy.append(msg)

        if messages_copy and isinstance(messages_copy[-1], dict) and "content" in messages_copy[-1]:
            orig_content = messages_copy[-1]["content"]
            messages_copy[-1]["content"] = orig_content + "\n\nPlease respond in JSON format only, no other text."
        else:
            messages_copy.append({"role": "user", "content": "Please respond in JSON format only, no other text."})

        response_text = await self.chat(messages_copy, role, temperature, max_tokens)

        try:
            return json_repair.loads(response_text)
        except Exception:
            try:
                return json_repair.loads("{" + response_text + "}")
            except Exception:
                return {"raw_response": response_text}

    async def extract_info(
        self, content: str, info_to_extract: str, truncate_last_num_chars: int = 0
    ) -> str:
        if truncate_last_num_chars > 0:
            content = content[:-truncate_last_num_chars] + "[...truncated]"

        prompt = EXTRACT_INFO_PROMPT.format(info_to_extract, content)

        retry_delays = [1, 2, 4]

        for attempt, delay in enumerate(retry_delays, 1):
            try:
                result = await self.chat(
                    prompt,
                    role="summary",
                    temperature=1.0,
                    max_tokens=8192,
                    max_retries=2,
                )
                return result
            except Exception as e:
                error_str = str(e)
                if (
                    "Requested token count exceeds the model's maximum context length" in error_str
                    or "longer than the model's context length" in error_str
                ):
                    content = content[:-40960 * attempt] + "[...truncated]"
                    prompt = EXTRACT_INFO_PROMPT.format(info_to_extract, content)
                    await asyncio.sleep(delay)
                    continue
                raise

        raise Exception("Failed to extract info after all retries")
