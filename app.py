from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import pickle
import os
import pandas as pd
import json

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------------- Load model ---------------- #
with open("model/cost_model.pkl", "rb") as f:
    model, columns = pickle.load(f)

MULTIPLIER_FILE = "company_multipliers.json"

def load_multipliers():
    if not os.path.exists(MULTIPLIER_FILE):
        default = {"HDFC Ergo": 1.0, "ICICI Lombard": 1.0, "Niva Bupa": 1.0, "Star Health": 1.0}
        with open(MULTIPLIER_FILE, "w") as f:
            json.dump(default, f)
        return default
    with open(MULTIPLIER_FILE) as f:
        return json.load(f)

def save_multipliers(multipliers):
    with open(MULTIPLIER_FILE, "w") as f:
        json.dump(multipliers, f)

def init_db():
    conn = sqlite3.connect("insurance.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        name TEXT,
        age INTEGER,
        height REAL,
        weight REAL,
        claim_history TEXT,
        gender TEXT,
        marital_status TEXT,
        region TEXT,
        salary REAL,
        occupation TEXT,
        alcohol TEXT,
        smoker TEXT,
        exercise TEXT,
        diseases TEXT,
        family_history TEXT,
        disability TEXT,
        surgeries TEXT,
        is_admin INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        sum_insured REAL,
        policy_term INTEGER,
        policy_type TEXT,
        dependents INTEGER,
        add_ons TEXT,
        company TEXT,
        premium REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("insurance.db")

# ---------------- REGISTER ---------------- #
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        name = request.form["name"]
        age = request.form["age"]
        height = request.form["height"]
        weight = request.form["weight"]
        claim_history = request.form.get("claim_history", "Never")
        gender = request.form.get("gender")
        marital_status = request.form.get("marital_status")
        region = request.form.get("region")
        salary = request.form.get("salary")
        occupation = request.form.get("occupation")
        alcohol = request.form.get("alcohol")
        smoker = request.form.get("smoker")
        exercise = request.form.get("exercise")
        diseases = ",".join(request.form.getlist("diseases")) if request.form.getlist("diseases") else ""
        family_history = ",".join(request.form.getlist("family_history")) if request.form.getlist("family_history") else ""
        disability = request.form.get("disability")
        surgeries = request.form.get("surgeries")

        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match")

        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO users
                (username, password, name, age, height, weight, claim_history, gender, marital_status, region, salary, occupation, alcohol, smoker, exercise, diseases, family_history, disability, surgeries)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (username, password, name, age, height, weight, claim_history, gender, marital_status, region, salary, occupation, alcohol, smoker, exercise, diseases, family_history, disability, surgeries))
            conn.commit()
            user_id = cur.lastrowid
            conn.close()

            session["user_id"] = user_id
            session["username"] = username
            session["name"] = name
            session["is_admin"] = False

            return redirect(url_for("home"))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Username already exists")

    return render_template("register.html")

# ---------------- LOGIN ---------------- #
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT id, username, password, name, is_admin FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
       

        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]
            session["name"] = user[3]
            session["is_admin"] = True if user[4] == 1 else False

        
            conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id=?", (user[0],))
            conn.commit()
            conn.close()

            if session["is_admin"]:
                return redirect(url_for("admin_panel"))
            else:
                return redirect(url_for("home"))
        else:
            conn.close()
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

# ---------------- LOGOUT ---------------- #
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- HOME ---------------- #
@app.route("/")
def home():
    if "user_id" not in session or session.get("is_admin"):
        return redirect(url_for("login"))

    conn = get_db()
    history = conn.execute("SELECT * FROM predictions WHERE user_id=? ORDER BY id DESC",
                           (session["user_id"],)).fetchall()
    conn.close()
    return render_template("index.html", user_inputs={}, user_history=history, name=session.get("name"), company_premiums=None)

