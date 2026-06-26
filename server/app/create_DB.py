import sqlite3
from pathlib import Path
 
BASE_DIR = Path(__file__).resolve().parent
SQL_FILE = BASE_DIR.parent / "database" / "init_db.sql"
DB_FILE = BASE_DIR.parent / "database" / "restaurant.db"
 
print("SQLファイル:", SQL_FILE)
print("存在:", SQL_FILE.exists())
 
with sqlite3.connect(DB_FILE) as conn:
    with open(SQL_FILE, "r", encoding="utf-8") as f:
        sql = f.read()
 
    print("===== SQL内容 =====")
    print(sql)
 
    conn.executescript(sql)
    conn.commit()
 
print("完了")