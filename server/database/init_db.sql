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
 
-- ==========================================

-- 検索高速化インデックス

-- ==========================================

CREATE INDEX IF NOT EXISTS idx_count_log_store_time

ON count_log (

    store_id,

    recorded_at DESC

);
 
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

    25

);
 