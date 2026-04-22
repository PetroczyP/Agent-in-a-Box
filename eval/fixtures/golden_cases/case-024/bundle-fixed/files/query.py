"""Database query helpers for the product catalog."""

import sqlite3


def search_products(db_path: str, category: str, min_price: float) -> list[dict]:
    """Search products by category and minimum price."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT id, name, price, category FROM products"
        " WHERE category = ? AND price >= ?",
        (category, min_price),
    )
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_product_by_id(db_path: str, product_id: str) -> dict | None:
    """Fetch a single product by its ID."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
