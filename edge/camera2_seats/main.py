import cv2
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
cap = cv2.VideoCapture(4)

if not cap.isOpened():
    raise RuntimeError("カメラを開けませんでした")
# 最初の1フレームでROIを選ぶ

ret, frame = cap.read()
if not ret:
    raise RuntimeError("フレーム取得に失敗しました")
# 複数選択: ドラッグで範囲確定→Enter/Space、全部終わったらEsc
rois = cv2.selectROIs("select ROIs", frame)
cv2.destroyWindow("select ROIs")
# rois は shape (N, 4) の numpy 配列 (x, y, w, h)
CONF = 0.5
while True:
    ret, frame = cap.read()
    if not ret:
        break
    for i, (x, y, w, h) in enumerate(rois):
        roi = frame[y:y+h, x:x+w]
        results = model(roi, classes=[0], conf=CONF, verbose=False)
        present = len(results[0].boxes) > 0
        color = (0, 0, 255) if present else (0, 255, 0)
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(frame, f"{i}:{'PERSON' if present else 'EMPTY'}",
                    (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.imshow("multi ROI", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()
