import os
from datetime import datetime
from pathlib import Path

from com.willy.trade_bot.enums import LLMTarget
from com.willy.trade_bot.service import llm_svc


class MultiAgentSessionService:

    def __init__(self, strategy: str):
        self.workspace_dir = Path(".").resolve()
        self.dt_str = datetime.now().strftime("%Y%m%d%H%M%S")

        self.trainer_file_path = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy}/model_trainer.py"
        self.trained_model_path = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy}/generated/model_{self.dt_str}/"
        self.code_change_final_plan_ready_file_path = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy}/status/code_change_final_plan_ready.txt"
        self.conflicting_idea_file_path = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy}/status/conflicting_idea.txt"
        self.session_dir = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy}/sessions/"

        self.last_session_name = ""

        self.stack_trace = []

    @staticmethod
    def get_session_file_name(llm_name: LLMTarget) -> str:
        return f"{datetime.now().strftime("%Y%m%d%H%M%S")}_{llm_name.name}.md"

    def run_agent(self, llm_target: LLMTarget, prompt: str):
        print(f"start call LLM[{llm_target.name}]prompt[{prompt}]")
        output = llm_svc.run_once(llm_target, prompt)
        self.stack_trace.append({
            "target_llm": llm_target.name
            , "prompt": prompt
            , "output": output
        })
        print(f"output[{output}]")
        self.last_session_name = session_file_name


if __name__ == '__main__':
    agent_executor = MultiAgentSessionService("bti_xgb_v1")
    stop_discuss_loop_file_list = [agent_executor.code_change_final_plan_ready_file_path,
                                   agent_executor.conflicting_idea_file_path]

    # 重新執行時刪除暫停檔
    for path in stop_discuss_loop_file_list:
        if os.path.exists(path):
            os.remove(path)

    # 執行ML訓練並產出報告
    session_file_name = agent_executor.get_session_file_name(LLMTarget.GEMINI)
    agent_executor.run_agent(LLMTarget.GEMINI,
                             f"請幫我修改{agent_executor.trainer_file_path}"
                             f"，將匯出的模型放到{agent_executor.trained_model_path}"
                             f"，並執行{agent_executor.trainer_file_path}產出模型訓練結果"
                             f"，將模型訓練結果及後續修改計畫匯出到{agent_executor.session_dir}{session_file_name}")
    print("=========FINISH training and export result=========")
    print(agent_executor.stack_trace)

    # 討論結果並提出下一步修改方向
    is_need_to_stop_discuss_loop = False
    for i in range(3):
        for llm_taget in [LLMTarget.GEMINI, LLMTarget.CODEX]:
            for path in stop_discuss_loop_file_list:
                if os.path.exists(path):
                    is_need_to_stop_discuss_loop = True
            if is_need_to_stop_discuss_loop:
                break
            session_file_name = agent_executor.get_session_file_name(llm_taget)
            agent_executor.run_agent(llm_taget,
                                     f"{agent_executor.session_dir}{agent_executor.last_session_name}是我的模型訓練結果及後續修改計畫"
                                     f"，請以一個ML專家的角度，幫我review {agent_executor.session_dir}{agent_executor.last_session_name}的訓練結果及修改計畫"
                                     f"，將訓練結果及修改計畫加上你的補充建議一併匯出到{agent_executor.session_dir}{session_file_name}"
                                     f"，沒有補充意見的話，且完全同意目前的修改計畫，請產出一個空白檔案{agent_executor.code_change_final_plan_ready_file_path}"
                                     f"，如果有遇到與{agent_executor.session_dir}{agent_executor.last_session_name}衝突的想法"
                                     f"(比如它覺得應該將停利條件設為10%，你覺得應該設為5%)這種沒有一定對錯的衝突點，請用表格的方式將2者各自的優劣一併寫到{agent_executor.session_dir}{session_file_name}"
                                     f"，並產出一個空白檔案{agent_executor.conflicting_idea_file_path}，讓我知道")

    print("=========FINISH discussion=========")
    print(agent_executor.stack_trace)
