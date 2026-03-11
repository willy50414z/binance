import os
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from com.willy.trade_bot.enums import LLMTarget
from com.willy.trade_bot.service import llm_svc


class MultiAgentSessionService:

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
    ):
        self.version = version
        self.discussion_loop = discussion_loop
        self.current_depth = current_depth
        self.max_depth = max_depth
        self.max_workers = max(1, max_workers)
        self.strategy_name = strategy_name
        self.task_id = f"{self.strategy_name}_{self.version}"
        self.workspace_dir = Path(".").resolve()
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

    @staticmethod
    def get_session_file_name(llm_name: LLMTarget) -> str:
        return f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{llm_name.name}.md"

    @staticmethod
    def sanitize_graph_label(value: str) -> str:
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")

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
        output = llm_svc.run_once(llm_target, prompt)
        self.stack_trace.append(
            {
                "target_llm": llm_target.name,
                "prompt": prompt,
                "output": output,
                "task_id": self.task_id,
            }
        )
        print(f"output[{output}]")
        self.last_session_name = session_file_name

    def should_stop_discussion(self) -> bool:
        return (
            os.path.exists(self.implement_plan_ready_status_file_path)
            or os.path.exists(self.conflicting_idea_status_file_path)
        )

    def build_next_version(self, llm_target: LLMTarget) -> str:
        version_prefix, _, version_suffix = self.version.rpartition("_")
        if not version_prefix or not version_suffix.isdigit():
            raise ValueError(f"unsupported version format: {self.version}")

        if llm_target == self.usage_llm_models[-1]:
            return f"{version_prefix}_{int(version_suffix) + 1}"
        return f"{version_prefix}_{llm_target.name}_1"

    def implement_code(self):
        for _ in range(3):
            action = "修改" if os.path.exists(self.trainer_file_path) else "建立"
            self.run_agent(
                LLMTarget.GEMINI,
                f"請以一個專業 Python 工程師的角度，依照 {self.session_dir}{self.last_session_name} {action} "
                f"{self.trainer_file_path}，並將模型輸出到 {self.trained_model_path}",
                self.last_session_name,
            )

            if os.path.exists(self.code_need_fix_status_file_path):
                os.remove(self.code_need_fix_status_file_path)

            implement_code_session_file_name = self.get_session_file_name(LLMTarget.CODEX)
            self.run_agent(
                LLMTarget.CODEX,
                f"請以一個專業 Python 工程師的角度，檢查 {self.trainer_file_path} 是否有依照 "
                f"{self.session_dir}{self.last_session_name} 修改。若仍需修正，請直接修改程式並把說明輸出到 "
                f"{self.session_dir}{implement_code_session_file_name}；若仍有問題，請建立空白檔案 "
                f"{self.code_need_fix_status_file_path}",
                implement_code_session_file_name,
            )

            if not os.path.exists(self.code_need_fix_status_file_path):
                break

        if os.path.exists(self.code_need_fix_status_file_path):
            os.remove(self.code_need_fix_status_file_path)
            self.run_agent(
                LLMTarget.CODEX,
                f"請直接完成 {self.trainer_file_path} 的修正，並依照 {self.session_dir}{self.last_session_name} "
                f"的規劃調整模型輸出到 {self.trained_model_path}",
                self.last_session_name,
            )

        implement_code_session_file_name = self.get_session_file_name(LLMTarget.CODEX)
        self.run_agent(
            LLMTarget.CODEX,
            f"請執行 {self.trainer_file_path} 的訓練流程，將訓練結果與後續建議輸出到 "
            f"{self.session_dir}{implement_code_session_file_name}。若模型結果已可接受，請建立空白檔案 "
            f"{self.model_ready_status_file_path}",
            implement_code_session_file_name,
        )

        if os.path.exists(self.model_ready_status_file_path):
            self.record_status_node("model_ready", "Model Ready", "palegreen")
            print(f"model ready, strategy[{self.strategy_name}] version[{self.version}]")
            return

        if self.current_depth >= self.max_depth:
            self.record_status_node("max_depth", f"Max Depth {self.max_depth}", "lightcoral")
            print(
                f"max depth reached, stop improving strategy[{self.strategy_name}] "
                f"version[{self.version}] depth[{self.current_depth}]"
            )
            return

        self.improve_implement_plan()

    def improve_implement_plan(self):
        is_need_to_stop_discuss_loop = False
        for _ in range(self.discussion_loop):
            for llm_target in self.usage_llm_models:
                if self.should_stop_discussion():
                    is_need_to_stop_discuss_loop = True
                    break

                session_file_name = self.get_session_file_name(llm_target)
                self.run_agent(
                    llm_target,
                    f"請以一個 ML 專家的角度檢視 {self.session_dir}{self.last_session_name} 的執行計畫有沒有需要修正或補充。"
                    f"如果完全同意目前規劃，請建立空白檔案 {self.implement_plan_ready_status_file_path}。"
                    f"如果有與現有規劃方向衝突但各有利弊的想法，請把分析寫到 "
                    f"{self.session_dir}{session_file_name}，並建立空白檔案 {self.conflicting_idea_status_file_path}",
                    session_file_name,
                )

                if self.should_stop_discussion():
                    is_need_to_stop_discuss_loop = True
                    break

            if is_need_to_stop_discuss_loop:
                break

        if is_need_to_stop_discuss_loop:
            self.record_status_node("discussion_stop", "Discussion Stop", "khaki")
            return

        child_services = []
        for llm_target in self.usage_llm_models:
            new_version = self.build_next_version(llm_target)
            session_file_name = self.get_session_file_name(llm_target)
            new_agent_session_service = MultiAgentSessionService(
                self.strategy_name,
                new_version,
                discussion_loop=self.discussion_loop,
                current_depth=self.current_depth + 1,
                max_depth=self.max_depth,
                max_workers=self.max_workers,
                graph_state=self.graph_state,
                graph_lock=self.graph_lock,
                graph_output_dir=self.graph_output_dir,
            )
            self.register_edge(self.service_node_id, new_agent_session_service.service_node_id, f"spawn {llm_target.name}")

            self.run_agent(
                llm_target,
                f"{self.session_dir}{self.last_session_name} 是目前最新的模型訓練改善執行計畫。"
                f"請延續這份計畫，為下一個版本 {new_version} 產出可執行的改善方案，並輸出到 "
                f"{new_agent_session_service.session_dir}{session_file_name}",
                session_file_name,
            )
            child_services.append(new_agent_session_service)

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


if __name__ == "__main__":
    agent_executor = MultiAgentSessionService("bti_xgb", "bti_xgb_1")
    stop_discuss_loop_file_list = [
        agent_executor.implement_plan_ready_status_file_path,
        agent_executor.conflicting_idea_status_file_path,
    ]

    for path in stop_discuss_loop_file_list:
        if os.path.exists(path):
            os.remove(path)

    agent_executor.implement_code()
    agent_executor.export_flow_graph()
