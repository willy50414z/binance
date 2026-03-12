from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

CODE_MODEL = "gpt-4o-mini"
GENERAL_MODEL = "gpt-4o"


@dataclass(slots=True)
class LiteLLMRouterConfig:
    router_model: str = os.getenv("LITELLM_ROUTER_MODEL", GENERAL_MODEL)
    temperature: float = float(os.getenv("LITELLM_ROUTER_TEMPERATURE", "0"))


def _extract_text(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        return str(response).strip()

    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None and isinstance(first_choice, dict):
        message = first_choice.get("message")
    if message is None:
        return str(response).strip()

    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
            elif hasattr(item, "text"):
                text_parts.append(str(item.text))
        return "\n".join(part.strip() for part in text_parts if part and part.strip())
    return str(response).strip()


def _build_router_messages(prompt: str) -> list[dict[str, str]]:
    system_prompt = (
        "You are a model router.\n"
        "Your job is to choose the best target model for the user's prompt.\n"
        f"Rule 1: If the task is code-related, return exactly '{CODE_MODEL}'.\n"
        f"Rule 2: Otherwise, return exactly '{GENERAL_MODEL}'.\n"
        "Treat code-related tasks broadly: writing code, modifying code, debugging, refactoring, "
        "explaining source code, reviewing code, generating tests, shell scripting, SQL writing, "
        "regex construction, API implementation, and code architecture discussions are all code-related.\n"
        "Return only the model name. Do not explain your reasoning."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]


def normalize_selected_model(raw_text: str) -> str:
    normalized = raw_text.strip().lower()
    if normalized == CODE_MODEL.lower():
        return CODE_MODEL
    if normalized == GENERAL_MODEL.lower():
        return GENERAL_MODEL
    raise ValueError(f"Router returned unexpected model: {raw_text}")


def select_model(prompt: str, *, config: LiteLLMRouterConfig | None = None) -> str:
    if not prompt.strip():
        raise ValueError("prompt must not be empty.")

    runtime_config = config or LiteLLMRouterConfig()

    try:
        from litellm import completion
    except ImportError as exc:
        raise RuntimeError(
            "litellm is not installed. Install it first, for example: pip install litellm"
        ) from exc

    response = completion(
        model=runtime_config.router_model,
        messages=_build_router_messages(prompt),
        temperature=runtime_config.temperature,
    )
    return normalize_selected_model(_extract_text(response))


def _read_prompt(args: argparse.Namespace) -> str:
    if args.prompt:
        return args.prompt
    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as file:
            return file.read()
    raise ValueError("Provide a prompt argument or --prompt-file.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select the best model for a prompt: code-related tasks use gpt-4o-mini, other tasks use gpt-4o."
    )
    parser.add_argument("prompt", nargs="?", help="Prompt text.")
    parser.add_argument("--prompt-file", help="Read prompt text from a file.")
    args = parser.parse_args()

    prompt = _read_prompt(args)
    selected_model = select_model(prompt)
    print(selected_model)


if __name__ == "__main__":
    main()
