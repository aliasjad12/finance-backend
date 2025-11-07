import joblib, torch
import numpy as np
from future_prediction.utils import fetch_category_monthly_series
from future_prediction.train_forcaster import LSTMRegressor
import pandas as pd 
from sklearn.preprocessing import MinMaxScaler
import os

def predict_for_category(user_id: str, category: str):
    ts = fetch_category_monthly_series(user_id, category)
    if len(ts) == 0:
        return None, None

    # ── Fallback for new users (<12 months) ──
    if len(ts) < 12:
        last_n = ts[-3:] if len(ts) >= 3 else ts
        avg_pred = float(last_n.mean()) if not last_n.empty else 0.0
        print(f" Using fallback avg for {user_id}/{category}: {avg_pred}")
        return round(avg_pred, 2), "fallback"

    # ── Normal ARIMA+LSTM path ──
    ts.index = pd.to_datetime(ts.index)
    ts = ts.asfreq("MS")

    arima_path = f"./models/{user_id}/category_arima/{category}_arima.pkl"
    lstm_path = f"./models/{user_id}/category_lstm/{category}_lstm.pt"
    scaler_path = f"./models/{user_id}/category_lstm/scaler_{category}.pkl"

    ar_pred = None
    if os.path.exists(arima_path):
        try:
            arima = joblib.load(arima_path)
            ar_pred = float(arima.predict(n_periods=1).iloc[0])
        except Exception as e:
            print(f" ARIMA failed for {category}: {e}")

    lstm_model = LSTMRegressor()
    lstm_model.load_state_dict(torch.load(lstm_path, map_location="cpu")["model"])
    lstm_model.eval()
    scaler: MinMaxScaler = joblib.load(scaler_path)

    seq = scaler.transform(ts.values.reshape(-1, 1)).flatten()
    seq = np.pad(seq, (max(0, 12 - len(seq)), 0), mode="constant")[-12:]
    x = torch.tensor(seq, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)

    with torch.no_grad():
        lstm_scaled = lstm_model(x).item()
    lstm_pred = float(scaler.inverse_transform([[lstm_scaled]])[0][0])

    if ar_pred is not None:
        return round((ar_pred + lstm_pred) / 2, 2), "ARIMA+LSTM"
    return round(lstm_pred, 2), "LSTM_only"


def predict_all_categories(user_id: str, categories: list[str]):
    category_preds = {}
    sources = {}
    total = 0.0
    final_source = "ARIMA+LSTM"  # assume best, downgrade if fallback used

    for cat in categories:
        pred, source = predict_for_category(user_id, cat)
        if pred is not None:
            category_preds[cat] = pred
            sources[cat] = source
            total += pred
            if source == "fallback":
                final_source = "fallback"

    return {
        "month": "Next Month",
        "categoryExpenses": category_preds,
        "totalPrediction": round(total, 2),
        "source": final_source,      # overall source
        "sources": sources           # per-category source (optional but useful)
    }
