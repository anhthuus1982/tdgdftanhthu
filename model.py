import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from stable_baselines3 import PPO
import gym
import logging
import os

nhat_ky = logging.getLogger(__name__)

class TradingEnv(gym.Env):
    def __init__(self, ky_hieu, san):
        super(TradingEnv, self).__init__()
        self.ky_hieu = ky_hieu
        self.san = san
        self.action_space = gym.spaces.Discrete(3)  # Mua, Ban, Giu
        self.observation_space = gym.spaces.Box(low=0, high=1, shape=(60,), dtype=np.float32)
        self.reset()

    def reset(self):
        self.du_lieu = self.san.lay_ohlcv(self.ky_hieu, "1h", limit=60)
        self.so_du = 1000
        self.vi_the = 0
        return np.array([d['close'] for d in self.du_lieu[-60:]]) / max(d['close'] for d in self.du_lieu)

    def step(self, action):
        gia_hien_tai = self.du_lieu[-1]['close']
        if action == 0 and self.so_du > 0:  # Mua
            self.vi_the = self.so_du / gia_hien_tai
            self.so_du = 0
        elif action == 1 and self.vi_the > 0:  # Ban
            self.so_du = self.vi_the * gia_hien_tai
            self.vi_the = 0
        reward = self.so_du + self.vi_the * gia_hien_tai - 1000
        self.du_lieu.append(self.san.lay_ohlcv(self.ky_hieu, "1h", limit=1)[0])
        done = len(self.du_lieu) > 100
        return np.array([d['close'] for d in self.du_lieu[-60:]]) / max(d['close'] for d in self.du_lieu), reward, done, {}

class MoHinhKetHop:
    def __init__(self, csdl):
        self.csdl = csdl
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.lstm = self.khoi_tao_lstm()
        self.rl = None

    def khoi_tao_lstm(self):
        model = Sequential([
            Input(shape=(60, 1)), LSTM(50, return_sequences=True), Dropout(0.2),
            LSTM(50, return_sequences=False), Dropout(0.2), Dense(25), Dense(1)
        ])
        model.compile(optimizer='adam', loss='mean_squared_error')
        return model

    def chuan_bi_du_lieu(self, ky_hieu, khung_thoi_gian):
        du_lieu = self.csdl.tai_lich_su_gia(ky_hieu, khung_thoi_gian)
        if len(du_lieu) < 60:
            raise ValueError(f"Du lieu khong du 60 ky cho {ky_hieu}")
        df = pd.DataFrame(du_lieu)
        gia_dong = df['close'].values
        gia_dong_scaled = self.scaler.fit_transform(gia_dong.reshape(-1, 1))
        X = [gia_dong_scaled[i-60:i, 0] for i in range(60, len(gia_dong_scaled))]
        return np.array(X).reshape(-1, 60, 1), gia_dong_scaled

    def huan_luyen_lstm(self, ky_hieu, khung_thoi_gian):
        X, gia_dong_scaled = self.chuan_bi_du_lieu(ky_hieu, khung_thoi_gian)
        y = gia_dong_scaled[60:, 0]
        X_train, y_train = X[:int(0.8 * len(X))], y[:int(0.8 * len(y))]
        X_test, y_test = X[int(0.8 * len(X)):], y[int(0.8 * len(y)):]
        self.lstm.fit(X_train, y_train, epochs=5, batch_size=32, validation_data=(X_test, y_test), verbose=0)
        self.lstm.save(f"lstm_models/{ky_hieu}_{khung_thoi_gian}.h5")

    def huan_luyen_rl(self, ky_hieu, san):
        env = TradingEnv(ky_hieu, san)
        model = PPO("MlpPolicy", env, verbose=0)
        model.learn(total_timesteps=10000)
        model.save(f"rl_models/{ky_hieu}.zip")
        self.rl = model

    def du_doan_xu_huong(self, ky_hieu, khung_thoi_gian, san):
        X, gia_dong_scaled = self.chuan_bi_du_lieu(ky_hieu, khung_thoi_gian)
        if os.path.exists(f"lstm_models/{ky_hieu}_{khung_thoi_gian}.h5"):
            self.lstm = load_model(f"lstm_models/{ky_hieu}_{khung_thoi_gian}.h5")
        lstm_pred = self.lstm.predict(X[-1:], verbose=0)
        lstm_pred = self.scaler.inverse_transform(lstm_pred)[0][0]
        gia_hien_tai = self.scaler.inverse_transform(gia_dong_scaled[-1:])[0][0]

        if os.path.exists(f"rl_models/{ky_hieu}.zip"):
            self.rl = PPO.load(f"rl_models/{ky_hieu}.zip")
            obs = X[-1].flatten()
            rl_action, _ = self.rl.predict(obs)
            rl_pred = 1 if rl_action == 0 else -1 if rl_action == 1 else 0
        else:
            rl_pred = 0

        return 1 if lstm_pred > gia_hien_tai + 0.01 and rl_pred == 1 else -1 if lstm_pred < gia_hien_tai - 0.01 and rl_pred == -1 else 0
