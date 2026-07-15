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

    # 店舗情報
    cursor.execute("""
        SELECT
            store_name
        FROM store
        WHERE store_id = ?
    """, (store_id,))

    store = cursor.fetchone()

    if store is None:
        conn.close()
        return jsonify({"error": "店舗が存在しません"}), 404

    # カウンター席
    cursor.execute("""
    SELECT
        occupied,
        seat_count
    FROM seat_status
    WHERE
        store_id = ?
    AND
        seat_id = 0
    """, (store_id,))

    counter = cursor.fetchone()

    counter_total = 4

    if counter:
        counter_vacant = 4 - counter["seat_count"]
    else:
        counter_vacant = 4

    # テーブル席
    cursor.execute("""
    SELECT
        occupied
    FROM seat_status
    WHERE
        store_id = ?
    AND
        seat_id IN (1,2)
    ORDER BY seat_id
    """, (store_id,))

    tables = cursor.fetchall()

    table_total = 2
    table_vacant = 0

    for table in tables:
        if table["occupied"] == 0:
            table_vacant += 1

    # 最新の残席数
    cursor.execute("""
        SELECT
            remaining_seats,
            recorded_at
        FROM seat_log
        WHERE
            store_id = ?
        ORDER BY
            recorded_at DESC
        LIMIT 1
    """, (store_id,))

    seat_log = cursor.fetchone()

    conn.close()

    if seat_log is None:
        remaining_seats = 0
        updated_at = None
        is_stale = True
    else:
        remaining_seats = seat_log["remaining_seats"]
        updated_at = seat_log["recorded_at"]
        is_stale = False

    return jsonify({

        "store_id": store_id,

        "counter_vacant": counter_vacant,
        "counter_total": counter_total,

        "table_vacant": table_vacant,
        "table_total": table_total,

        "remaining_seats": remaining_seats,

        "updated_at": updated_at,

        "is_stale": is_stale

    })

# カメラ2
@app.route("/api/seats", methods=["POST"])
def save_seats():

    data = request.get_json()

    if not data:
        return jsonify({"error": "JSONデータがありません"}), 400

    if "store_id" not in data or "seats" not in data:
        return jsonify({"error": "store_id と seats が必要です"}), 400

    store_id = data["store_id"]
    seats = data["seats"]

    conn = get_connection()
    cursor = conn.cursor()

    # 各席の状態を更新
    for seat in seats:

        cursor.execute("""
            INSERT INTO seat_status
            (
                seat_id,
                store_id,
                occupied,
                seat_count,
                updated_at
            )
            VALUES
            (
                ?, ?, ?, ?, CURRENT_TIMESTAMP
            )

            ON CONFLICT(seat_id)
            DO UPDATE SET
                occupied = excluded.occupied,
                seat_count = excluded.seat_count,
                updated_at = CURRENT_TIMESTAMP
        """,
        (
            seat["seat_id"],
            store_id,
            int(seat["occupied"]),
            seat["seat_count"]
        ))

    # 空席数を計算
    # 残席数を計算
    cursor.execute("""
        SELECT
            seat_id,
            occupied,
            seat_count
        FROM seat_status
        WHERE store_id = ?
    """, (store_id,))

    rows = cursor.fetchall()

    remaining_seats = 0

    for row in rows:

        # seat_id=0：カウンター席（4席）
        if row["seat_id"] == 0:
            remaining_seats += max(0, 4 - row["seat_count"])

        # seat_id=1,2：4人テーブル
        else:
            if row["occupied"] == 0:
                remaining_seats += 4

    # seat_logへ保存
    cursor.execute("""
        INSERT INTO seat_log
        (
            store_id,
            remaining_seats
        )
        VALUES(?, ?)""",
    (
        store_id,
        remaining_seats
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "席情報を保存しました",
        "remaining_seats": remaining_seats
    }) 
 
if __name__ == "__main__":
    print(app.url_map)
    app.run(
        host="0.0.0.0",
        port=3000,
        debug=True
    )