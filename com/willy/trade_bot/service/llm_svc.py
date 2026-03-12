import json
import os
import subprocess
from pathlib import Path

from com.willy.trade_bot.enums.llm_target import LLMTarget
from com.willy.trade_bot.service.litellm_route_svc import select_model_for_prompt

_ALLOW_ALL_OPENCODE_PERMISSION = {
    "bash": "allow",
    "read": "allow",
    "edit": "allow",
    "task": "allow",
    "glob": "allow",
    "grep": "allow",
    "list": "allow",
    "external_directory": "allow",
    "todowrite": "allow",
    "todoread": "allow",
    "question": "allow",
    "webfetch": "allow",
    "websearch": "allow",
    "codesearch": "allow",
    "lsp": "allow",
    "doom_loop": "allow",
    "skill": "allow",
}
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_TARGET_ROUTER_CONFIG = {
    LLMTarget.GEMINI: _CONFIG_DIR / "llm_model_router_gemini.json",
    LLMTarget.CODEX: _CONFIG_DIR / "llm_model_router_codex.json",
}


def _select_model(target: LLMTarget, prompt: str) -> str | None:
    config_path = _TARGET_ROUTER_CONFIG.get(target)
    if config_path is None:
        return None
    return select_model_for_prompt(prompt, config_path=config_path)


def run_once(
        target: LLMTarget,
        prompt: str,
        *,
        cwd: str | None = None,
        timeout: float | None = None,
        encoding: str = "utf-8",
) -> str:
    if not prompt.strip():
        raise ValueError("prompt must not be empty.")

    work_dir = str(Path(cwd).resolve()) if cwd else None
    model_name = _select_model(target, prompt)
    if target == LLMTarget.GEMINI:
        command = ["gemini", "--approval-mode", "yolo", "--sandbox", "false"]
        if model_name:
            command.extend(["--model", model_name])
        command.extend(["--prompt", prompt])
    elif target == LLMTarget.CODEX:
        command = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox"]
        if model_name:
            command.extend(["--model", model_name])
        command.append(prompt)
    elif target == LLMTarget.OPENCODE:
        command = ["opencode", "run"]
        command.extend(["--dir", work_dir or str(Path.cwd())])
        command.append(prompt)
    else:
        raise ValueError(f"Unsupported LLM target: {target}")

    env = dict(os.environ)
    if target == LLMTarget.OPENCODE:
        env.setdefault("OPENCODE_PERMISSION", json.dumps(_ALLOW_ALL_OPENCODE_PERMISSION))

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding=encoding,
        cwd=work_dir,
        env=env,
        timeout=timeout,
    )
    if completed.returncode != 0:
        stderr_text = (completed.stderr or "").strip()
        raise RuntimeError(
            f"LLM command failed with exit code {completed.returncode}. stderr: {stderr_text}"
        )
    return (completed.stdout or "").strip()
