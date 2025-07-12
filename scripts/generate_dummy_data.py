import random
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# ─── 1. Firebase initialise ──────────────────────────────────────────
if not firebase_admin._apps:
    cred = credentials.Certificate(
        "C:/Users/Abid computers/Desktop/finance_manager_backend/"
        "finalyear-3b277-firebase-adminsdk-fbsvc-b2c4c69496.json"
    )
    firebase_admin.initialize_app(cred)

db = firestore.client()
user_id = "MdrxqkDP1EhlqDhtwNMXrtoA2I22"
records_ref = db.collection("users").document(user_id).collection("records")

# ─── 2. Wipe ALL existing month docs ─────────────────────────────────
for doc in records_ref.stream():
    doc.reference.delete()
print("🗑️ All previous records removed.")

# ─── 3. Seasonal multipliers ─────────────────────────────────────────
def month_factor(month, base=1.0):
    if month == 12:
        return base * 1.15  # December shopping/food spike
    if month in (6, 7, 8):
        return base * 1.5   # Summer travel
    if month in (1, 2):
        return base * 1.1   # Winter utilities
    if month == 11:
        return base * 1.3   # November shopping bump
    return base

# ─── 4. Generate 36 months (ending July 2025) ─────────────────────────
TOTAL_INCOME = 200_000
categories = ["Food", "Utilities", "Travel", "Shopping", "Health"]

start = datetime(2025, 7, 1)  # July 2025
for i in range(36):
    month_dt  = datetime(start.year, start.month, 1)
    m_str     = month_dt.strftime("%Y-%m")
    m_number  = month_dt.month
    year_frac = (35 - i) / 36  # trend: oldest = 0 → recent = 1

    # ─ Category calculations
    food     = int(40_000 * (1 + 0.05 * year_frac) * month_factor(m_number, 1))
    util     = int(12_000 * month_factor(m_number, 1))
    travel   = int(8_000 * month_factor(m_number, 1))
    shopping = int(15_000 * (1 + 0.07 * year_frac) * month_factor(m_number, 1))
    health   = int(TOTAL_INCOME * random.uniform(0.03, 0.06))

    raw_total = food + util + travel + shopping + health
    if raw_total > TOTAL_INCOME:
        scale = TOTAL_INCOME / raw_total
        food     = int(food * scale)
        util     = int(util * scale)
        travel   = int(travel * scale)
        shopping = int(shopping * scale)
        health   = TOTAL_INCOME - (food + util + travel + shopping)

    cat_map = {
        "Food": food,
        "Utilities": util,
        "Travel": travel,
        "Shopping": shopping,
        "Health": health
    }

    # ─── 5. Add monthly document ─────────────────────────────────────
    record_doc = records_ref.document(m_str)
    record_doc.set({
        "totalIncome": TOTAL_INCOME,
        "spentAmount": sum(cat_map.values()),
        "categoryExpenses": cat_map
    })

    # ─── 6. Add category-wise subcollections ─────────────────────────
    for category, amount in cat_map.items():
        record_doc.collection("categories").document(category).collection("expenses").add({
            "amount": amount,
            "timestamp": month_dt
        })

    # ⏮️ Move to previous month
    prev_month = month_dt.replace(day=1) - timedelta(days=1)
    start = prev_month.replace(day=1)

print("✅ 36 months (Aug 2022 to Jul 2025) written successfully.")
