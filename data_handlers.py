import abc
import json
import datetime
import asyncio 
import websockets 

class AbstractDataHandler(abc.ABC):
    @abc.abstractmethod
    def setup(self):
        pass
    @abc.abstractmethod
    def handle_data(self, decoded_data_with_timestamp):
        pass
    @abc.abstractmethod
    def cleanup(self):
        pass

class ConsoleLogHandler(AbstractDataHandler):
    def setup(self):
        print("[ConsoleLogHandler] 初始化完成。")
    def handle_data(self, decoded_data_with_timestamp):
        timestamp = decoded_data_with_timestamp.get("processing_timestamp_utc", "N/A")
        data = decoded_data_with_timestamp.get("decoded_payload", {})
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
            self.file = open(self.filepath, 'a', encoding='utf-8')
            print(f"[FileLogHandler] 初始化完成，日誌將寫入至 {self.filepath}")
        except IOError as e:
            print(f"[FileLogHandler] 錯誤：無法開啟日誌檔案 {self.filepath}: {e}")
            self.file = None
    def handle_data(self, decoded_data_with_timestamp):
        if self.file:
            try:
                json.dump(decoded_data_with_timestamp, self.file, ensure_ascii=False)
                self.file.write('\n')
                self.file.flush()
            except Exception as e:
                print(f"[FileLogHandler] 寫入日誌時發生錯誤: {e}")
    def cleanup(self):
        if self.file:
            self.file.close()
            print(f"[FileLogHandler] 清理完成，日誌檔案 {self.filepath} 已關閉。")
