from flask import Flask, request, render_template, url_for, redirect, session, render_template_string, Response
import random
import smtplib
import pymysql
import requests
from datetime import datetime, timedelta
from ultralytics import YOLO
import cv2
from flask import Response
import csv
from io import StringIO
from flask import send_from_directory
import time
import os
import numpy as np
import urllib.parse #搭配 UTF-8 URL 編碼，為了下載的CSV檔名可為中文

app = Flask(__name__)
app.secret_key = "supersecretkey"  # 用於 Session 加密

#載入YOLOv模型
model = YOLO("C:/Data/code/PycharmProjects/yolov8_practice_v1/best2.pt")

# 預跑一次模型，加快第一次推論速度
dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)
model(dummy_image)
print("✅ 模型 warm-up 預跑完成")

cap = cv2.VideoCapture(0)  # 攝影機編號對嗎？

#cap = cv2.VideoCapture("rtsp://admin:888888@192.168.12.172:8554/stream1")

#登入正確密碼
correct_password = "40227000"

#初始化全域變數
latest_snapshot = None

#自動建立資料夾(放下載照片用)
os.makedirs("static/snapshots", exist_ok=True)

# MySQL 資料庫連接設定
db = pymysql.connect(
    host="localhost",
    user="root",
    password="87St66ev18en940",
    database="rental_db"
)

# 生成隨機 6 位數 OTP
def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

# 發送 OTP 到使用者填寫的 Gmail
def send_otp_email(user_gmail, otp):
    try:
        sender_email = "jjjdddlllaaabbb@gmail.com"
        sender_password = "agyvyjwswzndghil"
        subject = "【OTP 驗證碼】租借系統"
        body = f"""
        親愛的使用者，您好！

        感謝您使用租借系統。以下是您的 OTP 驗證碼，請在 30 分鐘內完成驗證：

        OTP 驗證碼：{otp}

        若非本人操作，請忽略此郵件。

        感謝您的配合！
        租借系統團隊
        """

        message = f"From: 租借系統 <{sender_email}>\n"
        message += f"To: {user_gmail}\n"
        message += f"Subject: {subject}\n"
        message += "MIME-Version: 1.0\n"
        message += "Content-Type: text/plain; charset=utf-8\n"
        message += f"\n{body}"

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, user_gmail, message.encode("utf-8"))
        print("OTP 已成功發送")
        return True
    except Exception as e:
        print("Error sending email:", e)
        return False

# 更新 OTP 驗證邏輯
def validate_otp(entered_otp):
    try:
        with db.cursor() as cursor:
            # 查詢所有未過期且未使用的 OTP
            sql = """
            SELECT id FROM rentals 
            WHERE otp = %s AND expiration > NOW() AND used = 0
            """
            cursor.execute(sql, (entered_otp,))
            result = cursor.fetchone()

            # 如果找到符合條件的 OTP
            if result:
                # 更新該 OTP 為已使用
                update_sql = "UPDATE rentals SET used = 1 WHERE id = %s"
                cursor.execute(update_sql, (result[0],))
                db.commit()
                print(f"OTP {entered_otp} 驗證成功，已標記為使用")
                return True
            else:
                print(f"OTP {entered_otp} 驗證失敗或已過期")
                return False
    except Exception as e:
        print(f"驗證 OTP 時發生錯誤：{str(e)}")
        return False

# 傳送 OTP 到 ESP32
def send_otp_to_esp32(otp):
    try:
        esp32_ip = "192.168.12.200"  # 更新為你的 ESP32 IP 位址
        url = f"http://{esp32_ip}/send-otp"  # 對應的API端點
        response = requests.post(url, data={"otp": otp})
        if response.status_code == 200:
            print(f"成功發送 OTP 到 ESP32：{otp}")
            return True
        else:
            print(f"發送 OTP 失敗，狀態碼：{response.status_code}, 回應內容：{response.text}")
            return False
    except Exception as e:
        print(f"錯誤：無法連線到 ESP32 - {str(e)}")
        return False

#login路由
#跳轉路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == correct_password:  # 檢查密碼
            session['logged_in'] = True
            next_page = session.pop('next', url_for('welcome'))  # 預設導向歡迎頁(退出的話)
            return redirect(next_page)  # 成功登入後跳轉到原本想去的頁面
        else:
            error_message = "密碼錯誤，請重新輸入"  # 設定錯誤訊息
            return render_template('login.html', error=error_message)

    return render_template('login.html')

#登出路由
#跳轉路由(跳到home_redirect函式)
@app.route('/logout')
def logout():
    session.pop("logged_in", None)
    page = request.args.get("page", "home")
    print(" 使用者登出，來源頁面：", page)
    return redirect(url_for('welcome', page=page))

