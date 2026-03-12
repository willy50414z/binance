from __future__ import annotations

import os
from pathlib import Path

from langsmith import Client


def _load_properties(file_path: Path) -> dict[str, str]:
    if not file_path.exists():
        raise FileNotFoundError(f"application properties not found: {file_path}")

    properties: dict[str, str] = {}
    for line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue

        delimiter = "=" if "=" in stripped else ":" if ":" in stripped else None
        if delimiter is None:
            continue

        key, value = stripped.split(delimiter, 1)
        properties[key.strip()] = value.strip()
    return properties


def resolve_workspace_and_application_ini(
    *,
    application_ini_path: str | Path | None,
    reference_file: str | Path,
) -> tuple[Path, Path]:
    def _find_workspace(start: Path) -> tuple[Path, Path] | None:
        start_resolved = start.resolve()
        for candidate_root in [start_resolved, *start_resolved.parents]:
            candidate_ini = candidate_root / "com" / "willy" / "trade_bot" / "application.ini"
            if candidate_ini.exists():
                return candidate_root, candidate_ini
        return None

    if application_ini_path is not None:
        ini_path = Path(application_ini_path).expanduser()
        if not ini_path.is_absolute():
            ini_path = (Path.cwd() / ini_path).resolve()
        else:
            ini_path = ini_path.resolve()

        if not ini_path.exists():
            raise FileNotFoundError(f"application properties not found: {ini_path}")

        from_ini = _find_workspace(ini_path.parent)
        if from_ini is not None:
            return from_ini
        return ini_path.parent, ini_path

    candidates = [
        Path.cwd(),
        Path(reference_file).resolve().parent,
    ]
    for candidate in candidates:
        found = _find_workspace(candidate)
        if found is not None:
            return found

    raise FileNotFoundError(
        "application properties not found. "
        "Please set `application_ini_path`, or run from repo root with "
        "`com/willy/trade_bot/application.ini` present."
    )


def configure_langsmith(*, application_ini_path: Path, default_project: str) -> tuple[Client, str]:
    properties = _load_properties(application_ini_path)
    api_key = (os.getenv("LANGSMITH_API_KEY") or properties.get("langsmith.apikey", "")).strip()
    if not api_key:
        raise ValueError(
            f"`langsmith.apikey` is missing in {application_ini_path}. "
            "Please set it before running LangSmith tracing."
        )

    project = (os.getenv("LANGSMITH_PROJECT") or properties.get("langsmith.project", default_project)).strip()
    endpoint = (os.getenv("LANGSMITH_ENDPOINT") or properties.get("langsmith.endpoint", "")).strip()

    os.environ["LANGSMITH_API_KEY"] = api_key
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = project
    if endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = endpoint

    client = Client(api_key=api_key, api_url=endpoint or None, auto_batch_tracing=False)
    return client, project
