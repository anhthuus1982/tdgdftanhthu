import pandas as pd
import numpy as np
import logging
from ta.trend import ADXIndicator, SMAIndicator
from ta.momentum import RSIIndicator

nhat_ky = logging.getLogger(__name__)

def lay_tin_hieu(du_lieu, trong_so):
    df = pd.DataFrame(du_lieu)
    df = df.astype({'high': float, 'low': float, 'close': float})

    rsi = RSIIndicator(close=df['close'], window=14).rsi().iloc[-1]
    adx = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
    sma_50 = SMAIndicator(close=df['close'], window=50).sma_indicator().iloc[-1]
    sma_200 = SMAIndicator(close=df['close'], window=200).sma_indicator().iloc[-1]

    tin_hieu = {}
    tin_hieu['rsi'] = 1 if rsi < 35 else -1 if rsi > 65 else 0
    tin_hieu['adx'] = 1 if adx.adx().iloc[-1] > 25 and adx.adx_pos().iloc[-1] > adx.adx_neg().iloc[-1] else -1 if adx.adx().iloc[-1] > 25 else 0
    tin_hieu['ma'] = 1 if sma_50 > sma_200 else -1 if sma_50 < sma_200 else 0

    return tin_hieu, adx.adx().iloc[-1], rsi

def kiem_tra_volume_breakout(du_lieu):
    df = pd.DataFrame(du_lieu)
    sma_volume = df['volume'].rolling(window=20).mean()
    return 1 if df['volume'].iloc[-1] > sma_volume.iloc[-1] * 2 and df['close'].iloc[-1] > df['close'].iloc[-2] else -1 if df['volume'].iloc[-1] > sma_volume.iloc[-1] * 2 else 0
