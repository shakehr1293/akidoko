# =====================================================================
# 出入口カメラのテストコード（横向き設置カメラ用）
# 
# 【特徴】
# ・人が画面を左右に横切る動きで「入店 / 退店」を判定
# =====================================================================

import cv2
from ultralytics import YOLO

model = YOLO('yolov5su.pt')
cap = cv2.VideoCapture(0) # 撮影した動画のパス

LINE_INSIDE  = 300  # 左側の線（赤）
LINE_OUTSIDE = 400  # 右側の線（青）

# 各人のステータスを記憶する辞書
people_status = {}

enter_count = 0
exit_count = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # 上下の不要な部分をカットし、真ん中の通路だけに絞るトリミング
    h, w, _ = frame.shape
    frame = frame[int(h*0.2):int(h*0.8), 0:w] 
    
    # YOLOに渡すために画面サイズを少し扱いやすく調整（横640サイズに縮小）
    frame = cv2.resize(frame, (640, int(640 * (frame.shape[0]/frame.shape[1]))))

    # 人だけを追跡
    results = model.track(frame, persist=True, classes=[0], verbose=False)

    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.cpu().numpy().astype(int)

        for box, obj_id in zip(boxes, ids):
            x1, y1, x2, y2 = box
            current_x = int((x1 + x2) / 2) # 人の中心を「X座標（左右）」にする

            if obj_id not in people_status:
                people_status[obj_id] = "none"

            # 💡【解決策】エリアで分けるのではなく、線をまたいだ瞬間をストレートに捉えます！

            # --- 🏃‍♂️ ① 左から右への「入店」ルート ---
            # 1. 最初(none)の状態で、左の赤線(300)を右向きに越えたら「入店準備中」
            if people_status[obj_id] == "none" and current_x > LINE_INSIDE and current_x < LINE_OUTSIDE:
                # 左側（赤線の近く）から入ってきた場合のみ入店準備中にする
                if current_x < (LINE_INSIDE + 40):
                    people_status[obj_id] = "passed_inside"
                    
            # 2. 「入店準備中」の人が、さらに右の青線(400)を越えたら入店確定！
            if people_status[obj_id] == "passed_inside" and current_x > LINE_OUTSIDE:
                enter_count += 1
                people_status[obj_id] = "counted"


            # --- 🏃‍♂️ ② 右から左への「退店」ルート ---
            # 1. 最初(none)の状態で、右の青線(400)を左向きに越えたら「退店準備中」
            if people_status[obj_id] == "none" and current_x < LINE_OUTSIDE and current_x > LINE_INSIDE:
                # 右側（青線の近く）から入ってきた場合のみ退店準備中にする
                if current_x > (LINE_OUTSIDE - 40):
                    people_status[obj_id] = "passed_outside"
                    
            # 2. 「退店準備中」の人が、さらに左の赤線(300)を越えたら退店確定！
            if people_status[obj_id] == "passed_outside" and current_x < LINE_INSIDE:
                exit_count += 1
                people_status[obj_id] = "counted"


            # 💡 安全装置：完全に画面端に消えたらステータスをリセットする
            if current_x < 40 or current_x > 600:
                people_status[obj_id] = "none"

            # 画面に枠を描画
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

    # 現在の店内の人数を計算
    current_inside_shop = max(0, enter_count - exit_count)

    # 画面に2本の「縦ライン」を描画（左側：赤、右側：青）
    cv2.line(frame, (LINE_INSIDE, 0), (LINE_INSIDE, frame.shape[0]), (0, 0, 255), 2)
    cv2.line(frame, (LINE_OUTSIDE, 0), (LINE_OUTSIDE, frame.shape[0]), (255, 0, 0), 2)
    
    # 画面上に入客数などを表示
    cv2.putText(frame, f"Inside Shop: {current_inside_shop} people", (20, 40), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.putText(frame, f"(Enter: {enter_count}  Exit: {exit_count})", (20, 70), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    cv2.imshow("Shop Population Counter", frame)
    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()