import logging
from pybit.unified_trading import WebSocket as PybitWebSocket
import time

nhat_ky = logging.getLogger(__name__)

class QuanLyWebSocket:
    def __init__(self, api_key=None, api_secret=None, testnet=True):
        self.api_key = api_key or os.environ.get("BYBIT_API_KEY")
        self.api_secret = api_secret or os.environ.get("BYBIT_SECRET")
        self.testnet = testnet
        self.ws = None
        self.chat_ids = {}

    def bat_dau_websocket(self, chat_id):
        while True:
            try:
                if chat_id not in self.chat_ids or not self.chat_ids[chat_id].connected:
                    self.ws = PybitWebSocket(
                        testnet=self.testnet, api_key=self.api_key, api_secret=self.api_secret,
                        channel_type="spot", subscriptions=["tickers.LINKUSDT", "orderbook.50.BTCUSDT", "publicTrade.ETHUSDT"]
                    )
                    self.ws.start()
                    self.chat_ids[chat_id] = self.ws
                    nhat_ky.info(f"WebSocket khoi tao thanh cong cho chat_id {chat_id}")
                    self.ws.on_message(lambda msg: self.xu_ly_du_lieu_websocket(msg, chat_id))
                break
            except Exception as e:
                nhat_ky.error(f"Loi WebSocket, thu lai sau 5s: {str(e)}")
                time.sleep(5)

    def xu_ly_du_lieu_websocket(self, msg, chat_id):
        if "topic" in msg and "orderbook" in msg["topic"]:
            depth = msg["data"]
            spread = float(depth["asks"][0][0]) - float(depth["bids"][0][0])
            if spread > 0.01:
                nhat_ky.warning(f"Spread lon cho {msg['symbol']}: {spread}%")

    def dong_websocket(self, chat_id):
        if chat_id in self.chat_ids and self.chat_ids[chat_id].connected:
            self.chat_ids[chat_id].close()
            del self.chat_ids[chat_id]
            nhat_ky.info(f"Da dong WebSocket cho chat_id {chat_id}")
