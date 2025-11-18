from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = "secret_key_for_session"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///booking.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# --------------------------
# 使用者資料表
# --------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True)
    password = db.Column(db.String(20))
    role = db.Column(db.String(10))  # admin 或 user

# --------------------------
# 預約資料
# --------------------------
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    user = db.Column(db.String(20))  # 建立這筆預約的使用者帳號
    date = db.Column(db.String(20))
    start_time = db.Column(db.String(20))
    end_time = db.Column(db.String(20))


# --------------------------
# 建立資料表 + 預設帳號
# --------------------------
with app.app_context():
    db.create_all()

    # 若無使用者資料，建立預設帳號
    if User.query.count() == 0:
        default_users = [
            ("user1", "123456", "user"),
            ("user2", "234567", "user"),
            ("user3", "345678", "user"),
            ("user4", "456789", "user"),
            ("user5", "567890", "user"),
            ("admin1", "admin123", "admin"),
            ("admin2", "admin123", "admin"),
        ]
        for u, p, r in default_users:
            db.session.add(User(username=u, password=p, role=r))
        db.session.commit()
        print("已建立預設帳號！")


# --------------------------
# 判斷 30 分鐘刻度
# --------------------------
def is_half_hour(t):
    dt = datetime.strptime(t, "%H:%M")
    return dt.minute in (0, 30)


# --------------------------
# 檢查是否時間衝突
# --------------------------
def is_conflict(date, start, end, exclude_id=None):
    s = datetime.strptime(start, "%H:%M")
    e = datetime.strptime(end, "%H:%M")

    bookings = Booking.query.filter_by(date=date).all()
    for b in bookings:
        if exclude_id and b.id == exclude_id:
            continue

        bs = datetime.strptime(b.start_time, "%H:%M")
        be = datetime.strptime(b.end_time, "%H:%M")

        # 有重疊
        if not (e <= bs or s >= be):
            return True
    return False


# --------------------------
# 登入頁面
# --------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username, password=password).first()

        if not user:
            flash("❌ 帳號或密碼錯誤")
            return redirect(url_for("login"))

        # 設定 session
        session["username"] = user.username
        session["role"] = user.role

        flash("✔ 登入成功")
        return redirect(url_for("index"))

    return render_template("login.html")


# --------------------------
# 登出
# --------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("已登出")
    return redirect(url_for("login"))


# --------------------------
# 首頁（新增預約）
# --------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        username = session["username"]
        name = request.form["name"]
        date = request.form["date"]
        start = request.form["start_time"]
        end = request.form["end_time"]

        # 30 分鐘
        if not is_half_hour(start) or not is_half_hour(end):
            flash("❌ 必須以 30 分鐘為單位")
            return redirect(url_for("index"))

        # 時間有效性
        if start >= end:
            flash("❌ 結束時間必須大於開始")
            return redirect(url_for("index"))

        # 最長 3 小時
        if datetime.strptime(end, "%H:%M") - datetime.strptime(start, "%H:%M") > timedelta(hours=3):
            flash("❌ 每次最多 3 小時")
            return redirect(url_for("index"))

        # 檢查衝突
        if is_conflict(date, start, end):
            flash("❌ 時間已被預約")
            return redirect(url_for("index"))

        new_booking = Booking(
            name=name,
            user=username,
            date=date,
            start_time=start,
            end_time=end
        )
        db.session.add(new_booking)
        db.session.commit()
        flash("✔ 預約成功")
        return redirect(url_for("list"))

    return render_template("index.html", username=session["username"], role=session["role"])


# --------------------------
# 列出所有預約
# --------------------------
@app.route("/list")
def list():
    if "username" not in session:
        return redirect(url_for("login"))

    bookings = Booking.query.order_by(Booking.date, Booking.start_time).all()
    return render_template("list.html", bookings=bookings, username=session["username"], role=session["role"])


# --------------------------
# 刪除預約
# --------------------------
@app.route("/delete/<int:id>")
def delete(id):
    if "username" not in session:
        return redirect(url_for("login"))

    b = Booking.query.get(id)

    if not b:
        flash("❌ 預約不存在")
        return redirect(url_for("list"))

    # 權限判斷
    if session["role"] != "admin" and b.user != session["username"]:
        flash("❌ 你沒有權限刪除這筆預約")
        return redirect(url_for("list"))

    db.session.delete(b)
    db.session.commit()
    flash("✔ 已刪除")
    return redirect(url_for("list"))


# --------------------------
# 修改預約（顯示頁面）
# --------------------------
@app.route("/edit/<int:id>")
def edit(id):
    if "username" not in session:
        return redirect(url_for("login"))

    b = Booking.query.get(id)

    if not b:
        flash("❌ 預約不存在")
        return redirect(url_for("list"))

    # 只有本人或 admin 可以修改
    if session["role"] != "admin" and b.user != session["username"]:
        flash("❌ 沒有權限修改")
        return redirect(url_for("list"))

    return render_template("edit.html", booking=b, username=session["username"], role=session["role"])


# --------------------------
# 更新預約
# --------------------------
@app.route("/update/<int:id>", methods=["POST"])
def update(id):
    if "username" not in session:
        return redirect(url_for("login"))

    b = Booking.query.get(id)

    if not b:
        flash("❌ 預約不存在")
        return redirect(url_for("list"))

    if session["role"] != "admin" and b.user != session["username"]:
        flash("❌ 你沒有權限")
        return redirect(url_for("list"))

    name = request.form["name"]
    date = request.form["date"]
    start = request.form["start_time"]
    end = request.form["end_time"]

    # 驗證
    if not is_half_hour(start) or not is_half_hour(end):
        flash("❌ 必須 30 分鐘為單位")
        return redirect(url_for("edit", id=id))

    if start >= end:
        flash("❌ 結束時間必須晚於開始")
        return redirect(url_for("edit", id=id))

    if datetime.strptime(end, "%H:%M") - datetime.strptime(start, "%H:%M") > timedelta(hours=3):
        flash("❌ 最長 3 小時")
        return redirect(url_for("edit", id=id))

    if is_conflict(date, start, end, exclude_id=id):
        flash("❌ 與其他預約衝突")
        return redirect(url_for("edit", id=id))

    # 更新
    b.name = name
    b.date = date
    b.start_time = start
    b.end_time = end
    db.session.commit()

    flash("✔ 修改成功")
    return redirect(url_for("list"))


# --------------------------
# 主程式
# --------------------------
if __name__ == "__main__":
    app.run(debug=True)
