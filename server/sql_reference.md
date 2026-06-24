# SQL利用一覧

## 客数登録

カメラから送信された客数を保存する。

```sql
INSERT INTO count_log(
    store_id,
    guest_count
)
VALUES (?, ?);
