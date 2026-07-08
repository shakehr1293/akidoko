from flask import Flask, jsonify, request
import sqlite3
from pathlib import Path
from flask_cors import CORS
 
app = Flask(__name__)
CORS(app)
app.json.ensure_ascii = False

# データベースのパス
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "database" / "restaurant.db"
 
 
# DB接続
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
 
 
# 動作確認
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Restaurant Seat System"
    })
 
 
# 客数を受信して保存
@app.route("/api/count", methods=["POST"])
def save_count():

    data = request.get_json()

    if not data:
        return jsonify({"error": "JSONデータがありません"}), 400

    if "store_id" not in data or "guest_count" not in data:
        return jsonify({"error": "store_id と guest_count が必要です"}), 400

    store_id = data["store_id"]
    guest_count = data["guest_count"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO count_log (
            store_id,
            guest_count
        )
        VALUES (?, ?)
    """, (store_id, guest_count))

    conn.commit()

    cursor.execute("""
        SELECT total_seats
        FROM store
        WHERE store_id = ?
    """, (store_id,))

    store_info = cursor.fetchone()

    conn.close()

    if store_info is None:
        return jsonify({"error": "店舗が存在しません"}), 404

    remaining_seats = store_info["total_seats"] - guest_count

    return jsonify({
        "message": "保存しました",
        "store_id": store_id,
        "remaining_seats": remaining_seats
    })
 
 
# 最新情報取得
@app.route("/api/status", methods=["GET"])
def status():

    store_id = request.args.get("store_id", default=1, type=int)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            s.store_name,
            sl.remaining_seats,
            sl.recorded_at
        FROM store s
        LEFT JOIN seat_log sl
            ON s.store_id = sl.store_id
        WHERE s.store_id = ?
        ORDER BY sl.recorded_at DESC
        LIMIT 1
    """, (store_id,))

    status_info = cursor.fetchone()

    conn.close()

    if status_info is None:
        return jsonify({"error": "店舗が存在しません"}), 404

    if status_info["remaining_seats"] is None:
        remaining_seats = 0
        updated_at = None
        is_stale = True
    else:
        remaining_seats = status_info["remaining_seats"]
        updated_at = status_info["recorded_at"]
        is_stale = False

    return jsonify({
        "store_id": store_id,
        "store_name": status_info["store_name"],
        "remaining_seats": remaining_seats,
        "updated_at": updated_at,
        "is_stale": is_stale
    })

#　カメラ2
@app.route("/api/seats", methods=["POST"])
def save_seats():

    data = request.get_json()

    if not data:
        return jsonify({"error": "JSONデータがありません"}), 400

    if "store_id" not in data or "seats" not in data:
        return jsonify({
            "error": "store_id と seats が必要です"
        }), 400

    store_id = data["store_id"]
    seats = data["seats"]

    # 使用中の席数
    occupied_count = sum(
        1 for seat in seats
        if seat.get("occupied", False)
    )

    # 空席数
    remaining_seats = len(seats) - occupied_count

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO seat_log
        (
            store_id,
            remaining_seats
        )
        VALUES (?, ?)
    """, (
        store_id,
        remaining_seats
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "席情報を保存しました",
        "store_id": store_id,
        "remaining_seats": remaining_seats
    })
 
 
if __name__ == "__main__":
    print(app.url_map)
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
    
