import json

class TelemetryConfig:
    def __init__(self, config_path="telemetry_parameters.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        self.frame_sync_word = int(config["frame_sync_word"], 16) # 將16進制字串轉為整數
        self.byte_order = config["byte_order"]
        self.parameters = config["parameters"]
        self.frame_total_length = config["frame_total_length"]

        # 建立一個查找表，方便按名稱查找參數定義
        self.param_map = {p["name"]: p for p in self.parameters}

    def get_parameter_definition(self, name):
        return self.param_map.get(name)

    def get_all_parameter_definitions(self):
        return self.parameters
