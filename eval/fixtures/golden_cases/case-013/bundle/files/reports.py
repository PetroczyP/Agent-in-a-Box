import sqlite3

DB_PATH = "analytics.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def generate_report(department_ids: list[int]) -> list[dict]:
    db = get_db()
    report = []
    for dept_id in department_ids:
        cursor = db.execute(
            "SELECT SUM(amount) as total FROM expenses WHERE dept_id = ?",
            (dept_id,),
        )
        row = cursor.fetchone()
        report.append({"dept_id": dept_id, "total": row["total"]})
    db.close()
    return report
