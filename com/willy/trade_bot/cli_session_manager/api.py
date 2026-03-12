from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from com.willy.trade_bot.cli_session_manager.engine import SessionFlowEngine
from com.willy.trade_bot.cli_session_manager.models import BaseSessionStrategy, StrategyWorkspace


def _load_strategy_class(import_path: str) -> type[BaseSessionStrategy]:
    module_name, _, class_name = import_path.rpartition(".")
    if not module_name or not class_name:
        raise ValueError(f"Invalid strategy import path: {import_path}")
    module = importlib.import_module(module_name)
    strategy_cls = getattr(module, class_name)
    if not issubclass(strategy_cls, BaseSessionStrategy):
        raise TypeError(f"{import_path} is not a BaseSessionStrategy subclass")
    return strategy_cls


def _result_to_dict(result) -> dict[str, Any]:
    return {
        "stopped_early": result.stopped_early,
        "touched_statuses": sorted(result.touched_statuses),
        "visited_nodes": list(result.visited_nodes),
        "sessions": [
            {
                "step_name": record.step_name,
                "llm_target": record.llm_target.name,
                "file_path": str(record.file_path),
                "created_at": record.created_at.isoformat(),
            }
            for record in result.sessions
        ],
    }


def create_app():
    try:
        from flask import Flask, jsonify, request
    except ImportError as exc:
        raise RuntimeError(
            "Flask is not installed. Install it first, for example: pip install flask"
        ) from exc

    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/session-flow/run")
    def run_from_config():
        payload = request.get_json(force=True, silent=False)
        engine = SessionFlowEngine.from_dict(payload)
        result = engine.run()
        graph_path = engine.export_graph()
        return jsonify(
            {
                "workspace": str(engine.workspace.strategy_dir),
                "graph_path": str(graph_path),
                "result": _result_to_dict(result),
            }
        )

    @app.post("/session-flow/run-strategy")
    def run_from_strategy():
        payload = request.get_json(force=True, silent=False)
        import_path = payload["strategy_class"]
        strategy_cls = _load_strategy_class(import_path)
        strategy = strategy_cls()
        engine = SessionFlowEngine.from_strategy(strategy)
        result = engine.run()
        graph_path = engine.export_graph()
        return jsonify(
            {
                "workspace": str(engine.workspace.strategy_dir),
                "graph_path": str(graph_path),
                "result": _result_to_dict(result),
            }
        )

    @app.post("/session-flow/export-graph")
    def export_graph():
        payload = request.get_json(force=True, silent=False)
        engine = SessionFlowEngine.from_dict(payload["flow"])
        file_stem = payload.get("file_stem")
        graph_path = engine.export_graph(file_stem=file_stem)
        return jsonify({"graph_path": str(graph_path)})

    @app.post("/session-flow/status/get")
    def get_status():
        payload = request.get_json(force=True, silent=False)
        workspace = StrategyWorkspace.from_strategy_dir(payload["strategy_dir"])
        status_name = payload["status_name"]
        status_path = workspace.status_file(status_name)
        return jsonify(
            {
                "status_name": status_name,
                "exists": status_path.exists(),
                "path": str(status_path),
                "content": status_path.read_text(encoding="utf-8") if status_path.exists() else "",
            }
        )

    @app.post("/session-flow/status/set")
    def set_status():
        payload = request.get_json(force=True, silent=False)
        workspace = StrategyWorkspace.from_strategy_dir(payload["strategy_dir"])
        status_name = payload["status_name"]
        content = payload.get("content", "")
        status_path = workspace.status_file(status_name)
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(content, encoding="utf-8")
        return jsonify({"status_name": status_name, "path": str(status_path), "written": True})

    @app.post("/session-flow/status/clear")
    def clear_status():
        payload = request.get_json(force=True, silent=False)
        workspace = StrategyWorkspace.from_strategy_dir(payload["strategy_dir"])
        status_name = payload["status_name"]
        status_path = workspace.status_file(status_name)
        existed = status_path.exists()
        if existed:
            status_path.unlink()
        return jsonify({"status_name": status_name, "path": str(status_path), "cleared": existed})

    @app.get("/session-flow/status/list")
    def list_statuses():
        strategy_dir = request.args["strategy_dir"]
        workspace = StrategyWorkspace.from_strategy_dir(strategy_dir)
        workspace.ensure_dirs()
        items = []
        for path in sorted(workspace.status_dir.glob("*.txt")):
            items.append({"name": path.stem, "path": str(path)})
        return jsonify({"strategy_dir": str(workspace.strategy_dir), "statuses": items})

    @app.post("/session-flow/config/export")
    def export_config():
        payload = request.get_json(force=True, silent=False)
        engine = SessionFlowEngine.from_dict(payload["flow"])
        output_path = Path(payload["output_path"])
        saved_path = engine.export_config(output_path)
        return jsonify({"output_path": str(saved_path)})

    return app


def main():
    app = create_app()
    app.run(host="0.0.0.0", port=8787, debug=False)


if __name__ == "__main__":
    main()
