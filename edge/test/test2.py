import cv2
from ultralytics import YOLO

model = YOLO('yolov5su.pt')
cap = cv2.VideoCapture(0) 

# 💡 線の位置の数値はそのまま維持
LINE_OUTSIDE = 200  # 上側の線（青）
LINE_INSIDE  = 500  # 下側の線（赤）

# 各人のステータスを記憶する辞書
people_status = {}

enter_count = 0
exit_count = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break


    frame = frame[0:1080, 0:1800]

    # トリミングした後のフレームに対して人だけを追跡
    results = model.track(frame, persist=True, classes=[0], verbose=False)

    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.cpu().numpy().astype(int)

        for box, obj_id in zip(boxes, ids):
            x1, y1, x2, y2 = box
            current_y = int((y1 + y2) / 2) # 人の中心（Y座標）

            if obj_id not in people_status:
                people_status[obj_id] = "none"

            # --- 🏃‍♂️ ① 上から下への「入店」ルート (外[青] -> 店内[赤]) ---
            if people_status[obj_id] == "none" and LINE_OUTSIDE < current_y < LINE_INSIDE:
                if current_y < (LINE_OUTSIDE + 50):
                    people_status[obj_id] = "passed_outside"

            if people_status[obj_id] == "passed_outside" and current_y > LINE_INSIDE:
                enter_count += 1
                people_status[obj_id] = "counted"


            # --- 🏃‍♂️ ② 下から上への「退店」ルート (店内[赤] -> 外[青]) ---
            if people_status[obj_id] == "none" and LINE_OUTSIDE < current_y < LINE_INSIDE:
                if current_y > (LINE_INSIDE - 50):
                    people_status[obj_id] = "passed_inside"

            if people_status[obj_id] == "passed_inside" and current_y < LINE_OUTSIDE:
                exit_count += 1
                people_status[obj_id] = "counted"


            # 💡 安全装置：画面の上下ギリギリに消え去ったらステータスをリセット
            if current_y < 40 or current_y > (frame.shape[0] - 40):
                people_status[obj_id] = "none"

            # 画面に枠を描画
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

    # 現在の店内の人数を計算
    current_inside_shop = max(0, enter_count - exit_count)

    # 画面に2本のラインを描画（外側：青、内側：赤）
    cv2.line(frame, (0, LINE_OUTSIDE), (frame.shape[1], LINE_OUTSIDE), (255, 0, 0), 2)
    cv2.line(frame, (0, LINE_INSIDE), (frame.shape[1], LINE_INSIDE), (0, 0, 255), 2)
    
    # 画面上に「現在の店内の人数」を大きく表示
    cv2.putText(frame, f"Inside Shop: {current_inside_shop} people", (20, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
    
    # 内訳（入・退数）も表示
    cv2.putText(frame, f"(Enter: {enter_count}  Exit: {exit_count})", (20, 95), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.imshow("Shop Population Counter", frame)
    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()