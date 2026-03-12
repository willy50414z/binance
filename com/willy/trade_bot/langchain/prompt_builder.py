from __future__ import annotations


class LangChainPromptBuilder:
    def __init__(
        self,
        *,
        session_dir: str,
        trainer_file_path: str,
        trained_model_path: str,
        implement_plan_ready_status_file_path: str,
        conflicting_idea_status_file_path: str,
        code_need_fix_status_file_path: str,
        model_ready_status_file_path: str,
    ):
        self.session_dir = session_dir
        self.trainer_file_path = trainer_file_path
        self.trained_model_path = trained_model_path
        self.implement_plan_ready_status_file_path = implement_plan_ready_status_file_path
        self.conflicting_idea_status_file_path = conflicting_idea_status_file_path
        self.code_need_fix_status_file_path = code_need_fix_status_file_path
        self.model_ready_status_file_path = model_ready_status_file_path

    def _previous_session(self, last_session_name: str) -> str:
        return f"{self.session_dir}{last_session_name}" if last_session_name else "None"

    def discussion_prompt(self, *, session_file_name: str, last_session_name: str) -> str:
        previous_session = self._previous_session(last_session_name)
        return (
            "You are continuing an ML strategy implementation discussion.\n"
            f"Previous session markdown: {previous_session}\n"
            f"Write this turn output to: {self.session_dir}{session_file_name}\n"
            "Refine the plan with concrete implementation details, data-split correctness, and leakage checks.\n"
            f"If the plan is ready, create this status file: {self.implement_plan_ready_status_file_path}\n"
            f"If critical conflicting ideas remain, create this status file: {self.conflicting_idea_status_file_path}\n"
            "Keep your response concise and decision-focused."
        )

    def implement_prompt(self, *, last_session_name: str, trainer_exists: bool) -> str:
        previous_session = self._previous_session(last_session_name)
        action = "update" if trainer_exists else "create"
        return (
            "Implement a Python ML trainer based on the latest approved discussion.\n"
            f"Previous session markdown: {previous_session}\n"
            f"Action: {action} trainer file {self.trainer_file_path}\n"
            f"Generated artifacts directory: {self.trained_model_path}\n"
            "Apply minimal targeted changes and keep time-series correctness."
        )

    def review_prompt(self, *, session_file_name: str, last_session_name: str) -> str:
        previous_session = self._previous_session(last_session_name)
        return (
            "Review trainer implementation against the latest discussion and implementation context.\n"
            f"Trainer file: {self.trainer_file_path}\n"
            f"Reference session markdown: {previous_session}\n"
            f"Write review to: {self.session_dir}{session_file_name}\n"
            f"If more fixes are required, create this status file: {self.code_need_fix_status_file_path}\n"
            "Return concrete issues and required fixes only."
        )

    def final_validation_prompt(self, *, session_file_name: str) -> str:
        return (
            "Perform final readiness review for the trainer.\n"
            f"Trainer file: {self.trainer_file_path}\n"
            f"Write final review to: {self.session_dir}{session_file_name}\n"
            f"If model and code are ready, create this status file: {self.model_ready_status_file_path}\n"
            "Verify implementation quality, leakage safety, and reproducibility."
        )

    def handoff_prompt(
        self,
        *,
        new_version: str,
        new_session_dir: str,
        session_file_name: str,
        last_session_name: str,
    ) -> str:
        previous_session = self._previous_session(last_session_name)
        return (
            "Prepare a concise handoff summary for a child branch of this strategy.\n"
            f"Current session markdown: {previous_session}\n"
            f"Child version: {new_version}\n"
            f"Write handoff session markdown to: {new_session_dir}{session_file_name}\n"
            "Focus on unresolved issues, concrete next implementation actions, and expected validation criteria."
        )
