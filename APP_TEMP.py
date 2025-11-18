from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = "secret123"

# SQLite 資料庫設定
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///booking.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# 資料庫模型
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    date = db.Column(db.String(20))
    time = db.Column(db.String(20))

# 首次執行自動建立資料庫
with app.app_context():
    db.create_all()


# 首頁：預約表單
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form["name"]
        date = request.form["date"]
        time = request.form["time"]

        # 防止重複預約同一天同時段
        exist = Booking.query.filter_by(date=date, time=time).first()
        if exist:
            flash("此時段已被預約！請選擇其他時間。")
            return redirect(url_for("index"))

        new_booking = Booking(name=name, date=date, time=time)
        db.session.add(new_booking)
        db.session.commit()

        flash("預約成功！")
        return redirect(url_for("index"))

    return render_template("index.html")


# 查看預約列表
@app.route("/list")
def list_bookings():
    bookings = Booking.query.order_by(Booking.date, Booking.time).all()
    return render_template("list.html", bookings=bookings)


if __name__ == "__main__":
    app.run(debug=True)
