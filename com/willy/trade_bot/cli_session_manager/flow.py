from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from com.willy.trade_bot.cli_session_manager.core import (
    AgentRunner,
    CallTreeRecorder,
    SessionStore,
    StatusManager,
)
from com.willy.trade_bot.cli_session_manager.models import (
    DiscussionStepSpec,
    FlowRunResult,
    ImplementationStepSpec,
    StrategyWorkspace,
)
from com.willy.trade_bot.cli_session_manager.prompts import PromptFactory
from com.willy.trade_bot.enums.llm_target import LLMTarget


class SessionFlow:
    def __init__(self, workspace: StrategyWorkspace):
        self.workspace = workspace
        self.workspace.ensure_dirs()
        self.statuses = StatusManager(workspace)
        self.sessions = SessionStore(workspace)
        self.graph = CallTreeRecorder(workspace.graph_output_dir)
        self.prompts = PromptFactory(workspace)
        self.runner = AgentRunner(workspace, self.sessions, self.graph)
        self.discussion_steps: list[DiscussionStepSpec] = []
        self.implementation_steps: list[ImplementationStepSpec] = []
        self.root_node_id = f"flow::{workspace.strategy_name}_{workspace.version}"
        self.graph.add_node(self.root_node_id, f"{workspace.strategy_name}_{workspace.version}", shape="box",
                            color="lightblue", style="filled")

    def add_discussion(self, spec: DiscussionStepSpec) -> "SessionFlow":
        self.discussion_steps.append(spec)
        return self

    def add_implementation(self, spec: ImplementationStepSpec) -> "SessionFlow":
        self.implementation_steps.append(spec)
        return self

    def run(self) -> FlowRunResult:
        result = FlowRunResult()

        for spec in self.discussion_steps:
            stop_paths = [self.statuses.path(status_name) for status_name in spec.stop_statuses]
            for _ in range(spec.rounds):
                if any(path.exists() for path in stop_paths):
                    result.stopped_early = True
                    break
                for llm_target in spec.llm_targets:
                    prompt = self.prompts.discussion_prompt(
                        instruction=spec.instruction,
                        previous_session=self.sessions.last_session.file_path if self.sessions.last_session else None,
                        stop_status_paths=stop_paths,
                    )
                    record = self.runner.run(spec.name, llm_target, prompt, self.root_node_id)
                    result.sessions.append(record)
                    if any(path.exists() for path in stop_paths):
                        result.touched_statuses.update(spec.stop_statuses)
                        result.stopped_early = True
                        break
                if result.stopped_early:
                    break

        for spec in self.implementation_steps:
            for _ in range(spec.max_retries):
                self.statuses.clear(spec.fix_status_name)
                implement_prompt = self.prompts.implement_prompt(
                    summary_instruction=spec.summary_instruction,
                    previous_session=self.sessions.last_session.file_path if self.sessions.last_session else None,
                    generated_dir=self.workspace.generated_dir,
                )
                result.sessions.append(
                    self.runner.run(spec.name, spec.implement_llm, implement_prompt, self.root_node_id))

                review_prompt = self.prompts.review_prompt(
                    previous_session=self.sessions.last_session.file_path if self.sessions.last_session else None,
                    fix_status_path=self.statuses.path(spec.fix_status_name),
                )
                result.sessions.append(
                    self.runner.run(f"{spec.name}_review", spec.review_llm, review_prompt, self.root_node_id))
                if not self.statuses.exists(spec.fix_status_name):
                    break
                result.touched_statuses.add(spec.fix_status_name)

            final_prompt = self.prompts.final_validation_prompt(
                previous_session=self.sessions.last_session.file_path if self.sessions.last_session else None,
                success_status_path=self.statuses.path(spec.success_status_name),
            )
            result.sessions.append(
                self.runner.run(f"{spec.name}_final", spec.review_llm, final_prompt, self.root_node_id))
            if self.statuses.exists(spec.success_status_name):
                result.touched_statuses.add(spec.success_status_name)

        return result

    def export_graph(self, file_stem: str | None = None) -> Path:
        if file_stem is None:
            file_stem = f"{self.workspace.strategy_name}_{self.workspace.version}_flow"
        return self.graph.export(file_stem)


class RecursiveImprovementCoordinator:
    def __init__(
            self,
            strategy_name: str,
            version: str,
            *,
            workspace_root: str | Path = ".",
            discussion_loop: int = 3,
            current_depth: int = 0,
            max_depth: int = 5,
            max_workers: int = 2,
            usage_llms: list[LLMTarget] | None = None,
            trainer_file_name: str = "model_trainer.py",
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace = StrategyWorkspace(
            strategy_name=strategy_name,
            version=version,
            root_dir=self.workspace_root,
            trainer_file_name=trainer_file_name,
        )
        self.discussion_loop = discussion_loop
        self.current_depth = current_depth
        self.max_depth = max_depth
        self.max_workers = max(1, max_workers)
        self.usage_llms = usage_llms or [LLMTarget.GEMINI, LLMTarget.CODEX]

        self.flow = SessionFlow(self.workspace)
        self.flow.add_discussion(
            DiscussionStepSpec(
                name="discussion",
                instruction="Review the latest session and refine the implementation plan until it is ready.",
                llm_targets=self.usage_llms,
                rounds=self.discussion_loop,
                stop_statuses=("implement_plan_ready_status_file", "conflicting_idea_status_file"),
            )
        )
        self.flow.add_implementation(
            ImplementationStepSpec(
                name="implementation",
                summary_instruction="Implement the trainer based on the latest approved plan and keep generated artifacts under the generated directory.",
                implement_llm=LLMTarget.GEMINI,
                review_llm=LLMTarget.CODEX,
            )
        )

    @property
    def task_id(self) -> str:
        return f"{self.workspace.strategy_name}_{self.workspace.version}"

    def _build_next_version(self, llm_target: LLMTarget) -> str:
        version_prefix, _, version_suffix = self.workspace.version.rpartition("_")
        if not version_prefix or not version_suffix.isdigit():
            raise ValueError(f"Unsupported version format: {self.workspace.version}")
        if llm_target == self.usage_llms[-1]:
            return f"{version_prefix}_{int(version_suffix) + 1}"
        return f"{version_prefix}_{llm_target.name}_1"

    def run(self) -> FlowRunResult:
        result = self.flow.run()
        self.flow.export_graph(self.task_id)
        return result

    def spawn_children(self) -> list["RecursiveImprovementCoordinator"]:
        children = []
        for llm_target in self.usage_llms:
            children.append(
                RecursiveImprovementCoordinator(
                    strategy_name=self.workspace.strategy_name,
                    version=self._build_next_version(llm_target),
                    workspace_root=self.workspace_root,
                    discussion_loop=self.discussion_loop,
                    current_depth=self.current_depth + 1,
                    max_depth=self.max_depth,
                    max_workers=self.max_workers,
                    usage_llms=self.usage_llms,
                    trainer_file_name=self.workspace.trainer_file_name,
                )
            )
        return children

    def run_recursive(self) -> list[FlowRunResult]:
        results = [self.run()]
        if self.current_depth >= self.max_depth:
            return results

        children = self.spawn_children()
        worker_count = min(self.max_workers, len(children))
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="cli-session-flow") as executor:
            futures = [executor.submit(child.run_recursive) for child in children]
            for future in as_completed(futures):
                results.extend(future.result())
        return results
