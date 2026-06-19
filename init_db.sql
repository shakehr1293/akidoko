--------------------------------------------------
-- 飲食店空き席数管理システム
-- SQLite 初期化SQL
--------------------------------------------------

PRAGMA foreign_keys = ON;

--------------------------------------------------
-- 店舗情報テーブル
-- 固定情報を管理
--------------------------------------------------
CREATE TABLE store (

    -- 店舗ID
    store_id INTEGER PRIMARY KEY,

    -- 店舗名
    store_name TEXT NOT NULL,

    -- 総席数
    total_seats INTEGER NOT NULL
);

--------------------------------------------------
-- 客数ログテーブル
-- カメラから送信される客数履歴を管理
--------------------------------------------------
CREATE TABLE count_log (

    -- ログID
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 店舗ID
    store_id INTEGER NOT NULL,

    -- 推定客数
    guest_count INTEGER NOT NULL,

    -- 記録時刻
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(store_id)
        REFERENCES store(store_id)
);

--------------------------------------------------
-- 最新データ検索
--------------------------------------------------
CREATE INDEX idx_count_log_store_time
ON count_log(
    store_id,
    recorded_at DESC
);

--------------------------------------------------
-- 初期データ
--------------------------------------------------
INSERT INTO store (
    store_id,
    store_name,
    total_seats
)
VALUES (
    1,
    'テスト店舗',
    25
);