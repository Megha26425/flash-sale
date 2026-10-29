import sys

import redis

from db import connect
from settings import ORDERS_KEY, PRODUCT_ID, REDIS_URL, STOCK_KEY


def reset(units=500):
    db = connect()
    cursor = db.cursor()
    cursor.execute("DELETE FROM orders WHERE product_id = %s", (PRODUCT_ID,))
    cursor.execute(
        "UPDATE inventory SET total_stock = %s, available_stock = %s WHERE product_id = %s",
        (units, units, PRODUCT_ID),
    )
    db.commit()
    db.close()

    r = redis.from_url(REDIS_URL)
    r.delete(ORDERS_KEY)
    r.set(STOCK_KEY, units)


if __name__ == "__main__":
    units = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    reset(units)
    print(f"Sale reset to {units} units")
