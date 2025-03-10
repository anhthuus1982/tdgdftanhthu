from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
import logging
import time
from concurrent.futures import ThreadPoolExecutor
import threading
import multiprocessing
import schedule
import psutil
from flask import Flask, render_template, request
from indicators import lay_tin_hieu, kiem_tra_volume_breakout
import os

nhat_ky = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')

class BotTelegram:
    def __init__(self, csdl, san, quan_ly_ws, mo_hinh):
        self.csdl = csdl
        self.san = san
        self.quan_ly_ws = quan_ly_ws
        self.mo_hinh = mo_hinh
        self.cap_nhat = Updater(os.environ.get("TELEGRAM_TOKEN"), use_context=True)
        self.thuc_thi = ThreadPoolExecutor(max_workers=max(2, multiprocessing.cpu_count() - 1))
        self.su_kien_dung = threading.Event()
        self.chat_id_hien_tai = None
        self.thiet_lap_lenh()

    def gui_tin_nhan(self, chat_id, tin_nhan, reply_markup=None):
        try:
            self.cap_nhat.bot.send_message(chat_id=chat_id, text=tin_nhan, reply_markup=reply_markup)
            nhat_ky.info(f"Gui tin nhan thanh cong den chat_id {chat_id}")
        except Exception as e:
            nhat_ky.error(f"Loi gui tin nhan: {str(e)}")

    def thiet_lap_lenh(self):
        dp = self.cap_nhat.dispatcher
        dp.add_handler(CommandHandler('start', self.bat_dau))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self.xu_ly_tin_nhan))
        dp.add_handler(CallbackQueryHandler(self.xu_ly_nut))

    def bat_dau(self, cap_nhat, ngu_canh):
        chat_id = str(cap_nhat.message.chat_id)
        nhat_ky.info(f"Nhan lenh /start tu chat_id: {chat_id}")
        if not self.chat_id_hien_tai:
            self.chat_id_hien_tai = chat_id
            nhat_ky.info(f"Da luu chat_id dau tien: {chat_id}")
        ngu_canh.user_data['trang_thai'] = None
        self.gui_tin_nhan(chat_id, "Chao mung den voi bot giao dich tu dong tren Bybit testnet!", self.hien_menu(chat_id))

    def hien_menu(self, chat_id):
        menu = [
            [KeyboardButton("Bat dau giao dich"), KeyboardButton("Trang thai")],
            [KeyboardButton("Ket thuc giao dich")],
            [KeyboardButton("Them ky hieu"), KeyboardButton("Xoa ky hieu")],
            [KeyboardButton("Cau hinh vi"), KeyboardButton("Mo phong")]
        ]
        return ReplyKeyboardMarkup(menu, resize_keyboard=True, one_time_keyboard=False)

    def xu_ly_tin_nhan(self, cap_nhat, ngu_canh):
        chat_id = str(cap_nhat.message.chat_id)
        if not self.chat_id_hien_tai:
            self.chat_id_hien_tai = chat_id
            nhat_ky.info(f"Da luu chat_id tu dong: {chat_id}")
        noi_dung = cap_nhat.message.text
        current_state = ngu_canh.user_data.get('trang_thai')

        if current_state == 'cho_ky_hieu':
            ky_hieu = noi_dung.upper()
            if ky_hieu not in ['BTC', 'ETH', 'LINK', 'XRP'] or len(self.csdl.tai_nguoi_dung(chat_id)['ky_hieu']) >= 10:
                self.gui_tin_nhan(chat_id, "Ky hieu khong hop le hoac vuot gioi han 10!", self.hien_menu(chat_id))
                return
            nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
            if ky_hieu not in nguoi_dung['ky_hieu']:
                nguoi_dung['ky_hieu'].append(ky_hieu)
                self.csdl.luu_nguoi_dung(chat_id, nguoi_dung)
                self.gui_tin_nhan(chat_id, f"Da them {ky_hieu}!", self.hien_menu(chat_id))
            ngu_canh.user_data['trang_thai'] = None
        elif current_state == 'cho_xoa_ky_hieu':
            ky_hieu = noi_dung.upper()
            nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
            if ky_hieu in nguoi_dung['ky_hieu']:
                nguoi_dung['ky_hieu'].remove(ky_hieu)
                self.csdl.luu_nguoi_dung(chat_id, nguoi_dung)
                self.gui_tin_nhan(chat_id, f"Da xoa {ky_hieu}!", self.hien_menu(chat_id))
            ngu_canh.user_data['trang_thai'] = None
        elif current_state == 'cho_phan_tram':
            try:
                phan_tram = float(noi_dung)
                if 0 <= phan_tram <= 100:
                    nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
                    nguoi_dung['phan_tram'] = phan_tram
                    self.csdl.luu_nguoi_dung(chat_id, nguoi_dung)
                    self.gui_tin_nhan(chat_id, f"Da dat % so du: {phan_tram}%!", self.hien_menu(chat_id))
                    ngu_canh.user_data['trang_thai'] = None
            except ValueError:
                self.gui_tin_nhan(chat_id, "Nhap so hop le!", self.hien_menu(chat_id))
        elif current_state == 'cho_dia_chi_vi':
            dia_chi = noi_dung.strip()
            if len(dia_chi) < 20:
                self.gui_tin_nhan(chat_id, "Dia chi vi khong hop le!", self.hien_menu(chat_id))
                return
            ban_phim = [
                [InlineKeyboardButton("TRC20", callback_data="network_TRC20"), InlineKeyboardButton("ERC20", callback_data="network_ERC20")]
            ]
            self.gui_tin_nhan(chat_id, f"Da nhan vi: {dia_chi}. Chon mang:", InlineKeyboardMarkup(ban_phim))
            ngu_canh.user_data['dia_chi_vi_tam'] = dia_chi
            ngu_canh.user_data['trang_thai'] = 'cho_mang_rut_tien'
        elif noi_dung == "Bat dau giao dich":
            self.bat_dau_giao_dich(chat_id, cap_nhat)
        elif noi_dung == "Trang thai":
            self.trang_thai(chat_id, cap_nhat)
        elif noi_dung == "Ket thuc giao dich":
            self.ket_thuc_giao_dich(chat_id, cap_nhat)
        elif noi_dung == "Them ky hieu":
            self.gui_tin_nhan(chat_id, "Nhap ky hieu (BTC, ETH, LINK, XRP):", self.hien_menu(chat_id))
            ngu_canh.user_data['trang_thai'] = 'cho_ky_hieu'
        elif noi_dung == "Xoa ky hieu":
            self.gui_tin_nhan(chat_id, "Nhap ky hieu can xoa:", self.hien_menu(chat_id))
            ngu_canh.user_data['trang_thai'] = 'cho_xoa_ky_hieu'
        elif noi_dung == "Cau hinh vi":
            self.gui_tin_nhan(chat_id, "Nhap dia chi vi rut tien:", self.hien_menu(chat_id))
            ngu_canh.user_data['trang_thai'] = 'cho_dia_chi_vi'
        elif noi_dung == "Mo phong":
            self.simulation_mode(chat_id, "BTC", "1h")

    def bat_dau_giao_dich(self, chat_id, cap_nhat):
        ban_phim = [
            [InlineKeyboardButton("Them Ky Hieu", callback_data="add_symbol")],
            [InlineKeyboardButton("Cau Hinh", callback_data="config")],
            [InlineKeyboardButton("Bat Dau", callback_data="start")]
        ]
        cap_nhat.message.reply_text("Chon hanh dong:", reply_markup=InlineKeyboardMarkup(ban_phim))

    def xu_ly_nut(self, cap_nhat, ngu_canh):
        truy_van = cap_nhat.callback_query
        chat_id = str(truy_van.message.chat_id)
        du_lieu = truy_van.data

        if du_lieu == 'add_symbol':
            truy_van.edit_message_text("Nhap ky hieu (BTC, ETH, LINK, XRP):")
            ngu_canh.user_data['trang_thai'] = 'cho_ky_hieu'
        elif du_lieu == 'config':
            ban_phim = [
                [InlineKeyboardButton("1h", callback_data="timeframe_1h"), InlineKeyboardButton("4h", callback_data="timeframe_4h")]
            ]
            truy_van.edit_message_text("Chon khung thoi gian:", reply_markup=InlineKeyboardMarkup(ban_phim))
        elif du_lieu.startswith('timeframe_'):
            khung_thoi_gian = du_lieu.split('_')[1]
            nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
            nguoi_dung['khung_thoi_gian'] = khung_thoi_gian
            self.csdl.luu_nguoi_dung(chat_id, nguoi_dung)
            truy_van.edit_message_text(f"Da chon {khung_thoi_gian}. Nhap % so du (0-100):")
            ngu_canh.user_data['trang_thai'] = 'cho_phan_tram'
        elif du_lieu.startswith('network_'):
            mang_rut_tien = du_lieu.split('_')[1]
            dia_chi_vi = ngu_canh.user_data.get('dia_chi_vi_tam')
            nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
            nguoi_dung['dia_chi_vi'] = dia_chi_vi
            nguoi_dung['mang_rut_tien'] = mang_rut_tien
            self.csdl.luu_nguoi_dung(chat_id, nguoi_dung)
            truy_van.edit_message_text(f"Da luu vi: {dia_chi_vi} tren {mang_rut_tien}!")
            ngu_canh.user_data['trang_thai'] = None
        elif du_lieu == 'start':
            nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
            if not nguoi_dung['ky_hieu'] or not nguoi_dung.get('khung_thoi_gian') or nguoi_dung['phan_tram'] <= 0:
                truy_van.edit_message_text("Chua cau hinh day du!")
            else:
                nguoi_dung['hoat_dong'] = True
                self.csdl.luu_nguoi_dung(chat_id, nguoi_dung)
                self.thuc_thi.submit(self.quan_ly_giao_dich, chat_id)
                self.gui_tin_nhan(chat_id, "Da bat dau giao dich!", self.hien_menu(chat_id))
                truy_van.edit_message_text("Giao dich da bat dau!")

    def quan_ly_giao_dich(self, chat_id):
        nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
        self.quan_ly_ws.bat_dau_websocket(chat_id)
        for ky_hieu in nguoi_dung['ky_hieu']:
            self.thuc_thi.submit(self.chay_giao_dich, chat_id, ky_hieu, nguoi_dung['khung_thoi_gian'])

    def chay_giao_dich(self, chat_id, ky_hieu, khung_thoi_gian):
        nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
        if not os.path.exists(f"lstm_models/{ky_hieu}_{khung_thoi_gian}.h5"):
            self.mo_hinh.huan_luyen_lstm(ky_hieu, khung_thoi_gian)
        if not os.path.exists(f"rl_models/{ky_hieu}.zip"):
            self.mo_hinh.huan_luyen_rl(ky_hieu, self.san)

        while nguoi_dung['hoat_dong'] and not self.su_kien_dung.is_set():
            try:
                du_lieu = self.csdl.tai_lich_su_gia(ky_hieu, khung_thoi_gian)
                if not du_lieu:
                    du_lieu = self.san.lay_ohlcv(ky_hieu, khung_thoi_gian, limit=200)
                    self.csdl.luu_lich_su_gia(ky_hieu, du_lieu)

                tin_hieu, adx, rsi = lay_tin_hieu(du_lieu, nguoi_dung['trong_so'])
                xu_huong = self.mo_hinh.du_doan_xu_huong(ky_hieu, khung_thoi_gian, self.san)
                volume_breakout = kiem_tra_volume_breakout(du_lieu)

                so_du = self.san.lay_so_du()
                gia_hien_tai = self.san.lay_gia_hien_tai(ky_hieu)
                so_luong = (so_du * nguoi_dung['phan_tram'] / 100) / gia_hien_tai * nguoi_dung['don_bay']

                diem_mua = sum(nguoi_dung['trong_so'].get(k, 0) * v for k, v in tin_hieu.items() if v == 1) + (0.5 if xu_huong == 1 else 0) + (0.3 if volume_breakout == 1 else 0)
                diem_ban = sum(nguoi_dung['trong_so'].get(k, 0) * v for k, v in tin_hieu.items() if v == -1) + (0.5 if xu_huong == -1 else 0) + (0.3 if volume_breakout == -1 else 0)

                if diem_mua > diem_ban + 0.5:
                    self.san.tao_lenh_mua_thi_truong(ky_hieu, so_luong)
                    self.gui_tin_nhan(chat_id, f"Mua {ky_hieu} tai {gia_hien_tai} voi {so_luong}")
                elif diem_ban > diem_mua + 0.5:
                    self.san.tao_lenh_ban_thi_truong(ky_hieu, so_luong)
                    self.gui_tin_nhan(chat_id, f"Ban {ky_hieu} tai {gia_hien_tai} voi {so_luong}")

                self.kiem_tra_rui_ro(chat_id)
                time.sleep(600)
                nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
            except Exception as e:
                nhat_ky.error(f"Loi giao dich {ky_hieu}: {str(e)}")
                time.sleep(30)

    def ket_thuc_giao_dich(self, chat_id, cap_nhat):
        nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
        nguoi_dung['hoat_dong'] = False
        self.csdl.luu_nguoi_dung(chat_id, nguoi_dung)
        self.su_kien_dung.set()
        self.quan_ly_ws.dong_websocket(chat_id)
        cap_nhat.message.reply_text("Da ket thuc giao dich!", reply_markup=self.hien_menu(chat_id))

    def trang_thai(self, chat_id, cap_nhat):
        nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
        so_du = self.san.lay_so_du()
        ky_hieu_list = ", ".join(nguoi_dung['ky_hieu']) if nguoi_dung['ky_hieu'] else "Chua co"
        cap_nhat.message.reply_text(
            f"Trang thai:\nHoat dong: {nguoi_dung['hoat_dong']}\nSo du: {so_du} USDT\nKy hieu: {ky_hieu_list}\n% so du: {nguoi_dung['phan_tram']}%",
            reply_markup=self.hien_menu(chat_id)
        )

    def simulation_mode(self, chat_id, ky_hieu, khung_thoi_gian, so_du_ban_dau=1000):
        du_lieu = self.san.lay_ohlcv(ky_hieu, khung_thoi_gian, limit=1000)
        so_du = so_du_ban_dau
        vi_the = 0
        for i in range(60, len(du_lieu)):
            tin_hieu, _, _ = lay_tin_hieu(du_lieu[:i], {'rsi': 0.4, 'adx': 0.4, 'ma': 0.2})
            gia = du_lieu[i]['close']
            if tin_hieu['rsi'] == 1 and so_du > 0:
                vi_the = so_du / gia
                so_du = 0
            elif tin_hieu['rsi'] == -1 and vi_the > 0:
                so_du = vi_the * gia
                vi_the = 0
        loi_nhuan = so_du - so_du_ban_dau
        self.gui_tin_nhan(chat_id, f"Mo phong {ky_hieu}: Loi nhuan {loi_nhuan} USDT")

    def kiem_tra_rui_ro(self, chat_id):
        nguoi_dung = self.csdl.tai_nguoi_dung(chat_id)
        so_du_hien_tai = self.san.lay_so_du()
        so_du_ban_dau = nguoi_dung.get('so_du_ban_dau', so_du_hien_tai)
        thua_lo = (so_du_ban_dau - so_du_hien_tai) / so_du_ban_dau * 100
        if thua_lo > 20:
            nguoi_dung['hoat_dong'] = False
            self.csdl.luu_nguoi_dung(chat_id, nguoi_dung)
            self.gui_tin_nhan(chat_id, f"Bot dung do thua lo vuot 20% ({thua_lo:.2f}%)!")
        nguoi_dung['so_du_ban_dau'] = so_du_hien_tai
        self.csdl.luu_nguoi_dung(chat_id, nguoi_dung)

    def thiet_lap_lich_trinh(self):
        if self.chat_id_hien_tai:
            schedule.every().day.at("00:00").do(self.simulation_mode, chat_id=self.chat_id_hien_tai, ky_hieu="BTC", khung_thoi_gian="1h")
            while True:
                schedule.run_pending()
                time.sleep(60)
        else:
            nhat_ky.warning("Chua co chat_id de thiet lap lich trinh")

    @app.route('/')
    def dashboard(self):
        if self.chat_id_hien_tai:
            nguoi_dung = self.csdl.tai_nguoi_dung(self.chat_id_hien_tai)
            so_du = self.san.lay_so_du()
            return render_template('dashboard.html', nguoi_dung=nguoi_dung, so_du=so_du)
        return "Chua co chat_id dang ky!"

    @app.route('/stop', methods=['POST'])
    def stop_bot(self):
        self.su_kien_dung.set()
        return "Bot da dung!"

    def khoi_dong_dashboard(self):
        app.run(host='0.0.0.0', port=5000)
