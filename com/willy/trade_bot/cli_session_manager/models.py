from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from com.willy.trade_bot.enums.llm_target import LLMTarget


@dataclass(slots=True)
class StrategyWorkspace:
    strategy_name: str
    version: str
    root_dir: Path
    trainer_file_name: str = "model_trainer.py"
    graph_dir_name: str = "flow_graph"
    strategy_dir_override: Path | None = None

    @property
    def strategy_dir(self) -> Path:
        if self.strategy_dir_override is not None:
            return self.strategy_dir_override
        return self.root_dir / "com" / "willy" / "trade_bot" / "ml" / f"{self.strategy_name}_{self.version}"

    @property
    def task_name(self) -> str:
        return self.strategy_dir.name

    @property
    def trainer_file_path(self) -> Path:
        return self.strategy_dir / self.trainer_file_name

    @property
    def sessions_dir(self) -> Path:
        return self.strategy_dir / "sessions"

    @property
    def status_dir(self) -> Path:
        return self.strategy_dir / "status"

    @property
    def generated_dir(self) -> Path:
        return self.strategy_dir / "generated"

    @property
    def graph_output_dir(self) -> Path:
        return self.generated_dir / self.graph_dir_name

    def ensure_dirs(self) -> None:
        self.strategy_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.status_dir.mkdir(parents=True, exist_ok=True)
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.graph_output_dir.mkdir(parents=True, exist_ok=True)

    def status_file(self, status_name: str) -> Path:
        return self.status_dir / f"{status_name}.txt"

    @classmethod
    def from_strategy_dir(
            cls,
            strategy_dir: str | Path,
            *,
            trainer_file_name: str = "model_trainer.py",
            graph_dir_name: str = "flow_graph",
    ) -> "StrategyWorkspace":
        strategy_path = Path(strategy_dir).resolve()
        return cls(
            strategy_name=strategy_path.name,
            version="runtime",
            root_dir=strategy_path.parent,
            trainer_file_name=trainer_file_name,
            graph_dir_name=graph_dir_name,
            strategy_dir_override=strategy_path,
        )


@dataclass(slots=True)
class SessionRecord:
    llm_target: LLMTarget
    prompt: str
    output: str
    file_path: Path
    created_at: datetime
    step_name: str


@dataclass(slots=True)
class DiscussionStepSpec:
    name: str
    instruction: str
    llm_targets: list[LLMTarget]
    rounds: int = 1
    stop_statuses: tuple[str, ...] = ()


@dataclass(slots=True)
class ImplementationStepSpec:
    name: str
    summary_instruction: str
    implement_llm: LLMTarget
    review_llm: LLMTarget
    max_retries: int = 3
    fix_status_name: str = "code_need_fix"
    success_status_name: str = "model_ready"


@dataclass(slots=True)
class FlowRunResult:
    sessions: list[SessionRecord] = field(default_factory=list)
    touched_statuses: set[str] = field(default_factory=set)
    stopped_early: bool = False
    visited_nodes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StatusSpec:
    name: str
    description: str = ""
    terminal: bool = False


@dataclass(slots=True)
class TransitionSpec:
    target: str
    label: str = ""
    when_status_exists: tuple[str, ...] = ()
    when_status_missing: tuple[str, ...] = ()


@dataclass(slots=True)
class FlowNodeSpec:
    name: str
    prompt: str
    llm_targets: list[LLMTarget]
    transitions: list[TransitionSpec] = field(default_factory=list)
    repeat: int = 1
    terminal: bool = False
    clear_statuses_before_run: tuple[str, ...] = ()
    description: str = ""
    mode: str = "sequential"


class BaseSessionStrategy:
    strategy_dir: str | Path = ""
    trainer_file_name: str = "model_trainer.py"
    graph_dir_name: str = "flow_graph"
    statuses: list[StatusSpec] = []
    nodes: list[FlowNodeSpec] = []
    start_node: str = ""
    max_steps: int = 100

    def build_workspace(self) -> StrategyWorkspace:
        return StrategyWorkspace.from_strategy_dir(
            self.strategy_dir,
            trainer_file_name=self.trainer_file_name,
            graph_dir_name=self.graph_dir_name,
        )
