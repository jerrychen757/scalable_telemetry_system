import time
import datetime
from config_loader import TelemetryConfig
from data_source import SimulatedDataSource # 可以替換成其他數據源
from frame_decoder import TelemetryFrameDecoder
from data_handlers import ConsoleLogHandler, FileLogHandler # 可以加入更多 Handler

def main():
    print("可擴充遙測系統模擬啟動...")

    # 載入設定
    try:
        config = TelemetryConfig(config_path="telemetry_parameters.json")
        print("設定檔載入成功。")
    except FileNotFoundError:
        print("錯誤: 找不到 telemetry_parameters.json 設定檔。請確保檔案存在於正確路徑。")
        return
    except Exception as e:
        print(f"載入設定檔時發生錯誤: {e}")
        return

    # 初始化組件
    data_source = SimulatedDataSource(config)
    decoder = TelemetryFrameDecoder(config)
    
    # 註冊數據處理器
    handlers = [
        ConsoleLogHandler(),
        FileLogHandler(filepath="flight_data_log.jsonl")
        # 在此處添加更多 handler 實例
    ]

    # 設定所有 handlers
    for handler in handlers:
        try:
            handler.setup()
        except Exception as e:
            print(f"設定 Handler {type(handler).__name__} 時發生錯誤: {e}")
            # 根據需求決定是否在此處終止程式或僅記錄錯誤


    print("\n開始接收和處理數據...\n")
    try:
        for i in range(10): # 模擬處理10個數據幀
            raw_frame = data_source.get_next_frame()

            if raw_frame is None:
                print("從數據源獲取數據失敗或數據流結束。")
                time.sleep(0.1) # 避免在失敗時快速空轉
                continue
            
            # print(f"收到原始幀 (main): {raw_frame.hex().upper()}") # 調試用
            
            decoded_data = decoder.decode(raw_frame)

            if decoded_data:
                # 為數據加上處理時間戳
                processing_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                data_to_handle = {
                    "processing_timestamp": processing_timestamp,
                    "source_timestamp_s": decoded_data.get("timestamp_s"), # 從數據中提取原始時間戳
                    "data": decoded_data
                }
                for handler in handlers:
                    try:
                        handler.handle_data(data_to_handle)
                    except Exception as e:
                        print(f"Handler {type(handler).__name__} 處理數據時發生錯誤: {e}")
            else:
                print("數據幀解碼失敗。")
            
            time.sleep(0.5) # 模擬數據幀之間的時間間隔
    
    except KeyboardInterrupt:
        print("\n偵測到使用者中斷 (Ctrl+C)。正在關閉系統...")
    finally:
        # 清理所有 handlers
        print("\n執行清理程序...")
        for handler in handlers:
            try:
                handler.cleanup()
            except Exception as e:
                print(f"清理 Handler {type(handler).__name__} 時發生錯誤: {e}")
        print("系統關閉。")


if __name__ == "__main__":
    main()

