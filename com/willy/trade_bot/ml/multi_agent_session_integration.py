import os
import threading
from datetime import datetime
from pathlib import Path

from com.willy.trade_bot.enums import LLMTarget
from com.willy.trade_bot.service import llm_svc


class MultiAgentSessionService:

    def __init__(self, strategy_name: str, version: str, discussion_loop: int = 3):
        self.version = version
        self.discussion_loop = discussion_loop
        self.strategy_name = strategy_name
        self.task_id = f"{self.strategy_name}_{self.version}"
        self.workspace_dir = Path(".").resolve()
        self.dt_str = datetime.now().strftime("%Y%m%d%H%M%S")

        self.trainer_file_path = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy_name}_{version}/model_trainer.py"
        self.trained_model_path = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy_name}_{version}/generated/model_{self.dt_str}/"
        self.session_dir = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy_name}_{version}/sessions/"

        # status file
        self.implement_plan_ready_status_file_path = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy_name}_{version}/status/implement_plan_ready_status_file.txt"
        self.conflicting_idea_status_file_path = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy_name}_{version}/status/conflicting_idea_status_file.txt"
        self.code_need_fix_status_file_path = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy_name}_{version}/status/code_need_fix_status_file.txt"
        self.model_ready_status_file_path = f"{self.workspace_dir}/com/willy/trade_bot/ml/{strategy_name}_{version}/status/model_ready_status_file.txt"

        self.last_session_name = ""

        self.usage_llm_models = [LLMTarget.GEMINI, LLMTarget.CODEX]

        self.stack_trace = []

    @staticmethod
    def get_session_file_name(llm_name: LLMTarget) -> str:
        return f"{datetime.now().strftime("%Y%m%d%H%M%S")}_{llm_name.name}.md"

    def run_agent(self, llm_target: LLMTarget, prompt: str, session_file_name: str):
        print(f"start call task_id[{self.task_id}]LLM[{llm_target.name}]prompt[{prompt}]")
        output = llm_svc.run_once(llm_target, prompt)
        self.stack_trace.append({
            "target_llm": llm_target.name
            , "prompt": prompt
            , "output": output
            , "task_id": self.task_id
        })
        print(f"output[{output}]")
        self.last_session_name = session_file_name

    def implement_code(self):
        for i in range(3):
            # 實現代碼
            # 不需更新session
            action = "修改" if os.path.exists(f"{self.trainer_file_path}") else "實現"
            self.run_agent(LLMTarget.GEMINI,
                           f"請以一個專業python工程師的角度，幫我依{self.session_dir}{self.last_session_name}{action}{self.trainer_file_path}"
                           f"，並將{self.trainer_file_path}匯出的model等資料路徑修改到{self.trained_model_path}"
                           , self.last_session_name)

            # 檢查代碼
            # 如果有檢查錯誤的紀錄，先移除
            if os.path.exists(self.code_need_fix_status_file_path):
                os.remove(self.code_need_fix_status_file_path)
            # 檢查代碼
            implement_code_session_file_name = self.get_session_file_name(LLMTarget.CODEX)
            self.run_agent(LLMTarget.CODEX,
                           f"請以一個專業python工程師的角度，幫我檢查{self.trainer_file_path}是不是有依照{self.session_dir}{self.last_session_name}修改"
                           f"，如果有，請執行{self.trainer_file_path}產出模型訓練結果，並將訓練結果及修改計畫匯出到{self.session_dir}{implement_code_session_file_name}"
                           f"，如果沒有，請將該如何修正，重新生成包含詳細說明及修改方式的執行計畫"
                           f"，並產出空的{self.code_need_fix_status_file_path}",
                           implement_code_session_file_name)

            # 代碼修改正確
            if not os.path.exists(self.code_need_fix_status_file_path):
                break

        # 修改了3輪還有問題，直接請codex自己改
        if os.path.exists(self.code_need_fix_status_file_path):
            os.remove(self.code_need_fix_status_file_path)
            self.run_agent(LLMTarget.CODEX,
                           f"請以一個專業python工程師的角度，幫我修改{self.trainer_file_path}"
                           f"，將匯出的模型放到{self.trained_model_path}"
                           f"，並在依{self.session_dir}{self.last_session_name}修改{self.trainer_file_path}",
                           self.last_session_name)

        # 執行並產出測試結果
        implement_code_session_file_name = self.get_session_file_name(LLMTarget.CODEX)
        self.run_agent(LLMTarget.CODEX,
                       f"執行{self.trainer_file_path}產出模型訓練結果"
                       f"，將模型訓練結果及後續修改計畫匯出到{self.session_dir}{implement_code_session_file_name}"
                       f"，如果模型訓練結果已經有潛力投入實戰，請幫我產出{self.model_ready_status_file_path}",
                       implement_code_session_file_name)

        if os.path.exists(self.model_ready_status_file_path):
            print(f"model ready, strategy[{self.strategy_name}]version[{self.version}]")
        else:
            # 還沒訓練出完整的模型 => 繼續改進執行計畫
            self.improve_implement_plan()

    def improve_implement_plan(self):
        # 討論結果並提出下一步修改方向
        is_need_to_stop_discuss_loop = False
        for i in range(self.discussion_loop):
            # 2個AI輪流對執行計畫做修改
            for llm_taget in self.usage_llm_models:
                # 達成共識就可以提早結束了
                if os.path.exists(agent_executor.implement_plan_ready_status_file_path):
                    break

                # 沒達成共識就繼續討論
                session_file_name = agent_executor.get_session_file_name(llm_taget)
                agent_executor.run_agent(llm_taget
                                         ,
                                         f"請以一個ML專家的角度檢視{self.session_dir}{self.last_session_name}的執行計畫有沒有需要修正或補充的"
                                         f"，如果沒有，請產出一個空白檔案{self.implement_plan_ready_status_file_path}，讓我知道你對這個執行計畫的內容完全認同"
                                         f"，如果有，請將你不認同的部分，補上詳細的原因、修改的方式，加上你認為有缺漏的部分，一併匯出到{self.session_dir}{session_file_name}",
                                         session_file_name)

        # 討論了多輪還沒討論出共識，各做各的
        if not is_need_to_stop_discuss_loop:
            for llm_taget in self.usage_llm_models:
                if llm_taget.name == self.usage_llm_models[-1].name:
                    new_version = f"{self.version[:self.version.rfind("_")]}_{int(self.version[self.version.rfind("_") + 1:]) + 1}"
                else:
                    new_version = f"{self.version[:self.version.rfind("_")]}_{llm_taget.name}_1"

                session_file_name = agent_executor.get_session_file_name(llm_taget)
                new_agent_session_service = MultiAgentSessionService(self.strategy_name, new_version)

                agent_executor.run_agent(llm_taget,
                                         f"{self.session_dir}{self.last_session_name}是目前最新的模型訓練改善執行計畫"
                                         f"，經過多次討論，還無法對下一次的執行計畫達成共識"
                                         f"，所以請你擷取你認同的改善項目，匯出你認為下一步的執行計畫到{new_agent_session_service.session_dir}{session_file_name}",
                                         session_file_name)

                # 最後一個才走主線程，其他都走async
                if llm_taget.name == self.usage_llm_models[-1].name:
                    new_agent_session_service.implement_code()
                else:
                    fork_session_thread = threading.Thread(target=new_agent_session_service.implement_code())
                    fork_session_thread.start()


