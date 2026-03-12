from __future__ import annotations

from pathlib import Path

from com.willy.trade_bot.cli_session_manager.models import StrategyWorkspace
from com.willy.trade_bot.enums.llm_target import LLMTarget


class PromptFactory:
    def __init__(self, workspace: StrategyWorkspace):
        self.workspace = workspace

    @staticmethod
    def _maybe_session(session_path: Path | None) -> str:
        if session_path is None:
            return "No previous session is available."
        return f"Previous session file: {session_path}"

    def discussion_prompt(
            self,
            *,
            instruction: str,
            previous_session: Path | None,
            stop_status_paths: list[Path],
    ) -> str:
        status_hint = "\n".join(
            f"- {path}" for path in stop_status_paths) if stop_status_paths else "- No stop status files"
        return (
            "You are continuing a multi-LLM engineering discussion.\n"
            f"Workspace strategy dir: {self.workspace.strategy_dir}\n"
            f"{self._maybe_session(previous_session)}\n"
            f"Instruction:\n{instruction}\n\n"
            "If the implementation plan is ready, write the decision into one of these status files:\n"
            f"{status_hint}\n"
            "If there is a conflicting idea that needs escalation, write that decision into the relevant status file.\n"
            "Respond with the discussion result only."
        )

    def implement_prompt(
            self,
            *,
            summary_instruction: str,
            previous_session: Path | None,
            generated_dir: Path,
    ) -> str:
        action = "update" if self.workspace.trainer_file_path.exists() else "create"
        return (
            "You are implementing a Python training component from a prior discussion.\n"
            f"{self._maybe_session(previous_session)}\n"
            f"Trainer file: {self.workspace.trainer_file_path}\n"
            f"Generated output directory: {generated_dir}\n"
            f"Task: {action} the trainer implementation.\n"
            f"Implementation guidance:\n{summary_instruction}\n"
            "Make the code changes directly and keep the implementation consistent with the discussion."
        )

    def review_prompt(
            self,
            *,
            previous_session: Path | None,
            fix_status_path: Path,
    ) -> str:
        return (
            "You are reviewing a Python implementation against the latest discussion.\n"
            f"{self._maybe_session(previous_session)}\n"
            f"Trainer file: {self.workspace.trainer_file_path}\n"
            f"If the code still needs fixes, create this status file: {fix_status_path}\n"
            "Review the code, list issues if any, and set the fix status only when another implementation pass is required."
        )

    def final_validation_prompt(
            self,
            *,
            previous_session: Path | None,
            success_status_path: Path,
    ) -> str:
        return (
            "You are performing a final readiness review for a Python training component.\n"
            f"{self._maybe_session(previous_session)}\n"
            f"Trainer file: {self.workspace.trainer_file_path}\n"
            f"If the trainer is ready, create this status file: {success_status_path}\n"
            "Validate whether the implementation is ready for the intended workflow and summarize remaining risks."
        )

    def handoff_prompt(
            self,
            *,
            llm_target: LLMTarget,
            new_version: str,
            previous_session: Path | None,
            child_session_dir: Path,
    ) -> str:
        return (
            "You are preparing a follow-up branch for another implementation attempt.\n"
            f"Previous session: {self._maybe_session(previous_session)}\n"
            f"Target LLM: {llm_target.name}\n"
            f"New version: {new_version}\n"
            f"Child session directory: {child_session_dir}\n"
            "Write a concise handoff summary that the child branch can continue from."
        )

    def flow_node_prompt(
            self,
            *,
            node_name: str,
            instruction: str,
            previous_session: Path | None,
            available_status_paths: list[Path],
    ) -> str:
        status_hint = "\n".join(
            f"- {path}" for path in available_status_paths) if available_status_paths else "- No status files"
        return (
            "You are running a declarative multi-LLM workflow node.\n"
            f"Workspace strategy dir: {self.workspace.strategy_dir}\n"
            f"Trainer file: {self.workspace.trainer_file_path}\n"
            f"{self._maybe_session(previous_session)}\n"
            f"Current node: {node_name}\n"
            f"Instruction:\n{instruction}\n\n"
            "Available status files:\n"
            f"{status_hint}\n"
            "Follow the instruction, update code or status files if the workflow requires it, and return the node result."
        )
