# =====================================================================
# カメラ1（出入口）処理 ― 入退店カウント【最小構成】
#
# 【動作】
# ・YOLO で person を検出・追跡し、画面に引いた 2 本の判定線
#   （外側＝出入口側 / 内側＝店内側）の通過順で入店・退店を判定する。
# ・外側 → 内側 の順に通過：入店（enter +1）
# ・内側 → 外側 の順に通過：退店（exit  +1）
# ・「入店数 − 退店数」を店内の推定客数とする（負にはしない）。
#
# 【設置】横向き設置カメラ用（人が画面を左右に横切る＝X 座標で判定）。
#   真上・見下ろし設置の場合は edge/sample/test2.py を参照し、
#   判定座標を中心 Y に、判定線を水平線に置き換える。
#1y
# =====================================================================

import cv2
from ultralytics import YOLO

# ===== 設定 =====
MODEL_PATH    = 'yolo26n.pt'    # YOLO モデル（初回実行時に自動ダウンロード）
CAMERA_SOURCE = 2               # USB カメラのデバイス番号

# 映像の前処理（現場の通路に合わせて調整する）
TRIM_TOP    = 0         # 上から何割カットするか（0 = カットしない）
TRIM_BOTTOM = 0         # 下から何割カットするか（0 = カットしない）
RESIZE_WIDTH = 640      # YOLOに渡す前の横幅。線の座標(LINE_*)はこの幅が基準

LINE_INSIDE   = 100     # 内側＝店内側の線（X座標。0〜RESIZE_WIDTH の範囲）
LINE_OUTSIDE  = 500     # 外側＝出入口側の線（X座標。0〜RESIZE_WIDTH の範囲）
NEAR_MARGIN   = 40      # 「どちらの線の近くから入ってきたか」を判定する余裕幅
EDGE_MARGIN   = 40      # 画面端でステータスをリセットする余裕幅

model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(CAMERA_SOURCE)

people_status = {}   # obj_id ごとの判定ステータス（none / from_outside / from_inside / counted）
enter_count = 0
exit_count = 0


# ===== 判定ヘルパー =====
def is_beyond(pos, line, other_line):
    """人の位置 pos が line を越えて、other_line と反対側まで出ているか判定する。
    カメラの設置向きで線の左右の並びが変わっても正しく動くよう、
    2 本の線の位置関係から「越えた」と見なす向きを決める。"""
    if line > other_line:
        # line が other_line より右にある → さらに右へ出たら「越えた」
        return pos > line
    else:
        # line が other_line より左にある → さらに左へ出たら「越えた」
        return pos < line

# 線から客が近いかどうかを判定
def is_near(pos, line):
    return abs(pos - line) <= NEAR_MARGIN


band_left  = min(LINE_INSIDE, LINE_OUTSIDE)   # 2本の線で挟まれた帯の左端（X座標が小さい方）
band_right = max(LINE_INSIDE, LINE_OUTSIDE)   # 帯の右端（X座標が大きい方）

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # 上下の不要部分をカットして真ん中の通路だけに絞り、横 RESIZE_WIDTH に縮小（sample/test.py 由来）
    h, w, _ = frame.shape
    frame = frame[int(h * TRIM_TOP):int(h * (1 - TRIM_BOTTOM)), 0:w]
    frame = cv2.resize(frame, (RESIZE_WIDTH, int(RESIZE_WIDTH * (frame.shape[0] / frame.shape[1]))))

    # 人（class=0）だけを追跡（固定カメラなので動き補正なしの bytetrack を使用）
    results = model.track(frame, persist=True, classes=[0], verbose=False,
                          tracker="bytetrack.yaml")

    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.cpu().numpy().astype(int)

        for box, obj_id in zip(boxes, ids):
            x1, y1, x2, y2 = box
            cx = int((x1 + x2) / 2)   # 人の中心 X 座標

            status = people_status.setdefault(obj_id, "none")

            # ① 2 本の線の間に入った瞬間、どちらの線の近くから来たかで方向を仮確定
            if status == "none" and band_left < cx < band_right:
                if is_near(cx, LINE_OUTSIDE):
                    people_status[obj_id] = "from_outside"   # 外側から進入 → 入店候補
                elif is_near(cx, LINE_INSIDE):
                    people_status[obj_id] = "from_inside"    # 内側から進入 → 退店候補

            # ② 反対側の線を越えたらカウント確定
            elif status == "from_outside" and is_beyond(cx, LINE_INSIDE, LINE_OUTSIDE):
                enter_count += 1
                people_status[obj_id] = "counted"
            elif status == "from_inside" and is_beyond(cx, LINE_OUTSIDE, LINE_INSIDE):
                exit_count += 1
                people_status[obj_id] = "counted"

            # 安全装置：画面端まで消えたらステータスをリセット（再進入に備える）
            if cx < EDGE_MARGIN or cx > frame.shape[1] - EDGE_MARGIN:
                people_status[obj_id] = "none"

            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

    # 店内の推定客数
    current_inside = max(0, enter_count - exit_count)

    # 判定線（内側＝赤 / 外側＝青）と人数を描画
    cv2.line(frame, (LINE_INSIDE, 0), (LINE_INSIDE, frame.shape[0]), (0, 0, 255), 2)
    cv2.line(frame, (LINE_OUTSIDE, 0), (LINE_OUTSIDE, frame.shape[0]), (255, 0, 0), 2)
    cv2.putText(frame, f"Inside Shop: {current_inside} people", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.putText(frame, f"(Enter: {enter_count}  Exit: {exit_count})", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    cv2.imshow("Camera1 - Entrance Counter", frame)

    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()