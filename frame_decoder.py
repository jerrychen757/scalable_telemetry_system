import struct

class TelemetryFrameDecoder:
    def __init__(self, config):
        self.config = config

    def decode(self, raw_frame_bytes):
        if len(raw_frame_bytes) < self.config.frame_total_length:
            print(f"錯誤: 接收到的數據幀太短 ({len(raw_frame_bytes)} bytes), 預期 {self.config.frame_total_length} bytes")
            return None

        decoded_data = {}
        
        # 檢查同步字 (假設第一個參數是同步字且被標記)
        sync_param_def = next((p for p in self.config.parameters if p.get("is_sync")), None)
        if sync_param_def:
            sync_val_packed = raw_frame_bytes[sync_param_def["offset"] : sync_param_def["offset"] + sync_param_def["length"]]
            sync_val_unpacked, = struct.unpack(self.config.byte_order + sync_param_def["struct_format"], sync_val_packed)
            if sync_val_unpacked != self.config.frame_sync_word:
                print(f"錯誤: 同步字不匹配! 收到: {hex(sync_val_unpacked)}, 預期: {hex(self.config.frame_sync_word)}")
                return None
        else:
            print("警告: 未在設定檔中找到同步字定義 (is_sync: true)")


        for param_def in self.config.parameters:
            name = param_def["name"]
            offset = param_def["offset"]
            length = param_def["length"]
            fmt = param_def["struct_format"]
            scale = param_def.get("scale_factor", 1.0) # 預設縮放因子為1
            unit = param_def.get("unit", "")

            # 從原始字節中提取參數的片段
            param_bytes = raw_frame_bytes[offset : offset + length]
            
            if len(param_bytes) < length:
                print(f"警告: 參數 '{name}' 的數據不足，跳過。")
                decoded_data[name] = "數據不足"
                continue

            try:
                # 解包
                raw_value, = struct.unpack(self.config.byte_order + fmt, param_bytes)
                
                # 應用縮放因子 (如果不是同步字或校驗和等特殊字段)
                if not param_def.get("is_sync") and not param_def.get("is_checksum"):
                    engineered_value = raw_value * scale
                else:
                    engineered_value = raw_value # 對於同步字或校驗和，通常不縮放

                decoded_data[name] = engineered_value
                if unit: # 如果有單位，也加入
                    decoded_data[name + "_unit"] = unit

            except struct.error as e:
                print(f"解包參數 '{name}' 時發生錯誤: {e}")
                decoded_data[name] = "解碼錯誤"
        
        # 校驗和驗證
       # checksum_param_def = next((p for p in self.config.parameters if p.get("is_checksum")), None)
        #if checksum_param_def:
         # ... 實現校驗和計算與比較 ...
         #  pass

        return decoded_data
