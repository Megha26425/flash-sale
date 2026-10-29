import mysql.connector
from mysql.connector import errorcode

from settings import DB, PRODUCT_ID


def connect():
    return mysql.connector.connect(**DB, autocommit=False)


def create_order(conn, user_id):
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM orders WHERE product_id = %s AND user_id = %s",
            (PRODUCT_ID, user_id),
        )
        if cursor.fetchone():
            conn.rollback()
            return "CONFIRMED"

        cursor.execute(
            "UPDATE inventory SET available_stock = available_stock - 1 "
            "WHERE product_id = %s AND available_stock > 0",
            (PRODUCT_ID,),
        )
        if cursor.rowcount == 0:
            conn.rollback()
            return "FAILED"

        cursor.execute(
            "INSERT INTO orders (product_id, user_id) VALUES (%s, %s)",
            (PRODUCT_ID, user_id),
        )
        conn.commit()
        return "CONFIRMED"
    except mysql.connector.IntegrityError as e:
        conn.rollback()
        if e.errno == errorcode.ER_DUP_ENTRY:
            return "CONFIRMED"
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def available_stock(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT available_stock FROM inventory WHERE product_id = %s", (PRODUCT_ID,))
    row = cursor.fetchone()
    cursor.close()
    conn.commit()
    return row[0] if row else 0
