import logging
import multiprocessing
from database import CSDL
from exchange import Exchange
from telegram_bot import BotTelegram
from websocket import QuanLyWebSocket
from model import MoHinhKetHop
import threading
import schedule
import time
import os

nhat_ky = logging.getLogger(__name__)

def thiet_lap_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )

def load_env(file_path=".env"):
    with open(file_path, "r") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key] = value

# Load file .env
load_env(".env")

def main():
    thiet_lap_logging()
    nhat_ky.info("Chuong trinh bat dau tren Bybit testnet...")

    csdl = CSDL()
    san = Exchange(testnet=True)
    quan_ly_ws = QuanLyWebSocket(san)
    mo_hinh = MoHinhKetHop(csdl)
    bot = BotTelegram(csdl, san, quan_ly_ws, mo_hinh)

    threading.Thread(target=bot.thiet_lap_lich_trinh, daemon=True).start()
    threading.Thread(target=bot.khoi_dong_dashboard, daemon=True).start()

    bot.cap_nhat.start_polling()
    nhat_ky.info("Bot khoi dong thanh cong, dang cho tin nhan tu Telegram...")
    bot.cap_nhat.idle()

if __name__ == "__main__":
    main()