# def implement_code(agent_executor):
#     # 執行ML訓練並產出報告
#     implement_code_session = agent_executor.get_session_file_name(LLMTarget.GEMINI)
#     agent_executor.run_agent(LLMTarget.GEMINI,
#                              f"請幫我修改{agent_executor.trainer_file_path}"
#                              f"，將匯出的模型放到{agent_executor.trained_model_path}"
#                              f"，並執行{agent_executor.trainer_file_path}產出模型訓練結果"
#                              f"，將模型訓練結果及後續修改計畫匯出到{agent_executor.session_dir}{implement_code_session}")
#     print("=========FINISH training and export result=========")
#     print(agent_executor.stack_trace)
#
#
# def generated_implement_plan():
#     # 討論結果並提出下一步修改方向
#     is_need_to_stop_discuss_loop = False
#     for i in range(3):
#         for llm_taget in [LLMTarget.GEMINI, LLMTarget.CODEX]:
#             for path in stop_discuss_loop_file_list:
#                 if os.path.exists(path):
#                     is_need_to_stop_discuss_loop = True
#             if is_need_to_stop_discuss_loop:
#                 break
#             session_file_name = agent_executor.get_session_file_name(llm_taget)
#             agent_executor.run_agent(llm_taget,
#                                      f"{agent_executor.session_dir}{agent_executor.last_session_name}是我的模型訓練結果及後續修改計畫"
#                                      f"，請以一個ML專家的角度，幫我review {agent_executor.session_dir}{agent_executor.last_session_name}的訓練結果及修改計畫"
#                                      f"，將訓練結果及修改計畫加上你的補充建議一併匯出到{agent_executor.session_dir}{session_file_name}"
#                                      f"，沒有補充意見的話，且完全同意目前的修改計畫，請產出一個空白檔案{agent_executor.implement_plan_ready_status_file_path}"
#                                      f"，如果有遇到與{agent_executor.session_dir}{agent_executor.last_session_name}衝突的想法"
#                                      f"(比如它覺得應該將停利條件設為10%，你覺得應該設為5%)這種沒有一定對錯的衝突點，請用表格的方式將2者各自的優劣一併寫到{agent_executor.session_dir}{session_file_name}"
#                                      f"，並產出一個空白檔案{agent_executor.conflicting_idea_file_path}，讓我知道")
#
#     print("=========FINISH discussion=========")
#     print(agent_executor.stack_trace)
#

