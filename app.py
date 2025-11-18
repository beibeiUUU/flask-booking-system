from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "super_secret_key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///booking.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# ----------------- 資料表 -----------------
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(50))          # 哪個帳號建立的
    title = db.Column(db.String(100))        # 預約名稱
    date = db.Column(db.String(20))          # yyyy-mm-dd
    start_time = db.Column(db.String(20))    # HH:MM
    end_time = db.Column(db.String(20))      # HH:MM


with app.app_context():
    db.create_all()


# ----------------- 使用者帳號 -----------------
USERS = {
    "user1": {"password": "123456", "role": "user"},
    "user2": {"password": "234567", "role": "user"},
    "user3": {"password": "345678", "role": "user"},
    "user4": {"password": "456789", "role": "user"},
    "user5": {"password": "567890", "role": "user"},
    "admin1": {"password": "admin123", "role": "admin"},
    "admin2": {"password": "admin123", "role": "admin"},
}


# 產生 30 分鐘一格的時間列表
def generate_time_slots():
    times = []
    t = datetime.strptime("00:00", "%H:%M")
    for _ in range(48):  # 24*2
        times.append(t.strftime("%H:%M"))
        t += timedelta(minutes=30)
    return times


def duration_hours(start_str, end_str):
    s = datetime.strptime(start_str, "%H:%M")
    e = datetime.strptime(end_str, "%H:%M")
    return (e - s).total_seconds() / 3600


def is_overlap(start1, end1, start2, end2):
    """判斷兩個時間區間是否重疊"""
    s1 = datetime.strptime(start1, "%H:%M")
    e1 = datetime.strptime(end1, "%H:%M")
    s2 = datetime.strptime(start2, "%H:%M")
    e2 = datetime.strptime(end2, "%H:%M")
    return not (e1 <= s2 or e2 <= s1)


# ----------------- 登入 / 登出 -----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = USERS.get(username)
        if not user or user["password"] != password:
            flash("帳號或密碼錯誤")
            return redirect(url_for("login"))

        session["username"] = username
        session["role"] = user["role"]
        flash("登入成功")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("已登出")
    return redirect(url_for("login"))


# ----------------- 首頁：新增預約 -----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    role = session["role"]
    time_slots = generate_time_slots()

    if request.method == "POST":
        title = request.form["title"].strip()
        date = request.form["date"]
        start = request.form["start_time"]
        end = request.form["end_time"]

        if not title:
            flash("預約名稱不能為空")
            return redirect(url_for("index"))

        # 時間先做基本檢查
        if start >= end:
            flash("結束時間必須晚於開始時間")
            return redirect(url_for("index"))

        dur = duration_hours(start, end)
        if dur > 3:
            flash("單次預約最多 3 小時")
            return redirect(url_for("index"))

        # 計算這個使用者這一天已預約的總時數（不含這次）
        bookings_same_day = Booking.query.filter_by(user=username, date=date).all()
        used = sum(duration_hours(b.start_time, b.end_time) for b in bookings_same_day)
        if used + dur > 3:
            flash("每個使用者每天最多只能預約 3 小時")
            return redirect(url_for("index"))

        # 檢查同一天任何人的預約是否時間衝突
        all_that_day = Booking.query.filter_by(date=date).all()
        for b in all_that_day:
            if is_overlap(start, end, b.start_time, b.end_time):
                flash(f"與 {b.user} 的預約時間重疊，請選擇其他時間")
                return redirect(url_for("index"))

        # 寫入資料庫
        new_booking = Booking(
            user=username,
            title=title,
            date=date,
            start_time=start,
            end_time=end,
        )
        db.session.add(new_booking)
        db.session.commit()
        flash("預約成功")
        return redirect(url_for("list_bookings"))

    return render_template(
        "index.html",
        time_slots=time_slots,
        username=username,
        role=role,
    )


# ----------------- 預約列表 -----------------
@app.route("/list")
def list_bookings():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    role = session["role"]

    bookings = Booking.query.order_by(Booking.date, Booking.start_time).all()
    return render_template(
        "list.html",
        bookings=bookings,
        username=username,
        role=role,
    )


# ----------------- 編輯預約 -----------------
@app.route("/edit/<int:booking_id>", methods=["GET", "POST"])
def edit_booking(booking_id):
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    role = session["role"]
    booking = Booking.query.get_or_404(booking_id)

    # 權限檢查：只有自己或 admin 可以改
    if role != "admin" and booking.user != username:
        flash("你沒有權限修改這筆預約")
        return redirect(url_for("list_bookings"))

    time_slots = generate_time_slots()

    if request.method == "POST":
        title = request.form["title"].strip()
        date = request.form["date"]
        start = request.form["start_time"]
        end = request.form["end_time"]

        if not title:
            flash("預約名稱不能為空")
            return redirect(url_for("edit_booking", booking_id=booking_id))

        if start >= end:
            flash("結束時間必須晚於開始時間")
            return redirect(url_for("edit_booking", booking_id=booking_id))

        dur = duration_hours(start, end)
        if dur > 3:
            flash("單次預約最多 3 小時")
            return redirect(url_for("edit_booking", booking_id=booking_id))

        # 計算這個使用者當天其他預約總時數（排除自己這筆）
        same_user_day = Booking.query.filter(
            Booking.user == booking.user,
            Booking.date == date,
            Booking.id != booking.id
        ).all()
        used = sum(duration_hours(b.start_time, b.end_time) for b in same_user_day)
        if used + dur > 3:
            flash("每個使用者每天最多只能預約 3 小時")
            return redirect(url_for("edit_booking", booking_id=booking_id))

        # 時間衝突檢查（排除自己）
        same_day = Booking.query.filter(
            Booking.date == date,
            Booking.id != booking.id
        ).all()
        for b in same_day:
            if is_overlap(start, end, b.start_time, b.end_time):
                flash(f"與 {b.user} 的預約時間重疊，請選擇其他時間")
                return redirect(url_for("edit_booking", booking_id=booking_id))

        # 更新
        booking.title = title
        booking.date = date
        booking.start_time = start
        booking.end_time = end
        db.session.commit()
        flash("修改成功")
        return redirect(url_for("list_bookings"))

    return render_template(
        "edit.html",
        booking=booking,
        time_slots=time_slots,
        username=username,
        role=role,
    )


# ----------------- 刪除預約 -----------------
@app.route("/delete/<int:booking_id>")
def delete_booking(booking_id):
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    role = session["role"]
    booking = Booking.query.get_or_404(booking_id)

    if role != "admin" and booking.user != username:
        flash("你沒有權限刪除這筆預約")
        return redirect(url_for("list_bookings"))

    db.session.delete(booking)
    db.session.commit()
    flash("已刪除")
    return redirect(url_for("list_bookings"))


if __name__ == "__main__":
    app.run(debug=True)
