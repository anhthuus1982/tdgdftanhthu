import logging
import time
import os
from pybit.unified_trading import HTTP

nhat_ky = logging.getLogger(__name__)

class Exchange:
    def __init__(self, api_key=None, api_secret=None, testnet=True):
        self.api_key = api_key or os.environ.get("BYBIT_API_KEY")
        self.api_secret = api_secret or os.environ.get("BYBIT_SECRET")
        self.testnet = testnet
        self.client = HTTP(testnet=self.testnet, api_key=self.api_key, api_secret=self.api_secret)
        self._dong_bo_thoi_gian()
        nhat_ky.info(f"San Bybit testnet khoi tao voi api_key: {self.api_key[:6]}...")

    def _dong_bo_thoi_gian(self):
        try:
            response = self.client.get_server_time()
            if response['retCode'] != 0:
                raise ValueError(f"Loi lay thoi gian server: {response['retMsg']}")
            server_time = int(response['result']['timeSecond'])
            local_time = int(time.time())
            delta = server_time - local_time
            if abs(delta) > 5:
                os.system("sudo ntpdate pool.ntp.org")
                nhat_ky.info("Dong bo thoi gian thanh cong")
        except Exception as e:
            nhat_ky.error(f"Loi dong bo thoi gian: {str(e)}")

    def lay_ohlcv(self, ky_hieu, khung_thoi_gian, limit=200):
        symbol = f"{ky_hieu}USDT"
        response = self.client.get_kline(category="linear", symbol=symbol, interval=khung_thoi_gian, limit=limit)
        if response['retCode'] != 0:
            raise ValueError(f"Loi lay OHLCV: {response['retMsg']}")
        data = response['result']['list']
        ohlcv = [{'timestamp': int(k[0]), 'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])} for k in data]
        ohlcv.reverse()
        return ohlcv

    def lay_so_du(self):
        response = self.client.request("GET", "/v5/asset/all-balance", params={"accountType": "UNIFIED"})
        if response['retCode'] != 0:
            raise ValueError(f"Loi lay so du: {response['retMsg']}")
        for coin_data in response['result']['list'][0]['coin']:
            if coin_data['coin'] in ["USDT", "USDC"] and float(coin_data['availableBalance']) > 0:
                return float(coin_data['availableBalance'])
        raise ValueError("Khong co so du kha dung")

    def lay_gia_hien_tai(self, ky_hieu):
        response = self.client.get_tickers(category="linear", symbol=f"{ky_hieu}USDT")
        if response['retCode'] != 0:
            raise ValueError(f"Loi lay gia: {response['retMsg']}")
        return float(response['result']['list'][0]['lastPrice'])

    def tao_lenh_mua_thi_truong(self, ky_hieu, so_luong):
        symbol = f"{ky_hieu}USDT"
        gia_hien_tai = self.lay_gia_hien_tai(ky_hieu)
        response = self.client.place_order(
            category="linear", symbol=symbol, side="Buy", orderType="Market", qty=so_luong,
            stopLoss=str(gia_hien_tai * 0.95), takeProfit=str(gia_hien_tai * 1.05), timeInForce="GTC"
        )
        if response['retCode'] != 0:
            raise ValueError(f"Loi tao lenh mua: {response['retMsg']}")
        return response['result']['orderId']

    def tao_lenh_ban_thi_truong(self, ky_hieu, so_luong):
        symbol = f"{ky_hieu}USDT"
        gia_hien_tai = self.lay_gia_hien_tai(ky_hieu)
        response = self.client.place_order(
            category="linear", symbol=symbol, side="Sell", orderType="Market", qty=so_luong,
            stopLoss=str(gia_hien_tai * 1.05), takeProfit=str(gia_hien_tai * 0.95), timeInForce="GTC"
        )
        if response['retCode'] != 0:
            raise ValueError(f"Loi tao lenh ban: {response['retMsg']}")
        return response['result']['orderId']
