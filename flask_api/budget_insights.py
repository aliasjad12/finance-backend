from flask import Blueprint, request, jsonify
from firebase_admin import firestore
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime
import firebase_admin

if not firebase_admin._apps:
    raise RuntimeError("Firebase app not initialized.")

db = firestore.client()
bp = Blueprint('budget', __name__)

@bp.route("/generate_budget", methods=["GET"])
def generate_budget():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    user_ref = db.collection("users").document(user_id)
    records_ref = user_ref.collection("records")
    records = list(records_ref.stream())
    if not records:
        return jsonify({"error": "No financial records found"}), 404

    # Sort and get latest month
    records_data = [r.to_dict() | {"month": r.id} for r in records]
    records_data.sort(key=lambda r: r["month"])
    latest_month = records_data[-1]["month"]
    current_record = records_ref.document(latest_month).get().to_dict()

    income = current_record.get("totalIncome", 0)
    spent = current_record.get("spentAmount", 0)
    category_exp = current_record.get("categoryExpenses", {})

    now = datetime.now()
    goals_ref = user_ref.collection("savings_goals")
    goals = list(goals_ref.stream())

    # Initialize containers
    savings_goals = {}
    monthly_savings_plan = {}
    suggestions = {}

    # ---------- Savings Goals Handling ----------
    if goals:
        savings_goals = {doc.id: doc.to_dict() for doc in goals}
        income_left = max(income - spent, 0)

        # Safe saving parameters
        ESSENTIAL_BUFFER_RATIO = 0.25  # Keep 25% for essentials
        SAFE_SAVING_RATIO = 0.4        # Max safe save % of income

        essential_buffer = ESSENTIAL_BUFFER_RATIO * income
        available_this_month = max(income_left - essential_buffer, 0)
        max_safe_save_month = income * SAFE_SAVING_RATIO

        urgent_goals_this_month = []
        processed_goals = []
        for doc_id, goal in savings_goals.items():
            name = goal.get("goal_name", doc_id)
            target = goal.get("target_amount", 0)
            saved = goal.get("amount_saved", 0)
            target_date = goal.get("end_date")
            amount_remaining = max(target - saved, 0)

            months_left = 1
            if target_date:
                try:
                    dt = datetime.fromisoformat(target_date)
                    if dt.year == now.year and dt.month == now.month + 1:
                        months_left = 2
                    else:
                        months_left = max(
                            1,
                            (dt.year - now.year) * 12 + (dt.month - now.month) +
                            (1 if dt.day > now.day else 0)
                        )
                except:
                    pass

            processed_goals.append({
                "id": doc_id,
                "name": name,
                "saved": saved,
                "remaining": amount_remaining,
                "months_left": months_left
            })

        remaining_safe_saving = min(max_safe_save_month, available_this_month)
        processed_goals.sort(key=lambda g: g["months_left"])

        for g in processed_goals:
            name = g["name"]
            amount_remaining = g["remaining"]
            saved = g["saved"]
            months_left = g["months_left"]

            already_saved_str = f"₹{saved:,.0f} already saved. " if saved > 0 else ""

            if amount_remaining <= 0:
                suggestions[f"✅ {name}"] = f"Goal '{name}' is already completed."
                monthly_savings_plan[name] = 0
                continue

            if months_left == 1:
                urgent_goals_this_month.append((name, amount_remaining))
                alloc = min(amount_remaining, remaining_safe_saving)
                if amount_remaining > income_left:
                    suggestions[f"⚠️ {name}"] = f"{already_saved_str}Goal '{name}' needs ₹{amount_remaining:,.0f} but only ₹{income_left:,.0f} left. Extend deadline or increase income."
                elif amount_remaining <= alloc:
                    suggestions[f"🎯 {name}"] = f"{already_saved_str}Save ₹{amount_remaining:,.0f} now to complete goal '{name}' this month."
                else:
                    suggestions[f"⚠️ {name}"] = f"{already_saved_str}Goal '{name}' requires more than safe saving limit. Save ₹{alloc:,.0f} now and extend deadline."
                monthly_savings_plan[name] = round(alloc, 2)
                remaining_safe_saving -= alloc

            elif months_left == 2:
                next_month_safe_limit = income * SAFE_SAVING_RATIO
                half_now = min(amount_remaining / 2, remaining_safe_saving)
                rest_next = amount_remaining - half_now

                if rest_next <= next_month_safe_limit:
                    suggestions[f"📅 {name}"] = (
                        f"{already_saved_str}Save ₹{half_now:,.0f} this month "
                        f"and ₹{rest_next:,.0f} next month to complete goal '{name}'."
                    )
                else:
                    suggestions[f"⚠️ {name}"] = (
                        f"{already_saved_str}Even splitting for goal '{name}' is not safe — "
                        f"next month's safe limit is ₹{next_month_safe_limit:,.0f}, "
                        f"but you'd need ₹{rest_next:,.0f}. Extend deadline or increase income."
                    )
                    half_now = min(amount_remaining, remaining_safe_saving)

                monthly_savings_plan[name] = round(half_now, 2)
                remaining_safe_saving -= half_now

            else:
                monthly_needed = amount_remaining / months_left
                alloc = min(monthly_needed, remaining_safe_saving)
                if monthly_needed <= max_safe_save_month:
                    suggestions[f"📅 {name}"] = f"{already_saved_str}Save about ₹{monthly_needed:,.0f} per month for {months_left} months to complete goal '{name}'."
                else:
                    suggestions[f"⚠️ {name}"] = f"{already_saved_str}Goal '{name}' needs ₹{monthly_needed:,.0f}/month which is above safe saving limit (₹{max_safe_save_month:,.0f}). Extend deadline."
                monthly_savings_plan[name] = round(alloc, 2)
                remaining_safe_saving -= alloc

        if len(urgent_goals_this_month) > 1:
            total_needed = sum(amt for _, amt in urgent_goals_this_month)
            if total_needed > income_left:
                goal_list = ", ".join([g for g, _ in urgent_goals_this_month])
                suggestions["⚠️ Urgent Goals Conflict"] = (
                    f"You have multiple urgent goals this month ({goal_list}) totaling ₹{total_needed:,.0f}, "
                    f"but only ₹{income_left:,.0f} left. Complete one and extend the others."
                )

    else:
        # No savings goals: still return budget insights
        income_left = max(income - spent, 0)
        suggestions["ℹ️ Savings"] = "You don’t have any savings goals yet. Add one to start tracking your progress!"

    # ---------- Predict Next Month’s Expenses ----------
    cat_hist = {}
    for r in records_data:
        for cat, amt in r.get("categoryExpenses", {}).items():
            cat_hist.setdefault(cat, []).append(amt)

    recommended = {}
    for cat, history in cat_hist.items():
        if len(history) >= 2:
            X = np.arange(len(history)).reshape(-1, 1)
            y = np.array(history)
            model = LinearRegression().fit(X, y)
            predicted = round(max(model.predict([[len(history)]])[0], 0), 2)
        else:
            predicted = round(history[-1], 2) if history else 0
        recommended[cat] = predicted

    # ---------- Dynamic Expense Insights ----------
    if category_exp:
        top_categories = sorted(category_exp.items(), key=lambda x: x[1], reverse=True)
        if top_categories:
            top_text = ", ".join([f"{cat} (₹{amt:,.0f})" for cat, amt in top_categories[:2]])
            suggestions["💡 Spending Insight"] = f"Your highest spending was in {top_text}. Consider reducing these next month."

    # ---------- Alerts ----------
    if spent >= income:
        suggestions["🚨 Overspending"] = f"You’ve already spent ₹{spent:,.2f} of ₹{income:,.2f} this month."
    if income > 0 and income_left / income < 0.10:
        suggestions["⚠️ Low Balance"] = "Your remaining balance is very low. Avoid non-essential spending."

    return jsonify({
        "recommended_budget_next_month": recommended,
        "suggestions": suggestions,
        "total_income": income,
        "spent": spent,
        "income_left": income_left,
        "savings_goals": monthly_savings_plan,
        "leftover_budget_after_savings": round(income_left - sum(monthly_savings_plan.values()), 2),
    })
