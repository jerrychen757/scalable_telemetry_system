import asyncio
import time
import datetime
import sys
import signal 

try:
    from config_loader import TelemetryConfig
    from data_source import SimulatedDataSource # 可替換
    from frame_decoder import TelemetryFrameDecoder
    from data_handlers import ConsoleLogHandler, FileLogHandler, WebSocketDataHandler # 引入修改後的 WebSocketDataHandler
except ImportError as e:
    print(f"錯誤：無法導入必要的模組 - {e}")
    sys.exit(1)

# 全局事件，用於通知所有任務關閉
shutdown_event = asyncio.Event()

def handle_signal(sig, frame):
    """處理作業系統信號 (如 Ctrl+C)"""
    print(f"\n收到信號 {sig}。正在準備優雅關閉...")
    shutdown_event.set()

async def data_processing_simulation_loop(config, data_source, decoder, handlers, max_frames, loop):
    """
    模擬數據的產生、解碼和分發給 Handlers 的異步迴圈。
    """
    frame_count = 0
    error_count = 0
    print("[DataLoop] 數據處理模擬迴圈已啟動。")

    while frame_count < max_frames and not shutdown_event.is_set():
        # 1. 獲取數據 (SimulatedDataSource.get_next_frame 是同步的)
        #    在真實異步應用中，數據源獲取也可能是 awaitable 的
        raw_frame = await loop.run_in_executor(None, data_source.get_next_frame)
        
        if raw_frame is None:
            error_count += 1
            if error_count > 5:
                print("[DataLoop] 連續多次獲取數據失敗，模擬數據流可能已結束。")
                break
            await asyncio.sleep(0.5) # 獲取失敗時等待
            continue
        
        # 2. 解碼數據 (TelemetryFrameDecoder.decode 也是同步的)
        decoded_data = await loop.run_in_executor(None, decoder.decode, raw_frame)

        if decoded_data:
            frame_count += 1
            error_count = 0
            processing_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            data_to_handle = {
                "processing_timestamp_utc": processing_timestamp,
                "source_timestamp_s": decoded_data.get("timestamp_s", "N/A"),
                "rocket_id": decoded_data.get("rocket_id", "N/A"),
                "raw_frame_hex": raw_frame.hex().upper(), # 可以選擇是否包含原始幀
                "decoded_payload": decoded_data
            }

            # 3. 分發給 Handlers
            for handler in handlers:
                try:
                    if isinstance(handler, WebSocketDataHandler):
                        # WebSocketDataHandler 的 handle_data 內部使用 asyncio.Queue.put_nowait
                        # 這是從異步協程調用，是安全的
                        handler.handle_data(data_to_handle)
                    elif asyncio.iscoroutinefunction(getattr(handler, 'handle_data_async', None)):
                        # 如果 Handler 有 handle_data_async 方法
                        asyncio.create_task(handler.handle_data_async(data_to_handle))
                    else:
                        # 對於同步的 Handler，在執行器中運行以避免阻塞事件循環
                        await loop.run_in_executor(None, handler.handle_data, data_to_handle)
                except Exception as e:
                    print(f"[DataLoop] Handler '{type(handler).__name__}' 處理數據時發生錯誤: {e}")
        else:
            print("[DataLoop] 數據幀解碼失敗或無效。")
        
        await asyncio.sleep(0.2) # 模擬數據幀之間的處理間隔

    print(f"[DataLoop] 已處理 {frame_count} 個數據幀。數據處理迴圈結束。")
    shutdown_event.set() # 通知其他任務也準備關閉