# --- WebSocketDataHandler 實現 ---
class WebSocketDataHandler(AbstractDataHandler):
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.connected_clients = set()
        self._server = None # 用於保存 websockets.serve 的返回物件
        self._server_task = None # 用於保存 WebSocket 伺服器的 asyncio Task
        self._broadcast_queue = asyncio.Queue(maxsize=100) # 異步佇列，限制大小以防記憶體無限增長

    async def _register_client(self, websocket, path):
        """當新的 WebSocket 客戶端連接時被調用"""
        self.connected_clients.add(websocket)
        print(f"[WebSocket] 用戶端 {websocket.remote_address} 已連接。目前 {len(self.connected_clients)} 個連接。")
        try:
            # 保持連接開啟，直到客戶端斷開或發生錯誤
            await websocket.wait_closed()
        except websockets.exceptions.ConnectionClosedError:
            print(f"[WebSocket] 用戶端 {websocket.remote_address} 連線意外關閉 (Error)。")
        except websockets.exceptions.ConnectionClosedOK:
            print(f"[WebSocket] 用戶端 {websocket.remote_address} 連線正常關閉 (OK)。")
        except Exception as e:
            print(f"[WebSocket] 與客戶端 {websocket.remote_address} 通訊時發生未知錯誤: {e}")
        finally:
            print(f"[WebSocket] 用戶端 {websocket.remote_address} 已斷開。")
            self.connected_clients.remove(websocket)

    async def _broadcast_data_loop(self):
        """異步迴圈：從佇列中獲取數據並廣播給所有連接的客戶端"""
        print("[WebSocket] 廣播迴圈已啟動。等待數據...")
        while True:
            try:
                message_to_send = await self._broadcast_queue.get()
                if message_to_send is None: # 收到 None 作為停止信號
                    print("[WebSocket] 廣播迴圈收到停止信號。")
                    break

                if self.connected_clients:
                    websockets.broadcast(self.connected_clients, message_to_send) # 較新版本
                    # 為了兼容性和更細緻的錯誤處理，手動迭代：
                    tasks = [client.send(message_to_send) for client in list(self.connected_clients)]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            client_addr = list(self.connected_clients)[i].remote_address # 獲取地址可能複雜
                            print(f"[WebSocket] 發送數據給某個客戶端時發生錯誤: {result}")
                            # 此處可以考慮移除發送失敗的客戶端
            except asyncio.CancelledError:
                print("[WebSocket] 廣播迴圈被取消。")
                break
            except Exception as e:
                print(f"[WebSocket] 廣播迴圈發生嚴重錯誤: {e}")
                await asyncio.sleep(1) # 發生錯誤時稍作等待，避免快速連續失敗

    def setup(self):
        """
        此方法在同步的 main 函數中被調用，但伺服器啟動是異步的。
        實際的伺服器啟動將由主 async 函數調用 start_server_async 來完成。
        """
        print(f"[WebSocketDataHandler] 準備啟動 WebSocket 伺服器 (實際啟動將在異步主函數中)。")
        # 此處不直接啟動伺服器，因為 setup 是同步調用

    async def start_server_async(self):
        """由異步主函數調用，實際啟動 WebSocket 伺服器和廣播迴圈"""
        if self._server_task is not None and not self._server_task.done():
            print("[WebSocket] 伺服器似乎已在運行中。")
            return

        try:
            # 啟動 WebSocket 伺服器
            self._server = await websockets.serve(
                self._register_client,
                self.host,
                self.port
            )
            print(f"[WebSocket] 伺服器已成功啟動於 ws://{self.host}:{self.port}")

            # 啟動廣播迴圈作為一個獨立的異步任務
            self._broadcast_task = asyncio.create_task(self._broadcast_data_loop())
            print("[WebSocket] 數據廣播任務已啟動。")

        except OSError as e: # 例如埠號被占用
            print(f"[WebSocket] 錯誤：無法啟動 WebSocket 伺服器於 ws://{self.host}:{self.port} - {e}")
            raise # 將錯誤拋出，讓主調用者處理
        except Exception as e:
            print(f"[WebSocket] 啟動伺服器或廣播任務時發生未知錯誤: {e}")
            raise

    def handle_data(self, decoded_data_with_timestamp):
        """
        從主數據處理迴圈接收數據，並將其放入異步佇列。
        這個方法可能從同步的迴圈中被調用，所以放入佇列的操作需要注意。
        如果主迴圈是異步的，可以直接 await self._broadcast_queue.put()
        如果主迴圈是同步的，需要透過 loop.call_soon_threadsafe 或類似機制，
        但此處我們假設主迴圈也將是異步的，所以可以直接使用 put_nowait (如果從異步協程調用)
        或讓主迴圈 await put()。為了簡單，我們用 try_put。
        """
        message = json.dumps(decoded_data_with_timestamp)
        try:
            self._broadcast_queue.put_nowait(message)
        except asyncio.QueueFull:
            print(f"[WebSocket] 警告: 數據廣播佇列已滿 ({self._broadcast_queue.qsize()})，最新數據可能被丟棄。")
        except Exception as e:
            print(f"[WebSocket] 推送數據到佇列時發生錯誤: {e}")


    async def cleanup_async(self):
        """異步清理資源，關閉伺服器和任務"""
        print("[WebSocketDataHandler] 正在執行異步清理...")
        if self._broadcast_task is not None and not self._broadcast_task.done():
            print("[WebSocket] 正在停止廣播迴圈...")
            try:
                await self._broadcast_queue.put(None) # 發送停止信號
                await asyncio.wait_for(self._broadcast_task, timeout=5.0)
                print("[WebSocket] 廣播迴圈已停止。")
            except asyncio.TimeoutError:
                print("[WebSocket] 警告: 等待廣播迴圈停止超時，將強制取消。")
                self._broadcast_task.cancel()
                try:
                    await self._broadcast_task # 等待取消完成
                except asyncio.CancelledError:
                    print("[WebSocket] 廣播迴圈已被強制取消。")
            except Exception as e:
                print(f"[WebSocket] 關閉廣播迴圈時發生錯誤: {e}")

        if self._server is not None:
            print("[WebSocket] 正在關閉 WebSocket 伺服器...")
            self._server.close()
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=5.0)
                print("[WebSocket] WebSocket 伺服器已關閉。")
            except asyncio.TimeoutError:
                print("[WebSocket] 警告: 等待 WebSocket 伺服器關閉超時。")
            except Exception as e:
                print(f"[WebSocket] 關閉伺服器時發生錯誤: {e}")
        
        self._server = None
        self._server_task = None
        self._broadcast_task = None
        print("[WebSocketDataHandler] 異步清理完成。")

    def cleanup(self):
        """同步清理接口，主要用於被同步的主程序調用。
           理想情況下，異步資源應由異步方式清理。
        """
        print("[WebSocketDataHandler] 同步清理被調用。建議使用 cleanup_async 在事件循環中清理。")
        # 如果事件循環仍在運行，可以嘗試安排異步清理
        # loop = asyncio.get_event_loop()
        # if loop.is_running():
        #     asyncio.run_coroutine_threadsafe(self.cleanup_async(), loop)
        # else:
        #     print("[WebSocketDataHandler] 沒有運行的事件循環來執行異步清理。")