#主頁面路由
#跳轉路由
@app.route('/')
def root():
    # 保留 page 參數，讓 ?page=dashboard 不會被吃掉
    page = request.args.get('page', 'home')
    return redirect(url_for('welcome', page=page))

#welcome路由
#跳轉路由
@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

#rental路由
#跳轉路由
@app.route('/rental')
def rental():
    return render_template('rental.html')

#rental路由，按下按鈕傳送資料到資料庫
@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    count = request.form['count']
    duration = request.form['duration']
    phone = request.form['phone']
    gmail = request.form['gmail']

    try:
        with db.cursor() as cursor:
            sql = """
            INSERT INTO rentals (name, count, duration, phone, gmail, is_approved, used)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (name, count, duration, phone, gmail, False, False))
            db.commit()

        return render_template_string("""
            <script>
                alert("申請已送出，請等待管理者審核。");
                window.location.href = "/";
            </script>
        """)

    except Exception as e:
        print("Database error:", e)
        return render_template_string(f"""
            <script>
                alert("資料庫錯誤，請重試。");
                window.location.href = "/";
            </script>
        """)

#verify路由
#跳轉路由，初始化頁面
@app.route('/verify_requests')
def verify_requests():
    if not session.get("logged_in"):
        session['next'] = url_for('verify_requests')
        return redirect(url_for('login'))

    with db.cursor() as cursor:
        cursor.execute("""
            SELECT 
                id, name, gmail, count, duration, phone,
                TIMESTAMPDIFF(SECOND, NOW(), created_at + INTERVAL 30 MINUTE) AS remaining_seconds
            FROM rentals
            WHERE is_approved = FALSE
            AND created_at >= NOW() - INTERVAL 30 MINUTE
        """)
        requests = cursor.fetchall()

    return render_template('verify.html', requests=requests)


#verify路由，通過審核時送出OTP與寫入approved_rentals資料庫
@app.route('/approve/<int:request_id>', methods=['POST'])
def approve(request_id):
    otp = generate_otp()
    expiration_time = datetime.now() + timedelta(minutes=30)  # 30分鐘有效
    approved_time = datetime.now()
    otp_created_at = datetime.now()  # OTP創建時間

    try:
        with db.cursor() as cursor:
            # 取出原始申請資料
            cursor.execute("""
                SELECT name, count, duration, phone, gmail
                FROM rentals
                WHERE id = %s
            """, (request_id,))
            data = cursor.fetchone()
            if not data:
                return "找不到資料"

            name, count, duration, phone, gmail = data

            # 更新原表為已核准 + 設定 OTP 和期限
            cursor.execute("""
                UPDATE rentals
                SET otp = %s, expiration = %s, is_approved = TRUE
                WHERE id = %s
            """, (otp, expiration_time, request_id))

            # 寫入 approved_rentals 並加入 otp_created_at 欄位
            cursor.execute("""
                INSERT INTO approved_rentals (
                    name, count, duration, phone, gmail,
                    otp, expiration, approved_at, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                name, count, duration, phone, gmail,
                otp, expiration_time, approved_time, otp_created_at
            ))

            db.commit()

        # 寄送OTP與通知ESP32
        send_otp_email(gmail, otp)
        send_otp_to_esp32(otp)

        # 核准成功提醒
        return render_template_string(f"""
            <script>
                alert("✅ OTP 已成功發送至：{gmail}");
                window.location.href = "/verify_requests";
            </script>
        """)

    except Exception as e:
        print(f"審核錯誤：{e}")
        return render_template_string(f"""
            <script>
                alert("❌ 核准過程發生錯誤：{str(e)}");
                window.location.href="/verify_requests";
            </script>
        """)

#records路由
#查詢路由
#跳轉路由
@app.route('/records')
def show_records():
    # **修正登入檢查機制**
    if not session.get("logged_in"):
        session['next'] = url_for('show_records')  # 記住欲前往頁面
        return redirect(url_for('login'))

    date_filter = request.args.get("date")

    try:
        with db.cursor() as cursor:
            if date_filter:
                sql = """
                SELECT id, name, count, duration, phone, gmail, otp, approved_at, expiration 
                FROM approved_rentals 
                WHERE DATE(approved_at) = %s
                """
                cursor.execute(sql, (date_filter,))
            else:
                sql = """
                SELECT id, name, count, duration, phone, gmail, otp, approved_at, expiration 
                FROM approved_rentals
                """
                cursor.execute(sql)
            records = cursor.fetchall()

            # 格式化資料
            formatted_records = [
                {
                    "id": record[0],
                    "name": record[1],
                    "count": record[2],
                    "duration": record[3],
                    "phone": record[4],
                    "gmail": record[5],
                    "otp": record[6],
                    "created_at": str(record[7]), # 這裡其實是 approved_at
                    "expiration": str(record[8])
                }
                for record in records
            ]
            print("格式化後的資料：", formatted_records)

        print("傳遞到模板的資料：", formatted_records)
        return render_template('records.html', records=formatted_records)
    except Exception as e:
        print(f"資料庫查詢錯誤：{str(e)}")
        return f"資料庫查詢錯誤：{str(e)}"

