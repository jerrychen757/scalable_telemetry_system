import time
import datetime
import sys 

try:
    from config_loader import TelemetryConfig
    from data_source import SimulatedDataSource # 您可以根據需要替換成其他數據源
    from frame_decoder import TelemetryFrameDecoder
    from data_handlers import ConsoleLogHandler, FileLogHandler # 您可以加入更多 Handler
    from data_handlers import WebSocketDataHandler # 並確保 data_handlers.py 中有其定義
    
except ImportError as e:
    print(f"錯誤：無法導入必要的模組 - {e}")
    print("請確保 config_loader.py, data_source.py, frame_decoder.py, data_handlers.py 檔案存在且位於PYTHONPATH中。")
    sys.exit(1)


def main():
    """
    主函數，負責初始化組件、載入設定並運行遙測數據處理循環。
    """
    print("可擴充遙測系統模擬啟動...")
    print("===================================")

    # 1. 載入設定
    try:
        # 您可以將設定檔路徑作為參數傳入，或使用環境變數等
        config = TelemetryConfig(config_path="telemetry_parameters.json")
        print(f"設定檔 '{config.config_path if hasattr(config, 'config_path') else 'telemetry_parameters.json'}' 載入成功。")
        print(f"  預期幀長度: {config.frame_total_length} bytes")
        print(f"  同步字: {hex(config.frame_sync_word)}")
    except FileNotFoundError:
        print(f"錯誤: 找不到 'telemetry_parameters.json' 設定檔。")
        print("請確保檔案存在於執行腳本的相同目錄下，或提供正確的路徑。")
        sys.exit(1)
    except KeyError as e:
        print(f"錯誤: 設定檔 'telemetry_parameters.json' 缺少必要的鍵: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"載入設定檔時發生未預期錯誤: {e}")
        sys.exit(1)

    # 2. 初始化組件
    #    - 數據源 (可替換為真實數據源，例如從序列埠、網路UDP、硬體卡等讀取)
    #    - 解碼器
    #    - 數據處理器列表
    try:
        data_source = SimulatedDataSource(config) # 使用模擬數據源
        decoder = TelemetryFrameDecoder(config)
    except Exception as e:
        print(f"初始化數據源或解碼器時發生錯誤: {e}")
        sys.exit(1)
    
    # 註冊數據處理器 (可以根據需求增減)
    handlers = [
        ConsoleLogHandler(),
        FileLogHandler(filepath="flight_data_log.jsonl") # 記錄到 JSON Lines 檔案
        # --- 若要啟用WebSocket Handler (注意：這需要主循環改為異步或在獨立線程運行WebSocket伺服器) ---
        WebSocketDataHandler(host="localhost", port=8765) 
        # ------------------------------------------------------------------------------------
    ]

    # 設定所有 handlers
    active_handlers = []
    print("\n正在設定數據處理器...")
    for handler in handlers:
        try:
            handler.setup() # 執行每個 handler 的 setup 方法
            active_handlers.append(handler) # 只有成功 setup 的才加入 active 列表
            print(f"  - {type(handler).__name__} 設定成功。")
        except Exception as e:
            print(f"警告: 設定 Handler '{type(handler).__name__}' 時發生錯誤: {e}")
            print(f"         '{type(handler).__name__}' 將不會被使用。")
    
    if not active_handlers:
        print("錯誤: 沒有任何數據處理器成功初始化。程式即將退出。")
        sys.exit(1)

    print("\n開始接收和處理遙測數據...")
    print("按下 Ctrl+C 可以中斷程式。")
    print("-----------------------------------")

    frame_count = 0
    error_count = 0
    max_frames_to_process = 20 # 模擬處理的幀數，可依需求調整

    try:
        while frame_count < max_frames_to_process:
            # a. 從數據源獲取原始數據幀
            raw_frame = data_source.get_next_frame()

            if raw_frame is None:
                print(f"注意: 從數據源 '{type(data_source).__name__}' 未獲取到數據幀 (可能數據流結束或模擬次數已到)。")
                # 在真實應用中，這裡可能需要等待或重試邏輯
                time.sleep(0.5) # 稍微等待
                error_count += 1
                if error_count > 5 : # 連續多次獲取失敗則退出
                    print("連續多次獲取數據失敗，模擬終止。")
                    break
                continue 
            
            print(f"[DEBUG] 收到原始幀 (main, {len(raw_frame)} bytes): {raw_frame.hex().upper()}") # 調試原始幀用

            # b. 解碼數據幀
            decoded_data = decoder.decode(raw_frame)

            if decoded_data:
                frame_count += 1
                error_count = 0 # 成功處理，重置錯誤計數
                # 為數據加上處理時間戳 (使用UTC時間並格式化為ISO 8601)
                processing_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                
                data_to_handle = {
                    "processing_timestamp_utc": processing_timestamp,
                    # 從解碼數據中提取原始時間戳 (如果存在)
                    "source_timestamp_s": decoded_data.get("timestamp_s", "N/A"), 
                    "rocket_id": decoded_data.get("rocket_id", "N/A"),
                    "raw_frame_hex": raw_frame.hex().upper(), # 加入原始幀的十六進制表示
                    "decoded_payload": decoded_data
                }
                
                # c. 將解碼後的數據傳遞給所有註冊的處理器
                for handler in active_handlers:
                    try:
                        handler.handle_data(data_to_handle)
                    except Exception as e:
                        print(f"警告: Handler '{type(handler).__name__}' 處理數據時發生錯誤: {e}")
                        # 可以選擇在這裡記錄更詳細的錯誤堆疊
            else:
                print("注意: 數據幀解碼失敗或無效。")
                error_count += 1
            
            time.sleep(0.2) # 模擬數據幀之間的時間間隔，可調整

        print(f"\n已處理 {frame_count} 個數據幀。模擬結束。")

    except KeyboardInterrupt:
        print("\n偵測到使用者中斷 (Ctrl+C)。正在準備關閉系統...")
    except Exception as e:
        print(f"\n主處理迴圈發生未預期錯誤: {e}")
        import traceback
        traceback.print_exc() # 打印詳細的錯誤堆疊
    finally:
        # d. 清理所有 handlers (例如關閉檔案、釋放資源等)
        print("\n正在執行清理程序...")
        for handler in active_handlers:
            try:
                handler.cleanup()
                print(f"  - {type(handler).__name__} 清理完成。")
            except Exception as e:
                print(f"警告: 清理 Handler '{type(handler).__name__}' 時發生錯誤: {e}")
        
        print("===================================")
        print("可擴充遙測系統模擬已關閉。")

if __name__ == "__main__":
    main()

