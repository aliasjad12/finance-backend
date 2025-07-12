import joblib, torch
import numpy as np
from future_prediction.utils import fetch_category_monthly_series
from future_prediction.train_forcaster import LSTMRegressor
import pandas as pd 
from sklearn.preprocessing import MinMaxScaler
import os

def predict_for_category(user_id: str, category: str):
    ts = fetch_category_monthly_series(user_id, category)
    if len(ts) < 12:
        return None

    ts.index = pd.to_datetime(ts.index)
    ts = ts.asfreq("MS")

    arima_path = f"./models/category_arima/{category}_arima.pkl"
    lstm_path = f"./models/category_lstm/{category}_lstm.pt"
    scaler_path = f"./models/category_lstm/scaler_{category}.pkl"

    # ── ARIMA (Try-Catch so app doesn’t crash) ────────────────────────
    ar_pred = None
    if os.path.exists(arima_path):
        try:
            arima = joblib.load(arima_path)
            ar_pred = float(arima.predict(n_periods=1).iloc[0])
        except Exception as e:
            print(f"⚠️ ARIMA failed for {category}: {e}")
    else:
        print(f"⚠️ ARIMA model not found for {category}, using LSTM only.")

    # ── LSTM ───────────────────────────────────────────────────────────
    lstm_model = LSTMRegressor()
    lstm_model.load_state_dict(torch.load(lstm_path, map_location="cpu")["model"])
    lstm_model.eval()
    scaler: MinMaxScaler = joblib.load(scaler_path)

    seq = scaler.transform(ts.values.reshape(-1, 1)).flatten()
    if len(seq) < 12:
        return None

    seq = np.pad(seq, (max(0, 12 - len(seq)), 0), mode="constant")[-12:]
    x = torch.tensor(seq, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)

    with torch.no_grad():
        lstm_scaled = lstm_model(x).item()
    lstm_pred = float(scaler.inverse_transform([[lstm_scaled]])[0][0])

    # ── Combine ARIMA and LSTM ─────────────────────────────────────────
    if ar_pred is not None:
        return round((ar_pred + lstm_pred) / 2, 2)
    return round(lstm_pred, 2)

def predict_all_categories(user_id: str, categories: list[str]):
    category_preds = {}
    total = 0.0
    for cat in categories:
        pred = predict_for_category(user_id, cat)
        if pred is not None:
            category_preds[cat] = pred
            total += pred

    return {
        "month": "Next Month",
        "categoryExpenses": category_preds,
        "totalPrediction": round(total, 2)
    }
