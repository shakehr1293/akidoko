import cv2
from ultralytics import YOLO
import time
import threading
import requests

model = YOLO('yolo26n.pt')
cap = cv2.VideoCapture(0)

LINE_INSIDE = 100
LINE_OUTSIDE = 500

people_status = {}
enter_count = 0
exit_count = 0
# =====================================================================
#  裏で動かすPOST送信関数を定義
# =====================================================================

def send_post_request():
    url = "https://honyahonya/api/count"
    payload ={


    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"[Thread]送信成功: {}(店内:{}人))")
        else:
            print(f"[Thread]サーバーエラー； {response.status_code}")
    except Exception as e:
        print(f"[Thread] 送信失敗 (ネットワークエラー):{e}")
# =====================================================================
while cap.isOpened():
    ret, frame = cap.read
    if not ret:
        break

    results = model.track(frame, perasist=True, classes=[0],verbose=False)

    if


cap.release()
cv2.destroyAllWindows()