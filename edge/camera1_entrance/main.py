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
# =====================================================================

import cv2
from ultralytics import YOLO
import threading
import requests
import time

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

# サーバ送信先（別担当のサーバ /api/count 実装後に URL を設定）
SERVER_URL = "http://10.77.98.239:5000/api/count"
STORE_ID   = 1

# カメラ切断時の再接続設定
RECONNECT_WAIT     = 3    # 再接続を試みるまでの待機秒数
MAX_READ_FAILURES  = 30   # 連続で読み取り失敗したら「切断」と見なすフレーム数


# ===== サーバ送信 =====
def send_count(guest_count):
    """推定客数をサーバへ POST する。映像処理を止めないよう別スレッドで呼ぶ。
    サーバの /api/count 実装後に SERVER_URL を設定し、下のコメントを有効化する
    （仕様: docs/概要設計書.md 4 章、payload は {store_id, guest_count}）。"""
    payload = {"store_id": STORE_ID, "guest_count": guest_count}
    try:
        res = requests.post(SERVER_URL, json=payload, timeout=5)
        if res.status_code == 200:
            print(f"[送信] 店内人数={guest_count}人 → OK")
        else:
            print(f"[送信] サーバーエラー: {res.status_code}")
    except Exception as e:
        print(f"[送信] 失敗（ネットワークエラー）: {e}")


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

# ===== カメラ接続 =====
def open_camera(source):
    """カメラを開いて VideoCapture を返す。開けなければ解放して None を返す。
    起動時・再接続時の両方で使う。"""
    cap = cv2.VideoCapture(source)
    if cap.isOpened():
        return cap
    cap.release()
    return None


def connect_camera(source):
    """カメラが開けるまで RECONNECT_WAIT 秒間隔で無限にリトライする。
    起動時にカメラが未接続でも、繋がるまで待ち続ける。"""
    while True:
        cap = open_camera(source)
        if cap is not None:
            print("[カメラ] 接続しました")
            return cap
        print(f"[カメラ] 接続待ち… {RECONNECT_WAIT}秒後に再試行します")
        time.sleep(RECONNECT_WAIT)


def main():
    model = YOLO(MODEL_PATH)
    cap = connect_camera(CAMERA_SOURCE)

    people_status = {}   # obj_id ごとの判定ステータス（none / from_outside / from_inside / counted）
    enter_count = 0
    exit_count = 0
    last_sent_count = None   # 直近でサーバへ送った人数（変化を検出するため）

    band_left  = min(LINE_INSIDE, LINE_OUTSIDE)   # 2本の線で挟まれた帯の左端（X座標が小さい方）
    band_right = max(LINE_INSIDE, LINE_OUTSIDE)   # 帯の右端（X座標が大きい方）

    read_failures = 0        # 連続読み取り失敗数（切断検知用）
    running = True           # q キーで終了するためのフラグ

    while running:
        # --- フレーム取得（失敗が続いたら切断と見なして再接続）---
        ret, frame = (False, None)
        try:
            ret, frame = cap.read()
        except Exception as e:
            print(f"[カメラ] 読み取り例外: {e}")

        if not ret or frame is None:
            read_failures += 1
            if read_failures >= MAX_READ_FAILURES:
                print("[カメラ] 切断を検知しました。再接続します")
                cap.release()
                cap = connect_camera(CAMERA_SOURCE)
                read_failures = 0
            else:
                # 一時的なコマ落ち。少し待って次のフレームへ
                time.sleep(0.1)
            continue
        read_failures = 0   # 正常に取得できたらカウンタをリセット

        # --- フレーム処理（1フレームの例外で全体を止めない）---
        try:
            frame, enter_count, exit_count = process_frame(
                model, frame, people_status, enter_count, exit_count,
                band_left, band_right,
            )

            # 店内の推定客数
            current_inside = max(0, enter_count - exit_count)

            # 店内人数が変化したときだけサーバへ送信
            if current_inside != last_sent_count:
                threading.Thread(target=send_count, args=(current_inside,), daemon=True).start()
                last_sent_count = current_inside

            # 判定線（内側＝赤 / 外側＝青）と人数を描画
            cv2.line(frame, (LINE_INSIDE, 0), (LINE_INSIDE, frame.shape[0]), (0, 0, 255), 2)
            cv2.line(frame, (LINE_OUTSIDE, 0), (LINE_OUTSIDE, frame.shape[0]), (255, 0, 0), 2)
            cv2.putText(frame, f"Inside Shop: {current_inside} people", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(frame, f"(Enter: {enter_count}  Exit: {exit_count})", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cv2.imshow("Camera1 - Entrance Counter", frame)
        except Exception as e:
            print(f"[処理] フレーム処理中の例外（このフレームはスキップ）: {e}")

        if cv2.waitKey(1) == ord('q'):
            running = False

    cap.release()
    cv2.destroyAllWindows()


def process_frame(model, frame, people_status, enter_count, exit_count, band_left, band_right):
    """1フレームを解析し、入退店カウントを更新して描画済みフレームを返す。"""
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

    # 更新したカウントと描画済みフレームを呼び出し元へ返す
    return frame, enter_count, exit_count

if __name__ == "__main__":
    main()