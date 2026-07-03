# =====================================================================
# カメラ2（店内側）処理 ― ROIによる席単位判定【拡張予定】
#
# 【動作】
# ・起動時に最初の1フレームで席のROI（矩形領域）を複数選択する。
#   選択した順に seat_id = 0, 1, 2, … を割り当てる。
# ・各フレームで ROI ごとに YOLO の person 検出を行い、
#   人物が写っていれば「使用中」、いなければ「空席」と判定する。
# ・店員の通過などによる一瞬の誤判定を抑えるため、直近数フレームの
#   判定結果を多数決で確定する（設計 3.3）。
# ・確定した全席の状況を、状態変化時＋一定間隔ごとにサーバへ POST する。
#
# 【設置】店内を見下ろす固定カメラ用。ROI は席の位置に合わせて選択する。
#   ROI 切り出しの最小デモは edge/sample/sample_roi.py を参照。
# =====================================================================

import cv2
from ultralytics import YOLO
import threading
import requests
import json
import time
from collections import deque

# ===== 設定 =====
MODEL_PATH    = 'yolo26n.pt'    # YOLO モデル（初回実行時に自動ダウンロード）
CAMERA_SOURCE = 2              # USB カメラのデバイス番号
CONF          = 0.5           # person 検出の信頼度しきい値

# 多数決による安定化（設計 3.3）
VOTE_WINDOW   = 5             # 直近何フレーム分の判定を多数決に使うか

# サーバ送信設定（別担当のサーバ /api/seats 実装後に URL を設定）
SERVER_URL    = "http://10.77.98.239:5000/api/seats"
STORE_ID      = 1
POST_INTERVAL = 60           # 変化が無くても最低この秒数ごとに送る（鮮度維持。設計上は席状況15分で stale）

# カメラ切断時の再接続設定
RECONNECT_WAIT    = 3         # 再接続を試みるまでの待機秒数
MAX_READ_FAILURES = 30        # 連続で読み取り失敗したら「切断」と見なすフレーム数


# ===== サーバ送信 =====
def send_seats(seats):
    """全席の使用状況をサーバへ POST する。映像処理を止めないよう別スレッドで呼ぶ。
    サーバの /api/seats 実装後に SERVER_URL を設定する
    （仕様: docs/概要設計書.md 4 章、payload は {store_id, seats:[{seat_id, occupied}, ...]}）。"""
    payload = {"store_id": STORE_ID, "seats": seats}
    # 送信する JSON を複数行の整形形式で表示（ensure_ascii=False で日本語もそのまま）
    print("[送信] payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    try:
        res = requests.post(SERVER_URL, json=payload, timeout=5)
        if res.status_code == 200:
            occupied = sum(1 for s in seats if s["occupied"])
            print(f"[送信] {len(seats)}席中 使用中={occupied} → OK")
        else:
            print(f"[送信] サーバーエラー: {res.status_code}")
    except Exception as e:
        print(f"[送信] 失敗（ネットワークエラー）: {e}")


# ===== カメラ接続 =====
def open_camera(source):
    """カメラを開いて VideoCapture を返す。開けなければ解放して None を返す。"""
    cap = cv2.VideoCapture(source)
    if cap.isOpened():
        return cap
    cap.release()
    return None


def connect_camera(source):
    """カメラが開けるまで RECONNECT_WAIT 秒間隔で無限にリトライする。"""
    while True:
        cap = open_camera(source)
        if cap is not None:
            print("[カメラ] 接続しました")
            return cap
        print(f"[カメラ] 接続待ち… {RECONNECT_WAIT}秒後に再試行します")
        time.sleep(RECONNECT_WAIT)


def select_rois(cap):
    """最初のフレームで席の ROI を複数選択して返す。
    ドラッグで範囲確定→Enter/Space、全部終わったら Esc。"""
    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("フレーム取得に失敗しました")
    rois = cv2.selectROIs("select ROIs", frame)
    cv2.destroyWindow("select ROIs")
    if len(rois) == 0:
        raise RuntimeError("ROI が1つも選択されませんでした")
    return rois   # shape (N, 4) の numpy 配列 (x, y, w, h)


def main():
    model = YOLO(MODEL_PATH)
    cap = connect_camera(CAMERA_SOURCE)
    rois = select_rois(cap)

    # 席ごとに直近 VOTE_WINDOW フレーム分の生判定（True=人あり）を保持する
    history = [deque(maxlen=VOTE_WINDOW) for _ in rois]
    last_sent = None          # 直近でサーバへ送った確定状況（[bool, ...]）。変化検出用
    last_sent_time = 0.0      # 直近で送信した時刻（鮮度維持のための定期送信用）

    read_failures = 0         # 連続読み取り失敗数（切断検知用）
    running = True            # q キーで終了するためのフラグ

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
                time.sleep(0.1)
            continue
        read_failures = 0

        # --- フレーム処理（1フレームの例外で全体を止めない）---
        try:
            confirmed = []   # 席ごとの確定状況（True=使用中）
            for i, (x, y, w, h) in enumerate(rois):
                roi = frame[y:y + h, x:x + w]
                results = model(roi, classes=[0], conf=CONF, verbose=False)
                present = len(results[0].boxes) > 0

                # 直近フレームの多数決で「使用中/空席」を確定する
                history[i].append(present)
                occupied = sum(history[i]) * 2 > len(history[i])
                confirmed.append(occupied)

                color = (0, 0, 255) if occupied else (0, 255, 0)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, f"{i}:{'USED' if occupied else 'EMPTY'}",
                            (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # 状態が変化したとき、または一定時間ごとにサーバへ送信する
            now = time.time()
            if confirmed != last_sent or (now - last_sent_time) >= POST_INTERVAL:
                seats = [{"seat_id": i, "occupied": bool(occ)}
                         for i, occ in enumerate(confirmed)]
                threading.Thread(target=send_seats, args=(seats,), daemon=True).start()
                last_sent = confirmed
                last_sent_time = now

            cv2.imshow("Camera2 - Seat Occupancy", frame)
        except Exception as e:
            print(f"[処理] フレーム処理中の例外（このフレームはスキップ）: {e}")

        if cv2.waitKey(1) == ord('q'):
            running = False

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
