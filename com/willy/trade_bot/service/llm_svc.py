import json
import os
import subprocess
from pathlib import Path

from com.willy.trade_bot.enums.llm_target import LLMTarget

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
    if target == LLMTarget.GEMINI:
        command = ["gemini", "--approval-mode", "yolo", "--sandbox", "false", "--prompt", prompt]
    elif target == LLMTarget.CODEX:
        command = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", prompt]
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