# ---------------- PROFILE ---------------- #
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session or session.get("is_admin"):
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        
        name = request.form["name"] 
        age = request.form["age"]
        height = request.form["height"]
        weight = request.form["weight"]
        gender = request.form["gender"]
        marital_status = request.form["marital_status"]
        region = request.form["region"]
        salary = request.form["salary"]
        occupation = request.form["occupation"]
        alcohol = request.form["alcohol"]
        smoker = request.form["smoker"]
        exercise = request.form["exercise"]
        diseases = ",".join(request.form.getlist("diseases")) if request.form.getlist("diseases") else ""
        family_history = ",".join(request.form.getlist("family_history")) if request.form.getlist("family_history") else ""
        disability = request.form["disability"]
        surgeries = request.form["surgeries"]
        
        cur.execute("""
            UPDATE users SET
                name=?,
                age=?, height=?, weight=?, gender=?, marital_status=?, region=?, salary=?, occupation=?,
                alcohol=?, smoker=?, exercise=?, diseases=?, family_history=?, disability=?, surgeries=?
            WHERE id=?
        """, (
            name, age, height, weight, gender, marital_status, region, salary, occupation, alcohol, smoker, exercise,
            diseases, family_history, disability, surgeries, session["user_id"]
        ))
        conn.commit()

    cur.execute("SELECT * FROM users WHERE id=?", (session["user_id"],))
    row = cur.fetchone()
    keys = [d[0] for d in cur.description] if hasattr(cur, 'description') and cur.description else [
        "id", "username", "password", "name", "age", "height", "weight", "claim_history", "gender", "marital_status",
        "region", "salary", "occupation", "alcohol", "smoker", "exercise", "diseases", "family_history", "disability", "surgeries", "is_admin"
    ]
    user = dict(zip(keys, row))

    
    for k in ["diseases", "family_history"]:
        if user.get(k): user[k] = user[k].split(",")
        else: user[k] = []
    conn.close()
    return render_template("profile.html", user=user, name=session.get("name"))

# ---------------- HISTORY ---------------- #
@app.route("/history")
def history():
    if "user_id" not in session or session.get("is_admin"):
        return redirect(url_for("login"))

    conn = get_db()
    history_data = conn.execute("SELECT * FROM predictions WHERE user_id=? ORDER BY id DESC",
                                (session["user_id"],)).fetchall()
    conn.close()
    return render_template("history.html", history=history_data)

# ---------------- ADMIN PANEL ---------------- #
from datetime import datetime, timedelta

@app.route("/admin")
def admin_panel():
    if "user_id" not in session or not session.get("is_admin"):
        return redirect(url_for("login"))

    conn = get_db()
    users = conn.execute("SELECT id, username, name, age, height, weight, claim_history, gender, marital_status, region, salary, occupation, alcohol, smoker, exercise, diseases, family_history, disability, surgeries FROM users  WHERE is_admin=0").fetchall()
    total_users = len(users)
    
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE is_admin=0 AND last_login >= ?", (twenty_four_hours_ago,))
    active_users = cur.fetchone()[0]

    submissions = conn.execute("SELECT * FROM predictions ORDER BY id DESC").fetchall()
   
    company_trends = {}
    policy_trends = {}
    premium_distribution = {}
    age_distribution = {}

    for row in submissions:
        company = row[7]       
        policy_type = row[4]   
        premium = row[8]
        user_id = row[1]
        
        user = conn.execute("SELECT age FROM users WHERE id=?", (user_id,)).fetchone()
        age = int(user[0]) if user and user[0] else None

      
        company_trends.setdefault(company, []).append(premium)

       
        policy_trends[policy_type] = policy_trends.get(policy_type, 0) + 1

       
        prem_range = f"{int(premium//5000)*5000}-{int(premium//5000)*5000 + 4999}"
        premium_distribution[prem_range] = premium_distribution.get(prem_range, 0) + 1

       
        if age is not None:
            age_bin = f"{(age//10)*10}-{(age//10)*10+9}"
            age_distribution[age_bin] = age_distribution.get(age_bin, 0) + 1

    company_trends_avg = {k: round(sum(v)/len(v), 2) for k,v in company_trends.items()}
    multipliers = load_multipliers()
    conn.close()

    return render_template("admin.html",
                           users=users,
                           total_users=total_users,
                           active_users=active_users,
                           submissions=submissions,
                           company_trends=company_trends_avg,
                           policy_trends=policy_trends,
                           premium_distribution=premium_distribution,
                           age_distribution=age_distribution,
                           company_factors=multipliers)
