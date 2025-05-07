import abc
import random
import time
import struct # 需要 struct 來打包模擬數據

class AbstractDataSource(abc.ABC):
    @abc.abstractmethod
    def get_next_frame(self):
        """獲取下一個原始數據幀 (bytes)"""
        pass

class SimulatedDataSource(AbstractDataSource):
    def __init__(self, config):
        self.config = config
        self.rng = random.Random()

    def get_next_frame(self):
        """產生一個模擬的二進制數據幀"""
        # 根據設定檔動態建立數據幀
        # 為了簡化，這裡我們仍然手動模擬一些值，但會根據設定檔的長度和格式打包
        # 真實的模擬器會更複雜地基於物理模型產生數據

        values_to_pack = []
        current_format_string = self.config.byte_order # 起始為字節序

        # 模擬值 (與之前範例類似，但更具彈性)
        sim_values = {
            "sync_word": self.config.frame_sync_word,
            "rocket_id": 1,
            "timestamp_s": int(time.time()) + self.rng.randint(0,5), # 稍微隨機化時間戳
            "altitude": int(self.rng.randint(0, 80000) / self.config.get_parameter_definition("altitude").get("scale_factor", 1.0)),
            "velocity": int(self.rng.randint(0, 3000) / self.config.get_parameter_definition("velocity").get("scale_factor", 1.0)),
            "engine_pressure": int(self.rng.uniform(0, 2000.0) / self.config.get_parameter_definition("engine_pressure").get("scale_factor", 1.0)),
            "status_byte": self.rng.randint(0, 7),
            "checksum": 0xEE # 虛擬校驗和
        }
        
        # 按照設定檔中參數的順序和格式進行打包
        # 注意: 為了簡化，我們假設設定檔中的參數順序就是打包順序
        # 真實情況可能需要更複雜的偏移量管理
        sorted_params_for_packing = sorted(self.config.get_all_parameter_definitions(), key=lambda p: p['offset'])

        for param_def in sorted_params_for_packing:
            current_format_string += param_def["struct_format"]
            values_to_pack.append(sim_values.get(param_def["name"], 0)) # 如果模擬值沒有，填0

        if len(values_to_pack) != len(sorted_params_for_packing):
            print("錯誤: 模擬值數量與參數定義不符")
            return None
        
        try:
            # print(f"Packing with format: {current_format_string}, values: {values_to_pack}")
            packed_frame = struct.pack(current_format_string, *values_to_pack)
            if len(packed_frame) != self.config.frame_total_length:
                # print(f"警告: 打包後的幀長度 ({len(packed_frame)}) 與預期 ({self.config.frame_total_length}) 不符")
                # 為了使模擬能繼續，如果長度不對，我們可能需要填充或截斷，但這表示設定或模擬邏輯有問題
                # 此處簡單返回 None 或拋出錯誤
                # For simplicity, let's assume this matches or pad/truncate if necessary
                # This part would need robust handling in a real system.
                 pass # 暫時忽略長度問題，以便範例運行
            return packed_frame
        except struct.error as e:
            print(f"打包模擬數據時發生錯誤: {e}")
            print(f"  Format: {current_format_string}")
            print(f"  Values: {values_to_pack}")
            return None
