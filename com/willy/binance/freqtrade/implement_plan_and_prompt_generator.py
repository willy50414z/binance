import glob
import os
import sys

import pyperclip

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from com.willy.binance.config.config_util import config_util


class PlanPromptGenerator:
    VERSION = 3
    STRATEGY_CODE = "AMRS"
    ROOT_DIR = os.path.normpath(config_util("project.path").get("root_dir"))
    BASE_PATH = os.path.join(ROOT_DIR, "com", "willy", "binance", "freqtrade", "strategy")

    @staticmethod
    def get_clipboard():
        content = pyperclip.paste()
        if not content.strip():
            raise ValueError("剪貼簿為空")
        return content

    @classmethod
    def find_strategy_folders(cls):
        folders = [f for f in os.listdir(cls.BASE_PATH) if f.startswith(cls.STRATEGY_CODE)]
        if not folders:
            raise FileNotFoundError("找不到任何 AMRS 開頭資料夾")
        return folders

    @classmethod
    def find_latest_md(cls, folder):
        plan_dir = os.path.join(cls.BASE_PATH, folder, "implement_plan")
        if not os.path.exists(plan_dir):
            os.makedirs(plan_dir)
        pattern = f"AMRS{cls.VERSION}_*.md"
        files = glob.glob(os.path.join(plan_dir, pattern))
        max_x = 0
        for file in files:
            basename = os.path.basename(file)
            try:
                x = int(basename.split("_")[1].split(".")[0])
                if x > max_x:
                    max_x = x
            except Exception:
                continue
        return max_x, plan_dir

    @classmethod
    def write_new_md(cls, plan_dir, x, content):
        new_md = f"AMRS{cls.VERSION}_{x}.md"
        md_path = os.path.join(plan_dir, new_md)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)
        return md_path

    @classmethod
    def generate_prompt(cls, folder, x):
        prev_strategy = f"com/willy/binance/freqtrade/strategy/{folder}/AMRS{cls.VERSION}_{x - 1}Strategy.py"
        plan_md = f"com/willy/binance/freqtrade/strategy/{folder}/implement_plan/AMRS{cls.VERSION}_{x}.md"
        new_strategy = f"com/willy/binance/freqtrade/strategy/{folder}/AMRS{cls.VERSION}_{x}Strategy.py"
        executor = "com/willy/binance/freqtrade/freqtrade_executor.py"
        prompt = f"請參考{prev_strategy}，\n並依據{plan_md}\n修改成{new_strategy}，\n並執行{executor}進行回測，再執行analyze_backtest_result.py產出分析報告"
        return prompt

    @classmethod
    def main(cls):
        content = cls.get_clipboard()
        folders = cls.find_strategy_folders()
        for folder in folders:
            max_x, plan_dir = cls.find_latest_md(folder)
            next_x = max_x + 1 if max_x else 1
            md_path = cls.write_new_md(plan_dir, next_x, content)
            prompt = cls.generate_prompt(folder, next_x)
            pyperclip.copy(prompt)
            print(f"已產生並寫回剪貼簿：{prompt}")


if __name__ == "__main__":
    PlanPromptGenerator.main()
