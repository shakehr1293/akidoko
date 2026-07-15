PRAGMA foreign_keys = ON;

-- ==========================================
-- 店舗情報テーブル
-- ==========================================

CREATE TABLE IF NOT EXISTS store (

    -- 店舗ID
    store_id INTEGER PRIMARY KEY,

    -- 店舗名
    store_name TEXT NOT NULL,

    -- 総席数
    total_seats INTEGER NOT NULL

);

-- ==========================================
-- 客数ログテーブル
-- ==========================================

CREATE TABLE IF NOT EXISTS count_log (

    -- ログID
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 店舗ID
    store_id INTEGER NOT NULL,

    -- 推定客数
    guest_count INTEGER NOT NULL,

    -- 記録時刻
    recorded_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (store_id)
        REFERENCES store(store_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE

);

CREATE INDEX IF NOT EXISTS idx_count_log_store_time
ON count_log (
    store_id,
    recorded_at DESC
);

-- ==========================================
-- 残席ログテーブル
-- ==========================================

CREATE TABLE IF NOT EXISTS seat_log (

    -- ログID
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 店舗ID
    store_id INTEGER NOT NULL,

    -- 残席数
    remaining_seats INTEGER NOT NULL,

    -- 記録時刻
    recorded_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (store_id)
        REFERENCES store(store_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE

);

CREATE INDEX IF NOT EXISTS idx_seat_log_store_time
ON seat_log (
    store_id,
    recorded_at DESC
);

-- ==========================================
-- 席状態テーブル
-- ==========================================

CREATE TABLE IF NOT EXISTS seat_status (

    -- 席ID
    seat_id INTEGER PRIMARY KEY,

    -- 店舗ID
    store_id INTEGER NOT NULL,

    -- 使用中
    occupied INTEGER NOT NULL,

    -- 着席人数（将来拡張）
    seat_count INTEGER NOT NULL DEFAULT 0,

    -- 更新時刻
    updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (store_id)
        REFERENCES store(store_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE

);

CREATE INDEX IF NOT EXISTS idx_seat_status_store
ON seat_status(store_id);

-- ==========================================
-- 初期データ
-- ==========================================

INSERT OR IGNORE INTO store (
    store_id,
    store_name,
    total_seats
)
VALUES (
    1,
    'テスト店舗',
    12
);

-- seat_id の割り当て
-- 0 : カウンター席（4人）
-- 1 : テーブル席1（4人）
-- 2 : テーブル席2（4人）

INSERT OR IGNORE INTO seat_status
(seat_id, store_id, occupied, seat_count)
VALUES
(0,1,0,0),
(1,1,0,0),
(2,1,0,0);


-- 初期残席数

INSERT OR IGNORE INTO seat_log (
    log_id,
    store_id,
    remaining_seats
)
VALUES (
    1,
    1,
    12
);