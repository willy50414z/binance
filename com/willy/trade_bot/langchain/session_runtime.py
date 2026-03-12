from __future__ import annotations

import os
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableLambda
from langchain_core.tracers import LangChainTracer
from langsmith import Client

from com.willy.trade_bot.enums import LLMTarget
from com.willy.trade_bot.langchain.langsmith_support import (
    configure_langsmith,
    resolve_workspace_and_application_ini,
)
from com.willy.trade_bot.langchain.prompt_builder import LangChainPromptBuilder
from com.willy.trade_bot.service import llm_svc


class LangChainSessionRuntime:
    def __init__(
        self,
        strategy_name: str,
        version: str,
        discussion_loop: int = 3,
        current_depth: int = 0,
        max_depth: int = 5,
        max_workers: int = 2,
        graph_state: dict | None = None,
        graph_lock: threading.Lock | None = None,
        graph_output_dir: str | None = None,
        application_ini_path: str | Path | None = None,
        langsmith_client: Client | None = None,
        langsmith_project: str | None = None,
    ):
        self.version = version
        self.discussion_loop = discussion_loop
        self.current_depth = current_depth
        self.max_depth = max_depth
        self.max_workers = max(1, max_workers)
        self.strategy_name = strategy_name
        self.task_id = f"{self.strategy_name}_{self.version}"
        self.workspace_dir, resolved_application_ini = resolve_workspace_and_application_ini(
            application_ini_path=application_ini_path,
            reference_file=__file__,
        )
        self.dt_str = datetime.now().strftime("%Y%m%d%H%M%S")

        base_dir = self.workspace_dir / "com" / "willy" / "trade_bot" / "ml" / f"{strategy_name}_{version}"
        self.trainer_file_path = str(base_dir / "model_trainer.py")
        self.trained_model_path = str(base_dir / "generated" / f"model_{self.dt_str}") + "/"
        self.session_dir = str(base_dir / "sessions") + "/"

        status_dir = base_dir / "status"
        self.implement_plan_ready_status_file_path = str(status_dir / "implement_plan_ready_status_file.txt")
        self.conflicting_idea_status_file_path = str(status_dir / "conflicting_idea_status_file.txt")
        self.code_need_fix_status_file_path = str(status_dir / "code_need_fix_status_file.txt")
        self.model_ready_status_file_path = str(status_dir / "model_ready_status_file.txt")
        self.graph_output_dir = graph_output_dir or str(base_dir / "generated" / "flow_graph")
        self.graph_state = graph_state if graph_state is not None else {"nodes": {}, "edges": [], "sequence": 0}
        self.graph_lock = graph_lock if graph_lock is not None else threading.Lock()

        self.last_session_name = ""
        self.usage_llm_models = [LLMTarget.GEMINI, LLMTarget.CODEX]
        self.stack_trace = []
        self.service_node_id = f"service::{self.task_id}"
        self.register_node(
            self.service_node_id,
            self.task_id,
            shape="box",
            color="lightblue",
            style="filled",
        )

        self.application_ini_path = resolved_application_ini
        if langsmith_client is None:
            self.langsmith_client, self.langsmith_project = configure_langsmith(
                application_ini_path=self.application_ini_path,
                default_project=f"trade_bot_{self.strategy_name}",
            )
        else:
            self.langsmith_client = langsmith_client
            self.langsmith_project = (
                langsmith_project or os.getenv("LANGSMITH_PROJECT") or f"trade_bot_{self.strategy_name}"
            )

        self.langchain_tracer = LangChainTracer(
            project_name=self.langsmith_project,
            client=self.langsmith_client,
            tags=["multi-agent-session", self.strategy_name, self.version],
        )
        self.langchain_state: dict[str, Any] = {}
        self.agent_runnable = RunnableLambda(self._invoke_llm_once)
        self.prompt_builder = LangChainPromptBuilder(
            session_dir=self.session_dir,
            trainer_file_path=self.trainer_file_path,
            trained_model_path=self.trained_model_path,
            implement_plan_ready_status_file_path=self.implement_plan_ready_status_file_path,
            conflicting_idea_status_file_path=self.conflicting_idea_status_file_path,
            code_need_fix_status_file_path=self.code_need_fix_status_file_path,
            model_ready_status_file_path=self.model_ready_status_file_path,
        )
        self.update_discussion_state()

    @staticmethod
    def get_session_file_name(llm_name: LLMTarget) -> str:
        return f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{llm_name.name}.md"

    @staticmethod
    def sanitize_graph_label(value: str) -> str:
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")

    def _langchain_config(
        self,
        *,
        run_name: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        discussion_state = self.update_discussion_state()
        config: dict[str, Any] = {
            "run_name": run_name,
            "callbacks": [self.langchain_tracer],
            "tags": ["langchain", "multi-agent-session", self.strategy_name, self.version],
            "metadata": {
                "task_id": self.task_id,
                "depth": self.current_depth,
                "flow_state": {
                    "discussion": discussion_state,
                },
            },
        }
        if tags:
            config["tags"] = list(config["tags"]) + tags
        if metadata:
            config["metadata"] = {**config["metadata"], **metadata}
        return config

    def discussion_state_file_paths(self) -> dict[str, str]:
        return {
            "discussion_ready": self.implement_plan_ready_status_file_path,
            "discussion_conflict": self.conflicting_idea_status_file_path,
        }

    def update_discussion_state(self) -> dict[str, bool]:
        discussion_state = {
            state_name: os.path.exists(path)
            for state_name, path in self.discussion_state_file_paths().items()
        }
        self.langchain_state["discussion"] = discussion_state
        return dict(discussion_state)

    def _invoke_llm_once(self, payload: dict[str, Any]) -> str:
        llm_target_value = payload["llm_target"]
        if isinstance(llm_target_value, LLMTarget):
            llm_target = llm_target_value
        elif llm_target_value in LLMTarget.__members__:
            llm_target = LLMTarget[llm_target_value]
        else:
            llm_target = LLMTarget(llm_target_value)
        prompt = payload["prompt"]
        cwd = payload.get("cwd")
        return llm_svc.run_once(llm_target, prompt, cwd=cwd)

    def next_graph_sequence(self) -> int:
        with self.graph_lock:
            self.graph_state["sequence"] += 1
            return self.graph_state["sequence"]

    def register_node(self, node_id: str, label: str, **attrs):
        with self.graph_lock:
            node = {"label": label}
            node.update(attrs)
            self.graph_state["nodes"][node_id] = node

    def register_edge(self, source: str, target: str, label: str = ""):
        with self.graph_lock:
            self.graph_state["edges"].append((source, target, label))

    def record_status_node(self, status_name: str, label: str, color: str):
        node_id = f"status::{self.task_id}::{status_name}"
        self.register_node(node_id, label, shape="ellipse", color=color, style="filled")
        self.register_edge(self.service_node_id, node_id, status_name)
        return node_id

    def export_flow_graph(self):
        output_dir = Path(self.graph_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"{self.task_id}_flow"
        dot_path = output_dir / f"{base_name}.dot"

        lines = [
            "digraph MultiAgentSession {",
            "  rankdir=LR;",
            "  graph [fontname=\"Microsoft JhengHei\"];",
            "  node [fontname=\"Microsoft JhengHei\"];",
            "  edge [fontname=\"Microsoft JhengHei\"];",
        ]

        with self.graph_lock:
            nodes = dict(self.graph_state["nodes"])
            edges = list(self.graph_state["edges"])

        for node_id, attrs in nodes.items():
            attr_pairs = []
            for key, value in attrs.items():
                attr_pairs.append(f'{key}="{self.sanitize_graph_label(str(value))}"')
            lines.append(f'  "{node_id}" [{", ".join(attr_pairs)}];')

        for source, target, label in edges:
            edge_label = self.sanitize_graph_label(label)
            if edge_label:
                lines.append(f'  "{source}" -> "{target}" [label="{edge_label}"];')
            else:
                lines.append(f'  "{source}" -> "{target}";')

        lines.append("}")
        dot_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        dot_exe = shutil.which("dot")
        if not dot_exe:
            print(f"graphviz dot not found, exported dot file to {dot_path}")
            return dot_path

        png_path = output_dir / f"{base_name}.png"
        svg_path = output_dir / f"{base_name}.svg"
        subprocess.run([dot_exe, "-Tpng", str(dot_path), "-o", str(png_path)], check=False)
        subprocess.run([dot_exe, "-Tsvg", str(dot_path), "-o", str(svg_path)], check=False)
        print(f"exported flow graph to {dot_path}, {png_path}, {svg_path}")
        return dot_path

    def run_agent(self, llm_target: LLMTarget, prompt: str, session_file_name: str):
        print(f"start call task_id[{self.task_id}] LLM[{llm_target.name}] prompt[{prompt}]")
        step_id = f"agent::{self.task_id}::{self.next_graph_sequence()}"
        prompt_preview = prompt[:80] + ("..." if len(prompt) > 80 else "")
        self.register_node(
            step_id,
            f"{llm_target.name}\\n{prompt_preview}",
            shape="note",
            color="lightyellow",
            style="filled",
        )
        self.register_edge(self.service_node_id, step_id, "run_agent")
        discussion_state_before = self.update_discussion_state()
        output = self.agent_runnable.invoke(
            {
                "llm_target": llm_target,
                "prompt": prompt,
                "cwd": str(self.workspace_dir),
            },
            config=self._langchain_config(
                run_name=f"agent_{llm_target.name}",
                tags=[llm_target.name.lower()],
                metadata={
                    "session_file_name": session_file_name,
                    "prompt_length": len(prompt),
                    "discussion_state_before": discussion_state_before,
                },
            ),
        )
        discussion_state_after = self.update_discussion_state()
        self.stack_trace.append(
            {
                "target_llm": llm_target.name,
                "prompt": prompt,
                "output": output,
                "task_id": self.task_id,
                "discussion_state_before": discussion_state_before,
                "discussion_state_after": discussion_state_after,
            }
        )
        print(f"output[{output}]")
        self.last_session_name = session_file_name

    def clear_discussion_stop_statuses(self):
        for path in self.discussion_state_file_paths().values():
            if os.path.exists(path):
                os.remove(path)
        self.update_discussion_state()

    def flush_traces(self):
        self.langsmith_client.flush()
