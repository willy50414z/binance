from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.tracers import LangChainTracer
from langgraph.graph import END, StateGraph
from langsmith import Client

# Support direct execution: `python .../non_recursive_session_workflow.py`
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from com.willy.trade_bot.enums import LLMTarget
from com.willy.trade_bot.langchain.langsmith_support import (
    configure_langsmith,
    resolve_workspace_and_application_ini,
)
from com.willy.trade_bot.service import llm_svc


class NonRecursiveWorkflowState(TypedDict, total=False):
    implement_attempt: int
    needs_fix: bool
    model_ready: bool
    discussion_round: int
    llm_index: int
    discussion_stop: bool
    final_reason: Literal[
        "model_ready",
        "max_depth_reached",
        "discussion_stop",
        "discussion_rounds_done",
        "no_discussion_loop",
    ]
    history: list[dict[str, Any]]


class LangChainNonRecursiveSessionService:
    def __init__(
        self,
        strategy_name: str,
        version: str,
        discussion_loop: int = 3,
        current_depth: int = 0,
        max_depth: int = 5,
        max_implement_retries: int = 3,
        graph_output_dir: str | None = None,
        application_ini_path: str | Path | None = None,
        langsmith_client: Client | None = None,
        langsmith_project: str | None = None,
    ):
        self.strategy_name = strategy_name
        self.version = version
        self.discussion_loop = max(0, discussion_loop)
        self.current_depth = current_depth
        self.max_depth = max_depth
        self.max_implement_retries = max(1, max_implement_retries)
        self.task_id = f"{strategy_name}_{version}"
        self.workspace_dir, resolved_application_ini = resolve_workspace_and_application_ini(
            application_ini_path=application_ini_path,
            reference_file=__file__,
        )
        self.dt_str = datetime.now().strftime("%Y%m%d%H%M%S")

        base_dir = self.workspace_dir / "com" / "willy" / "trade_bot" / "ml" / f"{strategy_name}_{version}"
        self.trainer_file_path = str(base_dir / "model_trainer.py")
        self.generated_dir = str(base_dir / "generated")

        status_dir = base_dir / "status"
        self.implement_plan_ready_status_file_path = str(status_dir / "implement_plan_ready_status_file.txt")
        self.conflicting_idea_status_file_path = str(status_dir / "conflicting_idea_status_file.txt")
        self.code_need_fix_status_file_path = str(status_dir / "code_need_fix_status_file.txt")
        self.model_ready_status_file_path = str(status_dir / "model_ready_status_file.txt")

        self.graph_output_dir = graph_output_dir or str(base_dir / "generated" / "flow_graph")
        Path(self.generated_dir).mkdir(parents=True, exist_ok=True)
        Path(status_dir).mkdir(parents=True, exist_ok=True)
        Path(self.graph_output_dir).mkdir(parents=True, exist_ok=True)

        self.usage_llm_models = [LLMTarget.GEMINI, LLMTarget.CODEX]
        self.stack_trace: list[dict[str, Any]] = []
        self.graph_state: dict[str, Any] = {"nodes": {}, "edges": [], "sequence": 0}
        self.graph_lock = threading.Lock()
        self.service_node_id = f"service::{self.task_id}"
        self.register_node(self.service_node_id, self.task_id, shape="box", color="lightblue", style="filled")

        self.application_ini_path = resolved_application_ini
        if langsmith_client is None:
            self.langsmith_client, self.langsmith_project = configure_langsmith(
                application_ini_path=self.application_ini_path,
                default_project=f"trade_bot_{self.strategy_name}_non_recursive",
            )
        else:
            self.langsmith_client = langsmith_client
            self.langsmith_project = (
                langsmith_project or os.getenv("LANGSMITH_PROJECT") or f"trade_bot_{self.strategy_name}_non_recursive"
            )

        self.langchain_tracer = LangChainTracer(
            project_name=self.langsmith_project,
            client=self.langsmith_client,
            tags=["non-recursive-workflow", self.strategy_name, self.version],
        )
        self.langchain_state: dict[str, Any] = {}
        self.agent_runnable = RunnableLambda(self._invoke_llm_once)

        self.implement_prompt = PromptTemplate.from_template(
            "Implement stage for Python ML trainer.\n"
            "Trainer file: {trainer_file}\n"
            "Generated directory: {generated_dir}\n"
            "Pre-check trainer exists: {trainer_exists}\n"
            "Required action:\n"
            "{action_instruction}\n"
            "Constraints:\n"
            "- Keep time-series correctness.\n"
            "- Avoid leakage.\n"
            "- Follow the latest discussion assumptions."
        )
        self.review_prompt = PromptTemplate.from_template(
            "Review trainer implementation quality.\n"
            "Trainer file: {trainer_file}\n"
            "If code still needs fixes, create status file: {fix_status_file}\n"
            "Return only concrete issues and required fixes."
        )
        self.fallback_fix_prompt = PromptTemplate.from_template(
            "Apply focused fixes to the trainer according to latest review findings.\n"
            "Trainer file: {trainer_file}\n"
            "Keep edits minimal and deterministic."
        )
        self.final_validation_prompt = PromptTemplate.from_template(
            "Perform final readiness validation for this trainer.\n"
            "Trainer file: {trainer_file}\n"
            "If ready, create status file: {model_ready_file}\n"
            "Check correctness, leakage safety, and reproducibility."
        )
        self.discussion_prompt = PromptTemplate.from_template(
            "You are in a non-recursive strategy discussion loop.\n"
            "Round: {round_index}\n"
            "Current LLM role: {llm_name}\n"
            "Trainer file: {trainer_file}\n"
            "If implementation plan is ready, create status file: {ready_file}\n"
            "If conflict exists, create status file: {conflict_file}\n"
            "Return concise decision-focused discussion output."
        )

        self.workflow = self._build_workflow()
        self.discussion_workflow = self._build_discussion_workflow()
        self.update_discussion_state()
        self._log(
            "initialized "
            f"workspace={self.workspace_dir} trainer={self.trainer_file_path} "
            f"discussion_loop={self.discussion_loop} max_depth={self.max_depth}"
        )

    def _log(self, message: str):
        print(
            f"[{datetime.now().isoformat()}][non-recursive][{self.task_id}] {message}",
            flush=True,
        )

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
            "tags": ["langchain", "non-recursive-workflow", self.strategy_name, self.version],
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

    def should_stop_discussion(self) -> bool:
        return any(self.update_discussion_state().values())

    def _invoke_llm_once(self, payload: dict[str, Any]) -> str:
        llm_target = payload["llm_target"]
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

    def run_agent(self, llm_target: LLMTarget, prompt: str, *, step_name: str) -> str:
        self._log(
            f"run_agent start step={step_name} llm={llm_target.name} prompt_len={len(prompt)}"
        )
        step_id = f"agent::{self.task_id}::{self.next_graph_sequence()}"
        prompt_preview = prompt[:80] + ("..." if len(prompt) > 80 else "")
        self.register_node(
            step_id,
            f"{llm_target.name}\\n{step_name}\\n{prompt_preview}",
            shape="note",
            color="lightyellow",
            style="filled",
        )
        self.register_edge(self.service_node_id, step_id, step_name)

        discussion_state_before = self.update_discussion_state()
        start_perf = time.perf_counter()
        output = self.agent_runnable.invoke(
            {
                "llm_target": llm_target,
                "prompt": prompt,
                "cwd": str(self.workspace_dir),
            },
            config=self._langchain_config(
                run_name=f"agent_{step_name}_{llm_target.name}",
                tags=["agent-step", step_name, llm_target.name.lower()],
                metadata={
                    "step_name": step_name,
                    "prompt_length": len(prompt),
                    "discussion_state_before": discussion_state_before,
                },
            ),
        )
        elapsed = time.perf_counter() - start_perf
        discussion_state_after = self.update_discussion_state()
        self.stack_trace.append(
            {
                "step_name": step_name,
                "target_llm": llm_target.name,
                "prompt": prompt,
                "output": output,
                "task_id": self.task_id,
                "discussion_state_before": discussion_state_before,
                "discussion_state_after": discussion_state_after,
            }
        )
        self._log(
            f"run_agent done step={step_name} llm={llm_target.name} "
            f"elapsed_sec={elapsed:.2f} output_len={len(output)}"
        )
        return output

    def _append_history(
        self,
        state: NonRecursiveWorkflowState,
        *,
        step_name: str,
        llm_target: LLMTarget,
        output: str,
    ) -> list[dict[str, Any]]:
        history = list(state.get("history", []))
        history.append({"step_name": step_name, "llm_target": llm_target.name, "output": output})
        return history

    def _build_workflow(self):
        graph = StateGraph(NonRecursiveWorkflowState)

        def implement_pass(state: NonRecursiveWorkflowState) -> NonRecursiveWorkflowState:
            self._log("node enter: implement_pass")
            trainer_exists = os.path.exists(self.trainer_file_path)
            if trainer_exists:
                action_instruction = (
                    "The trainer file already exists. Review the current implementation and modify it directly "
                    "to improve correctness and quality."
                )
            else:
                action_instruction = (
                    "The trainer file does not exist. Create it at the exact trainer path and provide a complete "
                    "initial implementation."
                )
            prompt = self.implement_prompt.format(
                trainer_file=self.trainer_file_path,
                generated_dir=self.generated_dir,
                trainer_exists=str(trainer_exists).lower(),
                action_instruction=action_instruction,
            )
            output = self.run_agent(LLMTarget.GEMINI, prompt, step_name="implement_pass")
            return {"history": self._append_history(state, step_name="implement_pass", llm_target=LLMTarget.GEMINI, output=output)}

        def review_pass(state: NonRecursiveWorkflowState) -> NonRecursiveWorkflowState:
            self._log("node enter: review_pass")
            if os.path.exists(self.code_need_fix_status_file_path):
                os.remove(self.code_need_fix_status_file_path)

            prompt = self.review_prompt.format(
                trainer_file=self.trainer_file_path,
                fix_status_file=self.code_need_fix_status_file_path,
            )
            output = self.run_agent(LLMTarget.CODEX, prompt, step_name="review_pass")
            return {
                "implement_attempt": state.get("implement_attempt", 0) + 1,
                "needs_fix": os.path.exists(self.code_need_fix_status_file_path),
                "history": self._append_history(state, step_name="review_pass", llm_target=LLMTarget.CODEX, output=output),
            }

        def route_after_review(state: NonRecursiveWorkflowState) -> str:
            if state.get("needs_fix", False) and state.get("implement_attempt", 0) < self.max_implement_retries:
                self._log(
                    f"route_after_review -> implement_pass "
                    f"attempt={state.get('implement_attempt', 0)} needs_fix=true"
                )
                return "implement_pass"
            if state.get("needs_fix", False):
                self._log(
                    f"route_after_review -> fallback_fix "
                    f"attempt={state.get('implement_attempt', 0)} needs_fix=true"
                )
                return "fallback_fix"
            self._log("route_after_review -> final_validation needs_fix=false")
            return "final_validation"

        def fallback_fix(state: NonRecursiveWorkflowState) -> NonRecursiveWorkflowState:
            self._log("node enter: fallback_fix")
            if os.path.exists(self.code_need_fix_status_file_path):
                os.remove(self.code_need_fix_status_file_path)

            prompt = self.fallback_fix_prompt.format(trainer_file=self.trainer_file_path)
            output = self.run_agent(LLMTarget.CODEX, prompt, step_name="fallback_fix")
            return {"history": self._append_history(state, step_name="fallback_fix", llm_target=LLMTarget.CODEX, output=output)}

        def final_validation(state: NonRecursiveWorkflowState) -> NonRecursiveWorkflowState:
            self._log("node enter: final_validation")
            prompt = self.final_validation_prompt.format(
                trainer_file=self.trainer_file_path,
                model_ready_file=self.model_ready_status_file_path,
            )
            output = self.run_agent(LLMTarget.CODEX, prompt, step_name="final_validation")
            return {
                "model_ready": os.path.exists(self.model_ready_status_file_path),
                "history": self._append_history(state, step_name="final_validation", llm_target=LLMTarget.CODEX, output=output),
            }

        def route_after_final_validation(state: NonRecursiveWorkflowState) -> str:
            if state.get("model_ready", False):
                self._log("route_after_final_validation -> complete model_ready=true")
                return "complete"
            if self.current_depth >= self.max_depth:
                self._log(
                    "route_after_final_validation -> complete "
                    f"current_depth={self.current_depth} max_depth={self.max_depth}"
                )
                return "complete"
            if self.discussion_loop <= 0:
                self._log("route_after_final_validation -> complete discussion_loop<=0")
                return "complete"
            self._log("route_after_final_validation -> discussion_turn")
            return "discussion_turn"

        def discussion_turn(state: NonRecursiveWorkflowState) -> NonRecursiveWorkflowState:
            self._log(
                f"node enter: discussion_turn round={state.get('discussion_round', 0) + 1} "
                f"llm_index={state.get('llm_index', 0)}"
            )
            llm_index = state.get("llm_index", 0)
            llm_target = self.usage_llm_models[llm_index]
            round_index = state.get("discussion_round", 0)
            prompt = self.discussion_prompt.format(
                round_index=round_index + 1,
                llm_name=llm_target.name,
                trainer_file=self.trainer_file_path,
                ready_file=self.implement_plan_ready_status_file_path,
                conflict_file=self.conflicting_idea_status_file_path,
            )
            output = self.run_agent(
                llm_target,
                prompt,
                step_name=f"discussion_round_{round_index + 1}_{llm_target.name.lower()}",
            )

            next_llm_index = llm_index + 1
            next_round_index = round_index
            if next_llm_index >= len(self.usage_llm_models):
                next_llm_index = 0
                next_round_index += 1

            return {
                "llm_index": next_llm_index,
                "discussion_round": next_round_index,
                "discussion_stop": self.should_stop_discussion(),
                "history": self._append_history(
                    state,
                    step_name=f"discussion_round_{round_index + 1}_{llm_target.name.lower()}",
                    llm_target=llm_target,
                    output=output,
                ),
            }

        def route_after_discussion_turn(state: NonRecursiveWorkflowState) -> str:
            if state.get("discussion_stop", False):
                self._log("route_after_discussion_turn -> complete discussion_stop=true")
                return "complete"
            if state.get("discussion_round", 0) >= self.discussion_loop:
                self._log(
                    "route_after_discussion_turn -> complete "
                    f"discussion_round={state.get('discussion_round', 0)}"
                )
                return "complete"
            self._log("route_after_discussion_turn -> discussion_turn")
            return "discussion_turn"

        def complete(state: NonRecursiveWorkflowState) -> NonRecursiveWorkflowState:
            self._log("node enter: complete")
            if state.get("model_ready", False):
                reason: NonRecursiveWorkflowState["final_reason"] = "model_ready"
                self.record_status_node("model_ready", "Model Ready", "palegreen")
            elif self.current_depth >= self.max_depth:
                reason = "max_depth_reached"
                self.record_status_node("max_depth", f"Max Depth {self.max_depth}", "lightcoral")
            elif state.get("discussion_stop", False):
                reason = "discussion_stop"
                self.record_status_node("discussion_stop", "Discussion Stop", "khaki")
            elif self.discussion_loop <= 0:
                reason = "no_discussion_loop"
            else:
                reason = "discussion_rounds_done"

            self.record_status_node("non_recursive_end", f"Non-Recursive End\\n{reason}", "lightgrey")
            self._log(f"non-recursive workflow finished reason={reason}")
            return {"final_reason": reason}

        graph.add_node("implement_pass", implement_pass)
        graph.add_node("review_pass", review_pass)
        graph.add_node("fallback_fix", fallback_fix)
        graph.add_node("final_validation", final_validation)
        graph.add_node("discussion_turn", discussion_turn)
        graph.add_node("complete", complete)

        graph.set_entry_point("implement_pass")
        graph.add_edge("implement_pass", "review_pass")
        graph.add_conditional_edges(
            "review_pass",
            route_after_review,
            {
                "implement_pass": "implement_pass",
                "fallback_fix": "fallback_fix",
                "final_validation": "final_validation",
            },
        )
        graph.add_edge("fallback_fix", "final_validation")
        graph.add_conditional_edges(
            "final_validation",
            route_after_final_validation,
            {
                "discussion_turn": "discussion_turn",
                "complete": "complete",
            },
        )
        graph.add_conditional_edges(
            "discussion_turn",
            route_after_discussion_turn,
            {
                "discussion_turn": "discussion_turn",
                "complete": "complete",
            },
        )
        graph.add_edge("complete", END)
        return graph.compile()

    def _build_discussion_workflow(self):
        graph = StateGraph(NonRecursiveWorkflowState)

        def discussion_turn(state: NonRecursiveWorkflowState) -> NonRecursiveWorkflowState:
            self._log(
                f"node enter: discussion_only_turn round={state.get('discussion_round', 0) + 1} "
                f"llm_index={state.get('llm_index', 0)}"
            )
            llm_index = state.get("llm_index", 0)
            llm_target = self.usage_llm_models[llm_index]
            round_index = state.get("discussion_round", 0)
            prompt = self.discussion_prompt.format(
                round_index=round_index + 1,
                llm_name=llm_target.name,
                trainer_file=self.trainer_file_path,
                ready_file=self.implement_plan_ready_status_file_path,
                conflict_file=self.conflicting_idea_status_file_path,
            )
            output = self.run_agent(
                llm_target,
                prompt,
                step_name=f"discussion_only_round_{round_index + 1}_{llm_target.name.lower()}",
            )

            next_llm_index = llm_index + 1
            next_round_index = round_index
            if next_llm_index >= len(self.usage_llm_models):
                next_llm_index = 0
                next_round_index += 1

            return {
                "llm_index": next_llm_index,
                "discussion_round": next_round_index,
                "discussion_stop": self.should_stop_discussion(),
                "history": self._append_history(
                    state,
                    step_name=f"discussion_only_round_{round_index + 1}_{llm_target.name.lower()}",
                    llm_target=llm_target,
                    output=output,
                ),
            }

        def route_after_discussion_turn(state: NonRecursiveWorkflowState) -> str:
            if state.get("discussion_stop", False):
                self._log("route_after_discussion_only_turn -> complete discussion_stop=true")
                return "complete"
            if state.get("discussion_round", 0) >= self.discussion_loop:
                self._log(
                    "route_after_discussion_only_turn -> complete "
                    f"discussion_round={state.get('discussion_round', 0)}"
                )
                return "complete"
            self._log("route_after_discussion_only_turn -> discussion_turn")
            return "discussion_turn"

        def complete(state: NonRecursiveWorkflowState) -> NonRecursiveWorkflowState:
            self._log("node enter: discussion_only_complete")
            if state.get("discussion_stop", False):
                reason: NonRecursiveWorkflowState["final_reason"] = "discussion_stop"
                self.record_status_node("discussion_stop", "Discussion Stop", "khaki")
            elif self.discussion_loop <= 0:
                reason = "no_discussion_loop"
            else:
                reason = "discussion_rounds_done"

            self.record_status_node("non_recursive_end", f"Non-Recursive End\\n{reason}", "lightgrey")
            self._log(f"non-recursive discussion finished reason={reason}")
            return {"final_reason": reason}

        graph.add_node("discussion_turn", discussion_turn)
        graph.add_node("complete", complete)

        graph.set_entry_point("discussion_turn")
        graph.add_conditional_edges(
            "discussion_turn",
            route_after_discussion_turn,
            {
                "discussion_turn": "discussion_turn",
                "complete": "complete",
            },
        )
        graph.add_edge("complete", END)
        return graph.compile()

    def implement_code(self) -> dict[str, Any]:
        self._log("workflow invoke: implement_code")
        initial_state: NonRecursiveWorkflowState = {
            "implement_attempt": 0,
            "needs_fix": False,
            "model_ready": os.path.exists(self.model_ready_status_file_path),
            "discussion_round": 0,
            "llm_index": 0,
            "discussion_stop": self.should_stop_discussion(),
            "history": [],
        }
        result = self.workflow.invoke(
            initial_state,
            config=self._langchain_config(
                run_name="non_recursive_workflow",
                tags=["workflow", "non-recursive"],
            ),
        )
        self._log(f"workflow done: implement_code final_reason={result.get('final_reason')}")
        return result

    def improve_implement_plan(self) -> dict[str, Any]:
        self._log("workflow invoke: improve_implement_plan")
        initial_state: NonRecursiveWorkflowState = {
            "needs_fix": False,
            "model_ready": False,
            "discussion_round": 0,
            "llm_index": 0,
            "discussion_stop": self.should_stop_discussion(),
            "history": [],
        }
        result = self.discussion_workflow.invoke(
            initial_state,
            config=self._langchain_config(
                run_name="non_recursive_discussion_only",
                tags=["workflow", "non-recursive", "discussion"],
            ),
        )
        self._log(f"workflow done: improve_implement_plan final_reason={result.get('final_reason')}")
        return result

    def clear_discussion_stop_statuses(self):
        for path in self.discussion_state_file_paths().values():
            if os.path.exists(path):
                os.remove(path)
        self.update_discussion_state()

    def flush_traces(self):
        self.langsmith_client.flush()

    def export_flow_graph(self):
        output_dir = Path(self.graph_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"{self.task_id}_flow_non_recursive"
        dot_path = output_dir / f"{base_name}.dot"

        lines = [
            "digraph NonRecursiveSessionFlow {",
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
        if dot_exe:
            subprocess.run([dot_exe, "-Tpng", str(dot_path), "-o", str(output_dir / f"{base_name}.png")], check=False)
            subprocess.run([dot_exe, "-Tsvg", str(dot_path), "-o", str(output_dir / f"{base_name}.svg")], check=False)
        return dot_path


if __name__ == "__main__":
    agent_executor = LangChainNonRecursiveSessionService("bti_xgb", "bti_xgb_1")
    agent_executor.clear_discussion_stop_statuses()
    agent_executor.implement_code()
    agent_executor.export_flow_graph()
    agent_executor.flush_traces()
