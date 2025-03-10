import websocket
import json
import threading
import logging
from collections import deque
import time

nhat_ky = logging.getLogger(__name__)

class QuanLyWebSocket:
    def __init__(self, bot_telegram):
        self.ws_thuc_thi = {}
        self.bo_dem_giao_dich = {}
        self.gia_cuoi = {}
        self.bo_dem_ws = {}
        self.bot = bot_telegram

    def bat_dau_websocket(self, chat_id):
        def khi_nhan_tin(ws, tin_nhan):
            du_lieu = json.loads(tin_nhan)
            if "c" in du_lieu and "deals" in du_lieu["d"]:
                ky_hieu = du_lieu["c"].split('@')[-1]
                giao_dich = du_lieu["d"]["deals"]
                thoi_gian_hien_tai = time.time()
                if chat_id not in self.bo_dem_giao_dich:
                    self.bo_dem_giao_dich[chat_id] = {}
                if ky_hieu not in self.bo_dem_giao_dich[chat_id]:
                    self.bo_dem_giao_dich[chat_id][ky_hieu] = deque(maxlen=200)
                for gd in giao_dich:
                    gia = float(gd["p"])
                    self.bo_dem_giao_dich[chat_id][ky_hieu].append({"gia": gia, "khoi_luong": float(gd["v"]), "ben": gd["S"], "moc_thoi_gian": gd["t"] / 1000})
                    if ky_hieu in self.gia_cuoi.get(chat_id, {}):
                        thay_doi = abs(gia - self.gia_cuoi[chat_id][ky_hieu]) / self.gia_cuoi[chat_id][ky_hieu] * 100
                        if thay_doi > 5:
                            self.bot.gui_tin_nhan(chat_id, f"Canh bao: {ky_hieu} bien dong {thay_doi:.2f}%!")
                    self.gia_cuoi.setdefault(chat_id, {})[ky_hieu] = gia
                self.bo_dem_ws[chat_id] = thoi_gian_hien_tai

        def khi_loi(ws, loi):
            nhat_ky.error(f"Loi WebSocket cho {chat_id}: {loi}")
            self.bo_dem_ws[chat_id] = 0

        def khi_dong(ws):
            nhat_ky.warning(f"WebSocket dong cho {chat_id}. Ket noi lai...")
            self.bo_dem_ws[chat_id] = 0
            threading.Thread(target=self.bat_dau_websocket, args=(chat_id,), daemon=True).start()

        def khi_mo(ws):
            nguoi_dung = self.bot.csdl.tai_nguoi_dung(chat_id)
            dang_ky = [f"spot@public.deals.v3.api@{s.replace('/', '')}" for s in nguoi_dung['ky_hieu']]
            ws.send(json.dumps({"method": "SUBSCRIPTION", "params": dang_ky}))

        self.ws_thuc_thi[chat_id] = websocket.WebSocketApp(
            "wss://wbs.mexc.com/ws",
            on_message=khi_nhan_tin,
            on_error=khi_loi,
            on_close=khi_dong,
            on_open=khi_mo
        )
        self.bo_dem_ws[chat_id] = 0
        threading.Thread(target=self.ws_thuc_thi[chat_id].run_forever, args=(30, 10), daemon=True).start()

    def cap_nhat_dang_ky(self, chat_id):
        nguoi_dung = self.bot.csdl.tai_nguoi_dung(chat_id)
        if chat_id in self.ws_thuc_thi and self.ws_thuc_thi[chat_id].sock:
            dang_ky = [f"spot@public.deals.v3.api@{s.replace('/', '')}" for s in nguoi_dung['ky_hieu']]
            self.ws_thuc_thi[chat_id].send(json.dumps({"method": "SUBSCRIPTION", "params": dang_ky}))

    def dong(self, chat_id):
        if chat_id in self.ws_thuc_thi:
            self.ws_thuc_thi[chat_id].close()
            del self.ws_thuc_thi[chat_id]