async def main_async():
    """
    主異步函數，初始化並運行所有組件。
    """
    # 設定信號處理器，以便優雅關閉 (Ctrl+C)
    loop = asyncio.get_event_loop()
    for sig_name in ('SIGINT', 'SIGTERM'):
        if hasattr(signal, sig_name): # Windows 可能沒有 SIGTERM
             loop.add_signal_handler(getattr(signal, sig_name), handle_signal, getattr(signal, sig_name), None)


    print("可擴充遙測系統 (含 WebSocket) 模擬啟動...")
    print("===================================")

    config = None
    try:
        config = TelemetryConfig(config_path="telemetry_parameters.json")
        print("設定檔載入成功。")
    except Exception as e:
        print(f"載入設定檔失敗: {e}")
        return # 無法繼續

    data_source = SimulatedDataSource(config)
    decoder = TelemetryFrameDecoder(config)

    # 初始化 Handlers
    console_handler = ConsoleLogHandler()
    file_handler = FileLogHandler(filepath="flight_data_async_log.jsonl")
    websocket_handler = WebSocketDataHandler(host="localhost", port=8765)

    all_handlers = [console_handler, file_handler, websocket_handler]
    
    # 同步 setup (如果 handler 有)
    for handler in all_handlers:
        try:
            if hasattr(handler, 'setup') and callable(handler.setup):
                 # 如果 setup 是同步的，可以直接調用
                 if not asyncio.iscoroutinefunction(handler.setup):
                    handler.setup()
                 # 如果 setup 是異步的，理論上應該 await handler.setup()
                 # 但這裡為了保持 handler.setup() 的簡單性，假設它是同步的
        except Exception as e:
            print(f"設定 Handler '{type(handler).__name__}' 時發生錯誤: {e}")


    server_tasks = []
    try:
        # 啟動 WebSocket 伺服器 (這是異步的)
        await websocket_handler.start_server_async()
        
        # 啟動數據處理迴圈
        max_frames = 10000 # 運行更多幀，或直到被中斷
        data_loop_task = asyncio.create_task(
            data_processing_simulation_loop(config, data_source, decoder, all_handlers, max_frames, loop)
        )
        server_tasks.append(data_loop_task)
        if hasattr(websocket_handler, '_server') and websocket_handler._server is not None:
             # websockets.serve 本身返回一個 Server 物件，其 serve_forever() 或類似的被內部管理
             # 我們主要需要管理我們自己創建的 task，比如 _broadcast_task
             if hasattr(websocket_handler, '_broadcast_task') and websocket_handler._broadcast_task:
                server_tasks.append(websocket_handler._broadcast_task)


        print("\n系統運行中。按下 Ctrl+C 關閉。前端可連接至 ws://localhost:8765")
        
        # 等待關閉信號
        await shutdown_event.wait()
        print("\n收到關閉信號，開始終止任務...")

    except OSError as e: # 例如 WebSocket 埠號被占用
        print(f"系統啟動時發生 OS 錯誤 (可能是埠號衝突): {e}")
    except asyncio.CancelledError:
        print("主任務被取消。")
    except Exception as e:
        print(f"主異步函數發生未預期錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n正在執行異步清理程序...")

        # 取消仍在運行的任務
        for task in server_tasks:
            if task and not task.done():
                task.cancel()
        
        # 等待所有任務被取消
        if server_tasks:
            await asyncio.gather(*server_tasks, return_exceptions=True)
            print("所有模擬和廣播任務已嘗試關閉。")

        # 清理 Handlers (特別是 WebSocket)
        for handler in all_handlers:
            try:
                if hasattr(handler, 'cleanup_async') and asyncio.iscoroutinefunction(handler.cleanup_async):
                    await handler.cleanup_async()
                elif hasattr(handler, 'cleanup') and callable(handler.cleanup):
                    # 對於同步 cleanup，如果它可能阻塞，也應在 executor 中運行
                    await loop.run_in_executor(None, handler.cleanup)
                print(f"  - Handler '{type(handler).__name__}' 清理完成。")
            except Exception as e:
                print(f"警告: 清理 Handler '{type(handler).__name__}' 時發生錯誤: {e}")
        
        print("===================================")
        print("可擴充遙測系統 (含 WebSocket) 已關閉。")

if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n偵測到鍵盤中斷 (在 asyncio.run 之外)。程式終止。")
    except Exception as e: # 捕獲 asyncio.run() 本身可能拋出的其他錯誤
        print(f"執行 asyncio.run 時發生頂層錯誤: {e}")
