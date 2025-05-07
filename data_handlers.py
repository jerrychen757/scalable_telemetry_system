import abc
import json
import datetime

class AbstractDataHandler(abc.ABC):
    @abc.abstractmethod
    def setup(self): # 可選的設定方法
        pass

    @abc.abstractmethod
    def handle_data(self, decoded_data_with_timestamp):
        """處理已解碼的數據"""
        pass

    @abc.abstractmethod
    def cleanup(self): # 可選的清理方法
        pass

class ConsoleLogHandler(AbstractDataHandler):
    def setup(self):
        print("[ConsoleLogHandler] 初始化完成。")

    def handle_data(self, decoded_data_with_timestamp):
        timestamp = decoded_data_with_timestamp["processing_timestamp"]
        data = decoded_data_with_timestamp["data"]
        print(f"--- [Console Log @ {timestamp}] ---")
        for key, value in data.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
        print("--- End of Frame ---")
    
    def cleanup(self):
        print("[ConsoleLogHandler] 清理完成。")


class FileLogHandler(AbstractDataHandler):
    def __init__(self, filepath="telemetry_log.jsonl"):
        self.filepath = filepath
        self.file = None

    def setup(self):
        try:
            # 使用 'a' 模式以附加到檔案，並確保每條記錄為一行 JSON (JSON Lines)
            self.file = open(self.filepath, 'a', encoding='utf-8')
            print(f"[FileLogHandler] 初始化完成，日誌將寫入至 {self.filepath}")
        except IOError as e:
            print(f"[FileLogHandler] 錯誤：無法開啟日誌檔案 {self.filepath}: {e}")
            self.file = None # 確保如果開啟失敗，file物件是None

    def handle_data(self, decoded_data_with_timestamp):
        if self.file:
            try:
                # 將Python字典轉換為JSON字串並寫入，加上換行符
                json.dump(decoded_data_with_timestamp, self.file, ensure_ascii=False)
                self.file.write('\n')
                self.file.flush() # 確保即時寫入
            except IOError as e:
                print(f"[FileLogHandler] 錯誤：寫入日誌時發生錯誤: {e}")
            except TypeError as e:
                 print(f"[FileLogHandler] 錯誤：序列化數據時發生錯誤 (可能是數據類型問題): {e}")
                 print(f"  問題數據: {decoded_data_with_timestamp}")


    def cleanup(self):
        if self.file:
            self.file.close()
            print(f"[FileLogHandler] 清理完成，日誌檔案 {self.filepath} 已關閉。")

# 可以添加更多 Handler，例如：
# class DatabaseHandler(AbstractDataHandler): ...
# class AlertHandler(AbstractDataHandler): ...
