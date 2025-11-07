from dotenv import load_dotenv
load_dotenv()
import os, sys, torch, joblib, json
from datetime import datetime
import numpy as np
import pandas as pd
from torch import nn
from torch.utils.data import DataLoader
from sklearn.preprocessing import MinMaxScaler
import pmdarima as pm
import pathlib

from utils import fetch_category_monthly_series


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ───── Firebase ─────
import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ───── Torch dataset/model ─────
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

# ───── Helpers ─────
def get_metadata_path(user_id: str):
    return f"./models/{user_id}/metadata.json"

def load_metadata(user_id: str):
    path = get_metadata_path(user_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def save_metadata(user_id: str, last_expense_update: datetime):
    path = get_metadata_path(user_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "last_trained": datetime.utcnow().isoformat(),
        "last_expense_update": last_expense_update.isoformat()
    }
    with open(path, "w") as f:
        json.dump(data, f)

def fetch_last_expense_update(user_id: str) -> datetime | None:
    """Find the latest modified record date from Firestore"""
    records_ref = db.collection("users").document(user_id).collection("records")
    docs = records_ref.stream()

    latest = None
    for doc in docs:
        data = doc.to_dict()
        if not data: 
            continue
        snapshot = doc._reference.get()
        update_time = snapshot.update_time
        if update_time:
            dt = update_time.replace(tzinfo=None)  # strip tz
            if latest is None or dt > latest:
                latest = dt
    return latest

def needs_retraining(user_id: str) -> bool:
    meta = load_metadata(user_id)
    last_trained_expense_update = meta.get("last_expense_update")

    latest_expense_update = fetch_last_expense_update(user_id)
    if latest_expense_update is None:
        return False  # no expenses

    if not last_trained_expense_update:
        return True  # never trained before

    last_trained_expense_update = datetime.fromisoformat(last_trained_expense_update)

    latest_norm = latest_expense_update.replace(microsecond=0)
    trained_norm = last_trained_expense_update.replace(microsecond=0)

    return latest_norm > trained_norm


# ───── Logging helpers ─────
def ensure_user_dirs(user_id: str):
    base = os.path.join("./models", user_id)
    os.makedirs(base, exist_ok=True)
    os.makedirs(os.path.join(base, "category_arima"), exist_ok=True)
    os.makedirs(os.path.join(base, "category_lstm"), exist_ok=True)
    os.makedirs(os.path.join(base, "logs"), exist_ok=True)
    return base

# global variable for current log file
_current_log_file = None

def start_new_log(user_id: str):
    """Call this once per training run to create a fresh log file."""
    global _current_log_file
    base = ensure_user_dirs(user_id)
    logs_dir = os.path.join(base, "logs")
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    _current_log_file = os.path.join(logs_dir, f"run_{ts}.txt")
    os.makedirs(logs_dir, exist_ok=True)
    return _current_log_file

def append_log(user_id: str, text: str):
    """Append text to the current log file for this run."""
    global _current_log_file
    if _current_log_file is None:
        start_new_log(user_id)
    with open(_current_log_file, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    return _current_log_file



# ───── Training ─────
def train_for_category(user_id: str, category: str):
    ts = fetch_category_monthly_series(user_id, category)
    if ts is None or len(ts) < 12:
        msg = f"Not enough data for {user_id}/{category}"
        print(msg)
        append_log(user_id, msg)
        return

    arima_dir = f"./models/{user_id}/category_arima"
    lstm_dir = f"./models/{user_id}/category_lstm"
    os.makedirs(arima_dir, exist_ok=True)
    os.makedirs(lstm_dir, exist_ok=True)

    arima_path = f"{arima_dir}/{category}_arima.pkl"
    lstm_path = f"{lstm_dir}/{category}_lstm.pt"

    # ───── ARIMA ─────
    try:
        arima = pm.auto_arima(
            ts, seasonal=True, m=12, suppress_warnings=True,
            error_action='ignore', trace=False
        )
        joblib.dump(arima, arima_path)
        msg = f"ARIMA saved for {user_id}/{category}"
        print(msg)
        append_log(user_id, msg)
    except Exception as e:
        msg = f"ARIMA training failed for {category}: {e}"
        print(msg)
        append_log(user_id, msg)

    # ───── LSTM ─────
    try:
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(ts.values.reshape(-1, 1)).flatten()
        joblib.dump(scaler, f"{lstm_dir}/scaler_{category}.pkl")

        dataset = SeqDataset(scaled)
        if len(dataset) == 0:
            msg = f"Not enough LSTM data for {user_id}/{category}"
            print(msg)
            append_log(user_id, msg)
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

        torch.save({"model": model.state_dict()}, lstm_path)
        msg = f"LSTM saved for {user_id}/{category}"
        print(msg)
        append_log(user_id, msg)
    except Exception as e:
        msg = f"LSTM training failed for {category}: {e}"
        print(msg)
        append_log(user_id, msg)
        


def train_all_categories(user_id: str, categories: list[str]):
    for cat in categories:
        msg = f"\nTraining for {user_id}/{cat}"
        print(msg)
        append_log(user_id, msg)
        train_for_category(user_id, cat) 


# ───── Entrypoint ─────
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python train_forcaster.py <user_id>")
        sys.exit(1)

    user_id = sys.argv[1]
    categories = ["Food", "Utilities", "Travel", "Shopping", "Health"]

    ensure_user_dirs(user_id)
    start_new_log(user_id) 
    append_log(user_id, f"Training started for {user_id} at {datetime.utcnow().isoformat()}")

    print(f"Checking if retraining is needed for {user_id}...")
    append_log(user_id, f"Checking if retraining is needed for {user_id}...")

    # if not needs_retraining(user_id):
#     msg = "✅ Models are already up to date. Skipping training."
#     print(msg)
#     append_log(user_id, msg)
#     sys.exit(0)

    msg = f"Starting training for {user_id}..."
    print(msg)
    append_log(user_id, msg)

    train_all_categories(user_id, categories)

    last_update = fetch_last_expense_update(user_id)
    if last_update:
        save_metadata(user_id, last_update)

    msg = "Training finished ✅"
    print(msg)
    append_log(user_id, msg)
