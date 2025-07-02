import cv2

# 攝影機網址（改成你的帳密）
cap = cv2.VideoCapture("rtsp://admin:888888@192.168.12.172:554/stream1")

if not cap.isOpened():
    print("❌ 無法連接攝影機")
else:
    print("✅ 攝影機連接成功")
