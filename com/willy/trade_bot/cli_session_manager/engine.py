from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from com.willy.trade_bot.cli_session_manager.core import (
    AgentRunner,
    CallTreeRecorder,
    SessionStore,
    StatusManager,
)
from com.willy.trade_bot.cli_session_manager.models import (
    BaseSessionStrategy,
    FlowNodeSpec,
    FlowRunResult,
    StatusSpec,
    StrategyWorkspace,
    TransitionSpec,
)
from com.willy.trade_bot.cli_session_manager.prompts import PromptFactory
from com.willy.trade_bot.enums.llm_target import LLMTarget


class SessionFlowEngine:
    def __init__(
            self,
            workspace: StrategyWorkspace,
            *,
            statuses: list[StatusSpec],
            nodes: list[FlowNodeSpec],
            start_node: str,
            max_steps: int = 100,
    ):
        self.workspace = workspace
        self.workspace.ensure_dirs()
        self.status_specs = {status.name: status for status in statuses}
        self.nodes = {node.name: node for node in nodes}
        self.start_node = start_node
        self.max_steps = max_steps

        if start_node not in self.nodes:
            raise ValueError(f"start_node '{start_node}' is not defined in nodes")

        self.statuses = StatusManager(workspace)
        self.sessions = SessionStore(workspace)
        self.graph = CallTreeRecorder(workspace.graph_output_dir)
        self.prompts = PromptFactory(workspace)
        self.runner = AgentRunner(workspace, self.sessions, self.graph)

        self.root_node_id = f"engine::{workspace.task_name}"
        self.graph.add_node(self.root_node_id, workspace.task_name, shape="box", color="lightblue", style="filled")
        for node in nodes:
            graph_node_id = f"spec::{node.name}"
            self.graph.add_node(graph_node_id, node.name, shape="component", color="lightcyan", style="filled")
            self.graph.add_edge(self.root_node_id, graph_node_id, "declares")
            for transition in node.transitions:
                self.graph.add_edge(graph_node_id, f"spec::{transition.target}", transition.label or "transition")

    @classmethod
    def from_strategy(cls, strategy: BaseSessionStrategy) -> "SessionFlowEngine":
        return cls(
            workspace=strategy.build_workspace(),
            statuses=list(strategy.statuses),
            nodes=list(strategy.nodes),
            start_node=strategy.start_node,
            max_steps=strategy.max_steps,
        )

    @classmethod
    def from_dict(cls, config: dict) -> "SessionFlowEngine":
        workspace = StrategyWorkspace.from_strategy_dir(
            config["strategy_dir"],
            trainer_file_name=config.get("trainer_file_name", "model_trainer.py"),
            graph_dir_name=config.get("graph_dir_name", "flow_graph"),
        )
        statuses = [
            StatusSpec(
                name=item["name"],
                description=item.get("description", ""),
                terminal=item.get("terminal", False),
            )
            for item in config.get("statuses", [])
        ]
        nodes = []
        for item in config["nodes"]:
            llm_targets = [LLMTarget[target] if isinstance(target, str) else target for target in item["llm_targets"]]
            transitions = [
                TransitionSpec(
                    target=transition["target"],
                    label=transition.get("label", ""),
                    when_status_exists=tuple(transition.get("when_status_exists", [])),
                    when_status_missing=tuple(transition.get("when_status_missing", [])),
                )
                for transition in item.get("transitions", [])
            ]
            nodes.append(
                FlowNodeSpec(
                    name=item["name"],
                    prompt=item["prompt"],
                    llm_targets=llm_targets,
                    transitions=transitions,
                    repeat=item.get("repeat", 1),
                    terminal=item.get("terminal", False),
                    clear_statuses_before_run=tuple(item.get("clear_statuses_before_run", [])),
                    description=item.get("description", ""),
                    mode=item.get("mode", "sequential"),
                )
            )
        return cls(
            workspace=workspace,
            statuses=statuses,
            nodes=nodes,
            start_node=config["start_node"],
            max_steps=config.get("max_steps", 100),
        )

    def export_config(self, path: str | Path) -> Path:
        output_path = Path(path)
        payload = {
            "strategy_dir": str(self.workspace.strategy_dir),
            "trainer_file_name": self.workspace.trainer_file_name,
            "graph_dir_name": self.workspace.graph_dir_name,
            "start_node": self.start_node,
            "max_steps": self.max_steps,
            "statuses": [asdict(status) for status in self.status_specs.values()],
            "nodes": [
                {
                    **asdict(node),
                    "llm_targets": [target.name for target in node.llm_targets],
                }
                for node in self.nodes.values()
            ],
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output_path

    def _status_paths(self) -> list[Path]:
        names = list(self.status_specs.keys())
        return [self.statuses.path(name) for name in names]

    def _clear_node_statuses(self, node: FlowNodeSpec) -> None:
        for status_name in node.clear_statuses_before_run:
            self.statuses.clear(status_name)

    def _run_node(self, node: FlowNodeSpec, result: FlowRunResult) -> None:
        self._clear_node_statuses(node)
        spec_node_id = f"spec::{node.name}"

        for _ in range(node.repeat):
            for llm_target in node.llm_targets:
                prompt = self.prompts.flow_node_prompt(
                    node_name=node.name,
                    instruction=node.prompt,
                    previous_session=self.sessions.last_session.file_path if self.sessions.last_session else None,
                    available_status_paths=self._status_paths(),
                )
                record = self.runner.run(node.name, llm_target, prompt, spec_node_id)
                result.sessions.append(record)

    def _transition_matches(self, transition: TransitionSpec) -> bool:
        if any(not self.statuses.exists(status_name) for status_name in transition.when_status_exists):
            return False
        if any(self.statuses.exists(status_name) for status_name in transition.when_status_missing):
            return False
        return True

    def _resolve_next_node(self, node: FlowNodeSpec) -> str | None:
        for transition in node.transitions:
            if self._transition_matches(transition):
                return transition.target
        return None

    def run(self) -> FlowRunResult:
        current_node_name: str | None = self.start_node
        steps = 0
        result = FlowRunResult()

        while current_node_name is not None:
            if steps >= self.max_steps:
                raise RuntimeError(f"Flow exceeded max_steps={self.max_steps}")
            node = self.nodes[current_node_name]
            result.visited_nodes.append(current_node_name)
            self._run_node(node, result)

            if node.terminal:
                break

            touched = {status_name for status_name in self.status_specs if self.statuses.exists(status_name)}
            result.touched_statuses.update(touched)
            if any(self.status_specs[name].terminal for name in touched if name in self.status_specs):
                result.stopped_early = True
                break

            current_node_name = self._resolve_next_node(node)
            steps += 1

        return result

    def export_graph(self, file_stem: str | None = None) -> Path:
        if file_stem is None:
            file_stem = f"{self.workspace.task_name}_engine_flow"
        return self.graph.export(file_stem)
