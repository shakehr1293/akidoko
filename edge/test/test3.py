import cv2
from ultralytics import YOLO

model = YOLO('yolov5su.pt')
cap = cv2.VideoCapture(0) 

# 💡 トラッキングしない場合、歴史を覚える必要がないので
# people_status = {} は使いません（削除してOKです）

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # 画角のトリミング（真ん中1/4）
    #frame = frame[0:1080, 720:1200]

    # 💡 .track() ではなく、ただの検出（予測）を行う関数を使います
    results = model(frame, classes=[0], verbose=False)

    # 💡 今このコマ（フレーム）で見つかった人の数を直接数える
    boxes = results[0].boxes.xyxy.cpu().numpy()
    current_people_count = len(boxes) # 見つかった枠（box）の個数＝今の人数

    # 画面に検出された全員の枠を描画する
    for box in boxes:
        x1, y1, x2, y2 = box
        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

    # 画面に「今映っている人数」を表示
    cv2.putText(frame, f"People in Screen: {current_people_count}", (20, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)

    cv2.imshow("Shop Population Counter", frame)
    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()