@app.route('/remove_user', methods=['POST'])
def remove_user():
    if "user_id" not in session or not session.get("is_admin"):
        return redirect(url_for("login"))

    user_id = request.form['user_id']

    conn = get_db()
   
    conn.execute("DELETE FROM predictions WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

    flash('User removed successfully!', 'success')
    return redirect(url_for('admin_panel'))

    
# ---------------- UPDATE MULTIPLIERS ---------------- #
@app.route("/update_multipliers", methods=["POST"])
def update_multipliers():
    if "user_id" not in session or not session.get("is_admin"):
        return redirect(url_for("login"))

    multipliers = load_multipliers()
    for comp in multipliers.keys():
        if comp in request.form:
            try:
                multipliers[comp] = float(request.form[comp])
            except ValueError:
                pass

    save_multipliers(multipliers)
    return redirect(url_for("admin_panel"))

# ---------------- PREDICT ---------------- #
@app.route("/predict", methods=["POST"])
def predict():
    if "user_id" not in session or session.get("is_admin"):
        return redirect(url_for("login"))

    
    policy_inputs = {
        "sum_insured": float(request.form["sum_insured"]),
        "policy_term": int(request.form["policy_term"]),
        "policy_type": request.form["policy_type"],
        "dependents": int(request.form["dependents"]),
        "add_ons": request.form["add_ons"],
        "company": request.form["company"] if "company" in request.form else "HDFC Ergo"
    }

   
    conn = get_db()
    user_profile = conn.execute(
        "SELECT age, height, weight, claim_history FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    if not user_profile:
        conn.close()
        return redirect(url_for("logout"))

    age, height, weight, claim_history = user_profile
    bmi = weight / ((height/100) ** 2)

    
    user_inputs = {**policy_inputs,
                   "age": age, "height": height, "weight": weight,
                   "bmi": round(bmi,2), "claim_history": claim_history}

    df_row = {col: 0 for col in columns}
    for col in df_row:
        if col in user_inputs:
            df_row[col] = user_inputs[col]
    df = pd.DataFrame([df_row])

    
    encoding_map = {
        "claim_history": {"Never":0,"Frequent":1,"No":0,"Yes":1},
        "policy_type": {"Individual":0,"Family Floater":1, "1 Family":1, "2 Family":1, "3 Family":1, "Corporate":2}
    }
    for col, mapping in encoding_map.items():
        if col in df.columns:
            df[col] = df[col].map(mapping).fillna(0)

    premium = float(model.predict(df)[0])
    multipliers = load_multipliers()
    if user_inputs["company"] in multipliers:
        premium *= multipliers[user_inputs["company"]]
    premium = round(premium,2)

   
    conn.execute("""
    INSERT INTO predictions (
        user_id, sum_insured, policy_term, policy_type, dependents, add_ons, company, premium
    ) VALUES (?,?,?,?,?,?,?,?)
    """, (
        session["user_id"], policy_inputs["sum_insured"], policy_inputs["policy_term"],
        policy_inputs["policy_type"], policy_inputs["dependents"], policy_inputs["add_ons"],
        policy_inputs["company"], premium
    ))
    conn.commit()

    history = conn.execute("SELECT * FROM predictions WHERE user_id=? ORDER BY id DESC",
                           (session["user_id"],)).fetchall()
    conn.close()

    
    multipliers = load_multipliers()
    company_premiums = {}
    for comp in multipliers:
        pm = round(premium / multipliers[policy_inputs["company"]] * multipliers[comp], 2)
        company_premiums[comp] = pm

    return render_template("index.html", user_inputs=user_inputs, user_history=history,
                           premium=premium, name=session.get("name"), company_premiums=company_premiums)

if __name__ == "__main__":
    app.run(debug=True)