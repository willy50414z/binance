import json
import unittest
from datetime import datetime
from pathlib import Path

from com.willy.trade_bot.langchain.non_recursive_session_workflow import (
    LangChainNonRecursiveSessionService,
)
from com.willy.trade_bot.service import llm_svc


class TestNonRecursiveSessionWorkflow(unittest.TestCase):
    def setUp(self):
        self.log_path = Path("tmp_non_recursive_workflow_test.log")
        self.log_path.write_text("", encoding="utf-8")

    def _append_log(self, payload: dict):
        record = {"ts": datetime.now().isoformat(), **payload}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def test_run_with_same_params(self):
        original_run_once = llm_svc.run_once

        def wrapped_run_once(target, prompt, **kwargs):
            self._append_log(
                {
                    "event": "run_once_start",
                    "target": target.name,
                    "cwd": kwargs.get("cwd"),
                    "timeout": kwargs.get("timeout"),
                    "prompt": prompt,
                }
            )
            try:
                output = original_run_once(target, prompt, **kwargs)
                self._append_log(
                    {
                        "event": "run_once_done",
                        "target": target.name,
                        "output_len": len(output),
                    }
                )
                return output
            except Exception as exc:
                self._append_log(
                    {
                        "event": "run_once_error",
                        "target": target.name,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                raise

        llm_svc.run_once = wrapped_run_once
        try:
            self._append_log({"event": "workflow_start"})
            svc = LangChainNonRecursiveSessionService(
                "bti_xgb",
                "bti_xgb_1",
                discussion_loop=3,
                current_depth=0,
                max_depth=5,
                max_implement_retries=3,
            )
            svc.clear_discussion_stop_statuses()
            result = svc.implement_code()
            svc.flush_traces()
            self._append_log({"event": "workflow_end", "result": result})
            self.assertIn("final_reason", result)
        finally:
            llm_svc.run_once = original_run_once


if __name__ == "__main__":
    unittest.main()