if __name__ == '__main__':
    agent_executor = MultiAgentSessionService("bti_xgb", "bti_xgb_1")
    stop_discuss_loop_file_list = [agent_executor.implement_plan_ready_status_file_path,
                                   agent_executor.conflicting_idea_status_file_path]

    # 重新執行時刪除暫停檔
    for path in stop_discuss_loop_file_list:
        if os.path.exists(path):
            os.remove(path)

    agent_executor.implement_code()

    # 執行ML訓練並產出報告
    # implement_code(agent_executor)
    # session_file_name = agent_executor.get_session_file_name(LLMTarget.GEMINI)
    # agent_executor.run_agent(LLMTarget.GEMINI,
    #                          f"請幫我修改{agent_executor.trainer_file_path}"
    #                          f"，將匯出的模型放到{agent_executor.trained_model_path}"
    #                          f"，並執行{agent_executor.trainer_file_path}產出模型訓練結果"
    #                          f"，將模型訓練結果及後續修改計畫匯出到{agent_executor.session_dir}{session_file_name}")
    # print("=========FINISH training and export result=========")
    # print(agent_executor.stack_trace)

    # 討論結果並提出下一步修改方向
    # generated_implement_plan()
    # is_need_to_stop_discuss_loop = False
    # for i in range(3):
    #     for llm_taget in [LLMTarget.GEMINI, LLMTarget.CODEX]:
    #         for path in stop_discuss_loop_file_list:
    #             if os.path.exists(path):
    #                 is_need_to_stop_discuss_loop = True
    #         if is_need_to_stop_discuss_loop:
    #             break
    #         session_file_name = agent_executor.get_session_file_name(llm_taget)
    #         agent_executor.run_agent(llm_taget,
    #                                  f"{agent_executor.session_dir}{agent_executor.last_session_name}是我的模型訓練結果及後續修改計畫"
    #                                  f"，請以一個ML專家的角度，幫我review {agent_executor.session_dir}{agent_executor.last_session_name}的訓練結果及修改計畫"
    #                                  f"，將訓練結果及修改計畫加上你的補充建議一併匯出到{agent_executor.session_dir}{session_file_name}"
    #                                  f"，沒有補充意見的話，且完全同意目前的修改計畫，請產出一個空白檔案{agent_executor.code_change_final_plan_ready_file_path}"
    #                                  f"，如果有遇到與{agent_executor.session_dir}{agent_executor.last_session_name}衝突的想法"
    #                                  f"(比如它覺得應該將停利條件設為10%，你覺得應該設為5%)這種沒有一定對錯的衝突點，請用表格的方式將2者各自的優劣一併寫到{agent_executor.session_dir}{session_file_name}"
    #                                  f"，並產出一個空白檔案{agent_executor.conflicting_idea_file_path}，讓我知道")
    #
    # print("=========FINISH discussion=========")
    # print(agent_executor.stack_trace)
