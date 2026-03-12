from pathlib import Path


def select_model_for_prompt(prompt: str, config_path: str | Path | None = None) -> str:
    from com.willy.trade_bot.service.litellm_route_svc import select_model_for_prompt as _select_model_for_prompt

    return _select_model_for_prompt(prompt, config_path=config_path)


__all__ = ["select_model_for_prompt"]
