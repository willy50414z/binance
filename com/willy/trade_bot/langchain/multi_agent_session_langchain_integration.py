from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from langchain_core.runnables import RunnableLambda

from com.willy.trade_bot.enums import LLMTarget
from com.willy.trade_bot.langchain.session_runtime import LangChainSessionRuntime


class ImplementWorkflowState(TypedDict, total=False):
    attempt: int
    needs_fix: bool
    post_action: Literal["done", "improve"]


class ImproveWorkflowState(TypedDict, total=False):
    round_index: int
    llm_index: int
    stop: bool


class LangChainMultiAgentSessionService(LangChainSessionRuntime):
    def __init__(
        self,
        strategy_name: str,
        version: str,
        discussion_loop: int = 3,
        current_depth: int = 0,
        max_depth: int = 5,
        max_workers: int = 2,
        graph_state: dict | None = None,
        graph_lock=None,
        graph_output_dir: str | None = None,
        application_ini_path: str | None = None,
        langsmith_client=None,
        langsmith_project: str | None = None,
    ):
        super().__init__(
            strategy_name=strategy_name,
            version=version,
            discussion_loop=discussion_loop,
            current_depth=current_depth,
            max_depth=max_depth,
            max_workers=max_workers,
            graph_state=graph_state,
            graph_lock=graph_lock,
            graph_output_dir=graph_output_dir,
            application_ini_path=application_ini_path,
            langsmith_client=langsmith_client,
            langsmith_project=langsmith_project,
        )
        self._implement_workflow = self._build_implement_workflow()
        self._improve_workflow = self._build_improve_workflow()
        self.implement_runnable = RunnableLambda(self._implement_code_impl)
        self.improve_plan_runnable = RunnableLambda(self._improve_implement_plan_impl)

    def should_stop_discussion(self) -> bool:
        return any(self.update_discussion_state().values())

    def build_next_version(self, llm_target: LLMTarget) -> str:
        version_prefix, _, version_suffix = self.version.rpartition("_")
        if not version_prefix or not version_suffix.isdigit():
            raise ValueError(f"unsupported version format: {self.version}")

        if llm_target == self.usage_llm_models[-1]:
            return f"{version_prefix}_{int(version_suffix) + 1}"
        return f"{version_prefix}_{llm_target.name}_1"

    def _spawn_children(self) -> None:
        child_services = []
        for llm_target in self.usage_llm_models:
            new_version = self.build_next_version(llm_target)
            session_file_name = self.get_session_file_name(llm_target)
            child_service = LangChainMultiAgentSessionService(
                self.strategy_name,
                new_version,
                discussion_loop=self.discussion_loop,
                current_depth=self.current_depth + 1,
                max_depth=self.max_depth,
                max_workers=self.max_workers,
                graph_state=self.graph_state,
                graph_lock=self.graph_lock,
                graph_output_dir=self.graph_output_dir,
                application_ini_path=str(self.application_ini_path),
                langsmith_client=self.langsmith_client,
                langsmith_project=self.langsmith_project,
            )
            self.register_edge(self.service_node_id, child_service.service_node_id, f"spawn {llm_target.name}")

            self.run_agent(
                llm_target,
                self.prompt_builder.handoff_prompt(
                    new_version=new_version,
                    new_session_dir=child_service.session_dir,
                    session_file_name=session_file_name,
                    last_session_name=self.last_session_name,
                ),
                session_file_name,
            )
            child_services.append(child_service)

        worker_count = min(self.max_workers, len(child_services))
        executor_node_id = f"executor::{self.task_id}::{self.next_graph_sequence()}"
        self.register_node(
            executor_node_id,
            f"ThreadPoolExecutor\\nmax_workers={worker_count}",
            shape="component",
            color="lightskyblue",
            style="filled",
        )
        self.register_edge(self.service_node_id, executor_node_id, "execute children")
        for child_service in child_services:
            self.register_edge(executor_node_id, child_service.service_node_id, "submit")

        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="multi-agent-session") as executor:
            futures = [executor.submit(child_service.implement_code) for child_service in child_services]
            for future in as_completed(futures):
                future.result()

    def _build_implement_workflow(self):
        max_retries = 3
        graph = StateGraph(ImplementWorkflowState)

        def init_state(_: ImplementWorkflowState) -> ImplementWorkflowState:
            return {"attempt": 0, "needs_fix": False}

        def implement_pass(state: ImplementWorkflowState) -> ImplementWorkflowState:
            self.run_agent(
                LLMTarget.GEMINI,
                self.prompt_builder.implement_prompt(
                    last_session_name=self.last_session_name,
                    trainer_exists=os.path.exists(self.trainer_file_path),
                ),
                self.last_session_name,
            )
            return state

        def review_pass(state: ImplementWorkflowState) -> ImplementWorkflowState:
            if os.path.exists(self.code_need_fix_status_file_path):
                os.remove(self.code_need_fix_status_file_path)

            session_file_name = self.get_session_file_name(LLMTarget.CODEX)
            self.run_agent(
                LLMTarget.CODEX,
                self.prompt_builder.review_prompt(
                    session_file_name=session_file_name,
                    last_session_name=self.last_session_name,
                ),
                session_file_name,
            )
            return {
                "attempt": state.get("attempt", 0) + 1,
                "needs_fix": os.path.exists(self.code_need_fix_status_file_path),
            }

        def route_after_review(state: ImplementWorkflowState) -> str:
            if state.get("needs_fix", False) and state.get("attempt", 0) < max_retries:
                return "implement_pass"
            if state.get("needs_fix", False):
                return "fallback_fix"
            return "final_validation"

        def fallback_fix(state: ImplementWorkflowState) -> ImplementWorkflowState:
            if os.path.exists(self.code_need_fix_status_file_path):
                os.remove(self.code_need_fix_status_file_path)
            self.run_agent(
                LLMTarget.CODEX,
                self.prompt_builder.implement_prompt(
                    last_session_name=self.last_session_name,
                    trainer_exists=os.path.exists(self.trainer_file_path),
                ),
                self.last_session_name,
            )
            return state

        def final_validation(state: ImplementWorkflowState) -> ImplementWorkflowState:
            session_file_name = self.get_session_file_name(LLMTarget.CODEX)
            self.run_agent(
                LLMTarget.CODEX,
                self.prompt_builder.final_validation_prompt(session_file_name=session_file_name),
                session_file_name,
            )
            return state

        def post_validation(state: ImplementWorkflowState) -> ImplementWorkflowState:
            if os.path.exists(self.model_ready_status_file_path):
                self.record_status_node("model_ready", "Model Ready", "palegreen")
                print(f"model ready, strategy[{self.strategy_name}] version[{self.version}]")
                return {"post_action": "done"}

            if self.current_depth >= self.max_depth:
                self.record_status_node("max_depth", f"Max Depth {self.max_depth}", "lightcoral")
                print(
                    f"max depth reached, stop improving strategy[{self.strategy_name}] "
                    f"version[{self.version}] depth[{self.current_depth}]"
                )
                return {"post_action": "done"}

            return {"post_action": "improve"}

        def route_post_validation(state: ImplementWorkflowState) -> str:
            return state.get("post_action", "done")

        def invoke_improve_plan(state: ImplementWorkflowState) -> ImplementWorkflowState:
            self.improve_plan_runnable.invoke(
                {},
                config=self._langchain_config(
                    run_name="improve_implement_plan",
                    tags=["discussion", "workflow-subcall"],
                ),
            )
            return state

        graph.add_node("init", init_state)
        graph.add_node("implement_pass", implement_pass)
        graph.add_node("review_pass", review_pass)
        graph.add_node("fallback_fix", fallback_fix)
        graph.add_node("final_validation", final_validation)
        graph.add_node("post_validation", post_validation)
        graph.add_node("invoke_improve_plan", invoke_improve_plan)

        graph.set_entry_point("init")
        graph.add_edge("init", "implement_pass")
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
        graph.add_edge("final_validation", "post_validation")
        graph.add_conditional_edges(
            "post_validation",
            route_post_validation,
            {
                "done": END,
                "improve": "invoke_improve_plan",
            },
        )
        graph.add_edge("invoke_improve_plan", END)
        return graph.compile()

    def _build_improve_workflow(self):
        graph = StateGraph(ImproveWorkflowState)

        def init_state(_: ImproveWorkflowState) -> ImproveWorkflowState:
            return {
                "round_index": 0,
                "llm_index": 0,
                "stop": self.should_stop_discussion(),
            }

        def route_after_init(state: ImproveWorkflowState) -> str:
            if state.get("stop", False):
                return "discussion_stop"
            if state.get("round_index", 0) >= self.discussion_loop:
                return "spawn_children"
            return "discussion_turn"

        def discussion_turn(state: ImproveWorkflowState) -> ImproveWorkflowState:
            llm_index = state.get("llm_index", 0)
            llm_target = self.usage_llm_models[llm_index]
            session_file_name = self.get_session_file_name(llm_target)
            self.run_agent(
                llm_target,
                self.prompt_builder.discussion_prompt(
                    session_file_name=session_file_name,
                    last_session_name=self.last_session_name,
                ),
                session_file_name,
            )

            next_llm_index = llm_index + 1
            next_round_index = state.get("round_index", 0)
            if next_llm_index >= len(self.usage_llm_models):
                next_llm_index = 0
                next_round_index += 1

            return {
                "llm_index": next_llm_index,
                "round_index": next_round_index,
                "stop": self.should_stop_discussion(),
            }

        def route_after_turn(state: ImproveWorkflowState) -> str:
            if state.get("stop", False):
                return "discussion_stop"
            if state.get("round_index", 0) >= self.discussion_loop:
                return "spawn_children"
            return "discussion_turn"

        def discussion_stop(state: ImproveWorkflowState) -> ImproveWorkflowState:
            self.record_status_node("discussion_stop", "Discussion Stop", "khaki")
            return state

        def spawn_children(state: ImproveWorkflowState) -> ImproveWorkflowState:
            self._spawn_children()
            return state

        graph.add_node("init", init_state)
        graph.add_node("discussion_turn", discussion_turn)
        graph.add_node("discussion_stop", discussion_stop)
        graph.add_node("spawn_children", spawn_children)

        graph.set_entry_point("init")
        graph.add_conditional_edges(
            "init",
            route_after_init,
            {
                "discussion_turn": "discussion_turn",
                "discussion_stop": "discussion_stop",
                "spawn_children": "spawn_children",
            },
        )
        graph.add_conditional_edges(
            "discussion_turn",
            route_after_turn,
            {
                "discussion_turn": "discussion_turn",
                "discussion_stop": "discussion_stop",
                "spawn_children": "spawn_children",
            },
        )
        graph.add_edge("discussion_stop", END)
        graph.add_edge("spawn_children", END)
        return graph.compile()

    def _implement_code_impl(self, _: dict[str, Any]) -> None:
        self._implement_workflow.invoke(
            {},
            config=self._langchain_config(
                run_name="implement_code_workflow",
                tags=["workflow", "implementation"],
            ),
        )

    def _improve_implement_plan_impl(self, _: dict[str, Any]) -> None:
        self._improve_workflow.invoke(
            {},
            config=self._langchain_config(
                run_name="improve_implement_plan_workflow",
                tags=["workflow", "discussion"],
            ),
        )

    def implement_code(self):
        self.implement_runnable.invoke(
            {},
            config=self._langchain_config(
                run_name="implement_code",
                tags=["implementation"],
            ),
        )

    def improve_implement_plan(self):
        self.improve_plan_runnable.invoke(
            {},
            config=self._langchain_config(
                run_name="improve_implement_plan",
                tags=["discussion"],
            ),
        )


if __name__ == "__main__":
    agent_executor = LangChainMultiAgentSessionService("bti_xgb", "bti_xgb_1")
    agent_executor.clear_discussion_stop_statuses()
    agent_executor.implement_code()
    agent_executor.export_flow_graph()
    agent_executor.flush_traces()
