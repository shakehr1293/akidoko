from flask import Flask, jsonify, request
import sqlite3
from pathlib import Path
 
app = Flask(__name__)
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
            s.total_seats,
            c.guest_count,
            c.recorded_at
        FROM store s
        LEFT JOIN count_log c
            ON s.store_id = c.store_id
        WHERE s.store_id = ?
        ORDER BY c.recorded_at DESC
        LIMIT 1
    """, (store_id,))

    status_info = cursor.fetchone()

    conn.close()

    if status_info is None:
        return jsonify({"error": "店舗が存在しません"}), 404

    guest_count = (
        status_info["guest_count"]
        if status_info["guest_count"] is not None
        else 0
    )

    remaining_seats = status_info["total_seats"] - guest_count

    updated_at = status_info["recorded_at"]

    return jsonify({
        "store_id": store_id,
        "store_name": status_info["store_name"],
        "remaining_seats": remaining_seats,
        "updated_at": updated_at,
        "is_stale": False
    })
 
 
if __name__ == "__main__":
    print(app.url_map)
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
    
