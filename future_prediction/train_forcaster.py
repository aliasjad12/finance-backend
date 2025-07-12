
from dotenv import load_dotenv
load_dotenv()
import os, torch, joblib
import numpy as np
import pandas as pd
from torch import nn
from torch.utils.data import DataLoader, Dataset
from sklearn.preprocessing import MinMaxScaler
import pmdarima as pm
from future_prediction.utils import fetch_category_monthly_series

# ───────────── Dataset & Model ──────────────
class SeqDataset(torch.utils.data.Dataset):
    def __init__(self, data, seq_len=12):
        self.x, self.y = [], []
        for i in range(len(data) - seq_len):
            self.x.append(data[i:i + seq_len])
            self.y.append(data[i + seq_len])
        self.x = torch.tensor(self.x).unsqueeze(-1).float()
        self.y = torch.tensor(self.y).float()

    def __len__(self): return len(self.x)
    def __getitem__(self, idx): return self.x[idx], self.y[idx]

class LSTMRegressor(nn.Module):
    def __init__(self, hidden=32):
        super().__init__()
        self.lstm = nn.LSTM(1, hidden, batch_first=True)
        self.fc = nn.Linear(hidden, 1)

    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.fc(h[-1]).squeeze(-1)

# ───────────── Train One Category ──────────────
def train_for_category(user_id: str, category: str):
    ts = fetch_category_monthly_series(user_id, category, months_back=None)

    if len(ts) < 12:
        print(f"⏩ Not enough data for {category}")
        return

    # ----- ARIMA -----
    try:
        arima = pm.auto_arima(
            ts,
            seasonal=True,
            m=12,
            suppress_warnings=True,
            error_action='ignore',
            trace=True  # ✅ enable logs
        )
        os.makedirs("./models/category_arima", exist_ok=True)
        joblib.dump(arima, f"./models/category_arima/{category}_arima.pkl")
        print(f"✅ ARIMA saved for {category}")
    except Exception as e:
        print(f"⚠️ ARIMA training failed for {category}: {e}")

    # ----- LSTM -----
    os.makedirs("./models/category_lstm", exist_ok=True)
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(ts.values.reshape(-1, 1)).flatten()
    joblib.dump(scaler, f"./models/category_lstm/scaler_{category}.pkl")

    dataset = SeqDataset(scaled)
    if len(dataset) == 0:
        print(f"⏩ Not enough LSTM data for {category}")
        return

    loader = DataLoader(dataset, batch_size=16, shuffle=True)
    model = LSTMRegressor()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    for _ in range(50):
        for x, y in loader:
            opt.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()

    torch.save({"model": model.state_dict()}, f"./models/category_lstm/{category}_lstm.pt")
    print(f"✅ LSTM saved for {category}")

# ───────────── Train All Categories ──────────────
def train_all_categories(user_id: str, categories: list[str]):
    for cat in categories:
        print(f"🔁 Training for {cat}...")
        train_for_category(user_id, cat)

# ───────────── Main Script ──────────────
if __name__ == "__main__":
    from firebase_admin import firestore
    db = firestore.client()

    categories = ["Food", "Utilities", "Travel", "Shopping", "Health"]
    users_ref = db.collection("users")
    users = users_ref.stream()

    for user in users:
        user_id = user.id
        print(f"\n🧪 Checking user: {user_id}")
        any_category_has_12_months = False
        for cat in categories:
            ts = fetch_category_monthly_series(user_id, cat)
            if ts is not None and len(ts) >= 12:
                any_category_has_12_months = True
                break
        if any_category_has_12_months:
            print(f"✅ Training for {user_id}")
            train_all_categories(user_id, categories)
        else:
            print(f"⏩ Skipping {user_id} (Not enough data)")
