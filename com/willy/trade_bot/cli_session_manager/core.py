from __future__ import annotations

import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from com.willy.trade_bot.cli_session_manager.models import SessionRecord, StrategyWorkspace
from com.willy.trade_bot.enums.llm_target import LLMTarget
from com.willy.trade_bot.service import llm_svc


class StatusManager:
    def __init__(self, workspace: StrategyWorkspace):
        self.workspace = workspace

    def path(self, status_name: str) -> Path:
        return self.workspace.status_file(status_name)

    def exists(self, status_name: str) -> bool:
        return self.path(status_name).exists()

    def create(self, status_name: str, content: str = "") -> Path:
        target = self.path(status_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def clear(self, status_name: str) -> None:
        target = self.path(status_name)
        if target.exists():
            target.unlink()

    def clear_many(self, status_names: list[str] | tuple[str, ...]) -> None:
        for status_name in status_names:
            self.clear(status_name)


class SessionStore:
    def __init__(self, workspace: StrategyWorkspace):
        self.workspace = workspace
        self.last_session: SessionRecord | None = None

    @staticmethod
    def build_session_name(llm_target: LLMTarget, step_name: str) -> str:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_step = step_name.replace(" ", "_")
        return f"{ts}_{safe_step}_{llm_target.name}.md"

    def persist(self, llm_target: LLMTarget, step_name: str, prompt: str, output: str) -> SessionRecord:
        self.workspace.sessions_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.workspace.sessions_dir / self.build_session_name(llm_target, step_name)
        created_at = datetime.now()
        markdown = [
            f"# {step_name}",
            "",
            f"- LLM: `{llm_target.name}`",
            f"- Created At: `{created_at.isoformat()}`",
            "",
            "## Prompt",
            "",
            "```text",
            prompt,
            "```",
            "",
            "## Output",
            "",
            output,
            "",
        ]
        file_path.write_text("\n".join(markdown), encoding="utf-8")
        record = SessionRecord(
            llm_target=llm_target,
            prompt=prompt,
            output=output,
            file_path=file_path,
            created_at=created_at,
            step_name=step_name,
        )
        self.last_session = record
        return record


@dataclass(slots=True)
class GraphNode:
    label: str
    shape: str = "box"
    color: str = "white"
    style: str = "solid"


class CallTreeRecorder:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[tuple[str, str, str]] = []
        self.sequence = 0
        self.lock = threading.Lock()

    def next_id(self, prefix: str) -> str:
        with self.lock:
            self.sequence += 1
            return f"{prefix}::{self.sequence}"

    def add_node(self, node_id: str, label: str, *, shape: str = "box", color: str = "white", style: str = "solid"):
        with self.lock:
            self.nodes[node_id] = GraphNode(label=label, shape=shape, color=color, style=style)

    def add_edge(self, source: str, target: str, label: str = ""):
        with self.lock:
            self.edges.append((source, target, label))

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")

    def export(self, file_stem: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        dot_path = self.output_dir / f"{file_stem}.dot"
        lines = [
            "digraph SessionFlow {",
            "  rankdir=LR;",
            "  graph [fontname=\"Microsoft JhengHei\"];",
            "  node [fontname=\"Microsoft JhengHei\"];",
            "  edge [fontname=\"Microsoft JhengHei\"];",
        ]

        with self.lock:
            nodes = dict(self.nodes)
            edges = list(self.edges)

        for node_id, node in nodes.items():
            lines.append(
                f'  "{node_id}" [label="{self._escape(node.label)}", '
                f'shape="{node.shape}", color="{node.color}", style="{node.style}"];'
            )

        for source, target, label in edges:
            if label:
                lines.append(f'  "{source}" -> "{target}" [label="{self._escape(label)}"];')
            else:
                lines.append(f'  "{source}" -> "{target}";')
        lines.append("}")
        dot_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        dot_exe = shutil.which("dot")
        if dot_exe:
            subprocess.run([dot_exe, "-Tpng", str(dot_path), "-o", str(self.output_dir / f"{file_stem}.png")],
                           check=False)
            subprocess.run([dot_exe, "-Tsvg", str(dot_path), "-o", str(self.output_dir / f"{file_stem}.svg")],
                           check=False)
        return dot_path


class AgentRunner:
    def __init__(self, workspace: StrategyWorkspace, session_store: SessionStore, graph: CallTreeRecorder):
        self.workspace = workspace
        self.session_store = session_store
        self.graph = graph

    def run(self, step_name: str, llm_target: LLMTarget, prompt: str, parent_node_id: str) -> SessionRecord:
        node_id = self.graph.next_id("agent")
        preview = prompt[:80] + ("..." if len(prompt) > 80 else "")
        self.graph.add_node(node_id, f"{llm_target.name}\n{step_name}\n{preview}", shape="note", color="lightyellow",
                            style="filled")
        self.graph.add_edge(parent_node_id, node_id, step_name)
        output = llm_svc.run_once(llm_target, prompt, cwd=str(self.workspace.root_dir))
        return self.session_store.persist(llm_target, step_name, prompt, output)
