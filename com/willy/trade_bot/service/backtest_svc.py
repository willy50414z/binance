from com.willy.trade_bot.dto.backtest_config import BackTestConfig


class BackTestService:
    def __init__(self, back_test_config: BackTestConfig):
        self.back_test_config = back_test_config

    def download_test_data(self):
        module_name = f"com.willy.trade_bot.data_extractor.{self.back_test_config.exchange.name.lower()}_extractor"
        try:
            import importlib
            extractor_module = importlib.import_module(module_name)
            if hasattr(extractor_module, 'extract'):
                extractor_module.extract(self.back_test_config)
            else:
                raise AttributeError(f"Module {module_name} does not have an extract function.")
        except ImportError as e:
            raise ImportError(
                f"Could not import extractor module for exchange {self.back_test_config.exchange.name}: {e}")
