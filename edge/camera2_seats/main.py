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
import os
from collections import deque, Counter

# ===== 設定 =====
MODEL_PATH    = 'yolo26n.pt'    # YOLO モデル（初回実行時に自動ダウンロード）
CAMERA_SOURCE = 2              # USB カメラのデバイス番号
CONF          = 0.5           # person 検出の信頼度しきい値

# 多数決による安定化（設計 3.3）
VOTE_WINDOW   = 5             # 直近何フレーム分の判定を多数決に使うか

# サーバ送信設定（別担当のサーバ /api/seats 実装後に URL を設定）
SERVER_URL    = "http://10.77.99.164:3000/api/seats"
STORE_ID      = 1
POST_INTERVAL = 60           # 変化が無くても最低この秒数ごとに送る（鮮度維持。設計上は席状況15分で stale）
STABLE_DELAY  = 5            # 状態がこの秒数だけ変化しなかったら「確定」と見なして送信する（デバウンス）

# カメラ切断時の再接続設定
RECONNECT_WAIT    = 3         # 再接続を試みるまでの待機秒数
MAX_READ_FAILURES = 30        # 連続で読み取り失敗したら「切断」と見なすフレーム数

# ROI 設定ファイル（store_id ごとに保存し、次回以降は再選択せず読み込む）
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roi_config")


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


# ===== ROI 設定ファイルの読み書き =====
def roi_config_path(store_id):
    """store_id に対応する ROI 設定ファイルのパスを返す。"""
    return os.path.join(CONFIG_DIR, f"roi_store{store_id}.json")


def load_rois(store_id):
    """保存済みの ROI を読み込む。無ければ None を返す。
    返り値は [(x, y, w, h), ...] のリスト（全て int）。"""
    path = roi_config_path(store_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rois = [tuple(int(v) for v in roi) for roi in data["rois"]]
        if len(rois) == 0:
            return None
        print(f"[ROI] 設定ファイルを読み込みました（{len(rois)}席）: {path}")
        return rois
    except Exception as e:
        print(f"[ROI] 設定ファイルの読み込みに失敗しました（選択し直します）: {e}")
        return None


def save_rois(store_id, rois):
    """選択した ROI を store_id ごとの設定ファイルに保存する。"""
    path = roi_config_path(store_id)
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {"store_id": store_id,
                "rois": [[int(x), int(y), int(w), int(h)] for (x, y, w, h) in rois]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[ROI] 設定ファイルを保存しました（{len(rois)}席）: {path}")
    except Exception as e:
        print(f"[ROI] 設定ファイルの保存に失敗しました: {e}")


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


def get_rois(cap, store_id):
    """ROI を用意する。設定ファイルがあれば読み込み、無ければ選択して保存する。
    これにより範囲設定は store_id ごとに初回のみで済む。"""
    rois = load_rois(store_id)
    if rois is not None:
        return rois
    rois = select_rois(cap)
    save_rois(store_id, rois)
    return rois


def main():
    model = YOLO(MODEL_PATH)
    cap = connect_camera(CAMERA_SOURCE)
    rois = get_rois(cap, STORE_ID)

    # 席ごとに直近 VOTE_WINDOW フレーム分の生の検出人数を保持する
    history = [deque(maxlen=VOTE_WINDOW) for _ in rois]
    last_sent = None          # 直近でサーバへ送った確定状況。変化検出用
    last_sent_time = 0.0      # 直近で送信した時刻（鮮度維持のための定期送信用）
    prev_confirmed = None     # 前フレームの確定状況（変化検知＝デバウンス用）
    last_change_time = 0.0    # 状態が最後に変化した時刻（この時刻から STABLE_DELAY 秒静止で送信）

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
            confirmed = []   # 席ごとの確定状況 (occupied, count) のリスト
            for i, (x, y, w, h) in enumerate(rois):
                roi = frame[y:y + h, x:x + w]
                results = model(roi, classes=[0], conf=CONF, verbose=False)
                count_now = len(results[0].boxes)   # このフレームで ROI 内に映った人数

                # 直近フレームの最頻値で人数を確定し、瞬間的な誤検出を抑える
                history[i].append(count_now)
                count = Counter(history[i]).most_common(1)[0][0]
                occupied = count > 0
                confirmed.append((occupied, count))

                color = (0, 0, 255) if occupied else (0, 255, 0)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                label = f"{i}:{'USED' if occupied else 'EMPTY'}({count})"
                cv2.putText(frame, label,
                            (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # 使用中/空席（occupied）が変化したらタイマーをリセットし、STABLE_DELAY 秒
            # 静止したら送信する。人数(seat_count)の増減ではタイマーをリセットしない。
            # これにより人の出入りの途中では送らず、落ち着いた状態だけを送る（デバウンス）。
            occ_state = [occ for (occ, _) in confirmed]
            now = time.time()
            if occ_state != prev_confirmed:
                last_change_time = now
                prev_confirmed = occ_state

            stable_enough = (now - last_change_time) >= STABLE_DELAY
            changed_since_sent = occ_state != last_sent
            interval_elapsed = (now - last_sent_time) >= POST_INTERVAL
            if stable_enough and (changed_since_sent or interval_elapsed):
                seats = [{"seat_id": i, "occupied": bool(occ), "seat_count": int(cnt)}
                         for i, (occ, cnt) in enumerate(confirmed)]
                threading.Thread(target=send_seats, args=(seats,), daemon=True).start()
                last_sent = occ_state
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