#records路由
#下載路由
@app.route('/download_csv')
def download_csv():
    if not session.get("logged_in"):
        return redirect(url_for('login'))

    date_filter = request.args.get("date")

    try:
        with db.cursor() as cursor:
            if date_filter:
                cursor.execute("""
                    SELECT id, name, count, duration, phone, gmail, otp, approved_at
                    FROM approved_rentals
                    WHERE DATE(created_at) = %s
                """, (date_filter,))
            else:
                cursor.execute("""
                    SELECT id, name, count, duration, phone, gmail, otp, approved_at
                    FROM approved_rentals
                """)
            rows = cursor.fetchall()

        def generate():
            # 加上 BOM 讓 Excel 正常顯示中文
            data = ["\ufeffID,姓名,人數,時長,電話,Gmail,OTP,時間\n"]
            for row in rows:
                data.append(",".join([str(field) for field in row]) + "\n")
            return data

        filename = f"{date_filter}.csv" if date_filter else "全部紀錄.csv"
        quoted_filename = urllib.parse.quote(filename)

        return Response(generate(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}"})

    except Exception as e:
        return f"匯出錯誤：{str(e)}"

#entrance路由
#初始化頁面所需資訊
#進頁面前先驗證
@app.route('/entrance')
def entrance_page():
    if not session.get("logged_in"):
        session['next'] = url_for('entrance_page')  #這一行是關鍵
        return redirect(url_for('login'))
    return render_template("entrance.html")

#entrance路由
#顯示鏡頭畫面
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def generate_frames():
    global in_count, out_count, violation_count, last_violation_time, latest_snapshot, last_violation_labels

    in_count = 0
    out_count = 0
    violation_count = 0
    # last_violation_time = ""
    # latest_snapshot = ""
    last_violation_labels = set()
    last_violation_time = None
    latest_snapshot = None

    prev_time = time.time()
    last_snapshot_time = 0  # 記錄上次截圖時間
    last_saved_time = 0
    cap = cv2.VideoCapture(0)

    while True:
        success, frame = cap.read()
        if not success:
            print("⚠️ RTSP 讀取失敗，嘗試重連中...")
            cap.release()
            time.sleep(1)
            #cap.open("rtsp://admin:888888@192.168.12.172:8554/stream1")
            cap = cv2.VideoCapture(0)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)  # 顯示黑畫面防當機
            continue

        # 計算 FPS
        current_time = time.time()
        fps = 1.0 / (current_time - prev_time)
        prev_time = current_time

        #模型偵測
        results = model(frame)[0]

        #確保這一幀出現了「新的違規標籤」，才觸發儲存快照，就是一個空集合放標籤
        current_labels = set()

        for box in results.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # 根據訓練過的模型的類別名稱來設定 label
            label = results.names[cls]
            # 判斷類別，這裡改為符合實際情境的條件判斷，改為當初框圖的命名
            color = (0, 0, 255) if "違規" in label or "未穿布鞋" in label else (0, 255, 0)

            # 畫框與標籤
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # 違規邏輯
            #if "違規" in label or "未穿布鞋" in label:
            #只要標到就截圖
            if True:
                violation_count += 1
                last_violation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                current_labels.add(label)

                # 每 3 秒截圖一次
                if current_time - last_snapshot_time > 3:
                    last_snapshot_time = current_time
                    snapshot_name = f"violation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    snapshot_path = os.path.join("static/snapshots", snapshot_name)
                    cv2.imwrite(snapshot_path, frame)
                    latest_snapshot = snapshot_name

                # # 檢查是否出現新違規物件，且間隔超過3秒
                # if (current_labels - last_violation_labels) and (current_time - last_saved_time > 3):
                #     snapshot_name = f"violation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                #     snapshot_path = os.path.join("static/snapshots", snapshot_name)
                #     cv2.imwrite(snapshot_path, frame)
                #     latest_snapshot = snapshot_name
                #     last_saved_time = current_time
                #     last_violation_labels = current_labels.copy()  # ← 這一行很重要！
                #     print(f"已儲存快照：{snapshot_name}")

        # FPS 顯示
        cv2.putText(frame, f"FPS: {fps:.2f}", (10, frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # 畫中間線
        h, w = frame.shape[:2]
        #調整後面數字為橫線在螢幕比例位置
        line_y = int(h * 0.5)
        cv2.line(frame, (0, line_y), (w, line_y), (0, 255, 255), 2)

        # 顯示統計資料於鏡頭畫面
        cv2.putText(frame, f"In: {in_count}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, f"Out: {out_count}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        cv2.putText(frame, f"Violation: {violation_count}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        if last_violation_time:
            cv2.putText(frame, f"Violation Time: {last_violation_time}", (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # 傳送影像
        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


#entrance路由
#儲存截圖
@app.route('/latest_snapshot')
def latest_snapshot_route():
    global latest_snapshot
    if latest_snapshot:
        return send_from_directory('static/snapshots', latest_snapshot, as_attachment=True)
    else:
        return "No snapshot available", 404

#entrance路由
#將前端資料傳入後台變數中
@app.route('/stats_feed')
def stats_feed():
    return {
        "in_count": in_count,
        "out_count": out_count,
        "inside_count": in_count - out_count,
        "violation_count": violation_count,
        "violation_time": last_violation_time
    }

#entrance路由
#儲存按鈕路由
@app.route('/save_stats', methods=['POST'])
def save_stats():
    try:
        with db.cursor() as cursor:
            sql = """
                INSERT INTO entrance_stats (in_count, out_count, violation_count, violation_time)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (
                in_count,
                out_count,
                violation_count,
                last_violation_time
            ))
            db.commit()
        return "資料已成功儲存！"
    except Exception as e:
        print("儲存資料時發生錯誤：", str(e))
        return f"儲存資料失敗：{str(e)}", 500

##entrance_records路由，初始化頁面所需資訊
#門口辨識查詢資料
@app.route('/entrance_records')
#進入頁面前先登入驗證
def entrance_records():
    if not session.get("logged_in"):
        session['next'] = url_for('entrance_records')
        return redirect(url_for('login'))

    date_filter = request.args.get("date")

    try:
        with db.cursor() as cursor:
            if date_filter:
                sql = """
                SELECT id, in_count, out_count, violation_count, violation_time, saved_at
                FROM entrance_stats
                WHERE DATE(saved_at) = %s
                ORDER BY saved_at DESC
                """
                cursor.execute(sql, (date_filter,))
            else:
                cursor.execute("""
                SELECT id, in_count, out_count, violation_count, violation_time, saved_at
                FROM entrance_stats
                ORDER BY saved_at DESC
                """)
            rows = cursor.fetchall()

        formatted = [
            {
                "id": row[0],
                "in_count": row[1],
                "out_count": row[2],
                "violation_count": row[3],
                "violation_time": row[4],
                "saved_at": str(row[5])
            }
            for row in rows
        ]
        return render_template("entrance_records.html", records=formatted, date_filter=date_filter)
    except Exception as e:
        return f"查詢錯誤：{str(e)}"

#entrance_records路由
#門口辨識查詢資料
#下載CSV檔
@app.route('/download_entrance_csv')
def download_entrance_csv():
    if not session.get("logged_in"):
        return redirect(url_for('login'))

    date_filter = request.args.get("date")

    filename = f"{date_filter}_entrance.csv" if date_filter else "全部紀錄_entrance.csv"
    quoted_filename = urllib.parse.quote(filename)

    try:
        with db.cursor() as cursor:
            if date_filter:
                cursor.execute("""
                    SELECT id, in_count, out_count, violation_count, violation_time, saved_at
                    FROM entrance_stats
                    WHERE DATE(saved_at) = %s
                """, (date_filter,))
            else:
                cursor.execute(
                    "SELECT id, in_count, out_count, violation_count, violation_time, saved_at FROM entrance_stats")
            rows = cursor.fetchall()

        def generate():
            output = StringIO()
            writer = csv.writer(output)
            output.write('\ufeff')  # 加入 UTF-8 BOM，讓 Excel 正確顯示中文
            writer.writerow(["ID", "In Count", "Out Count", "Violation Count", "Violation Time", "Saved At"])
            for row in rows:
                writer.writerow(row)
            return output.getvalue()

        return Response(
            generate(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}"}
        )

    except Exception as e:
        return f"匯出錯誤：{str(e)}"

# 前往 Car.html 頁面，進行登入檢查
@app.route('/car')
def car():
    if not session.get("logged_in"):
        session['next'] = url_for('car')  # 儲存用戶想進入的頁面
        return redirect(url_for('login'))  # 重定向到登入頁面
    return render_template('Car.html')

# 前往 Car_records.html 頁面，進行登入檢查
@app.route('/car_records')
def car_records():
    if not session.get("logged_in"):
        session['next'] = url_for('car_records')  # 儲存用戶想進入的頁面
        return redirect(url_for('login'))  # 重定向到登入頁面
    return render_template('Car_records.html')

if __name__ == '__main__':
    app.run(debug=True)
