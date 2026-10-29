import argparse
import asyncio
import time
from collections import Counter

import aiohttp

from db import connect
from settings import PRODUCT_ID


async def click(client, user_id, results):
    for attempt in range(6):
        try:
            async with client.post("/api/checkout", json={"user_id": user_id}) as res:
                status = (await res.json())["status"]
            if status != "TRY_AGAIN":
                results[status] += 1
                return
        except (aiohttp.ClientError, ValueError):
            pass
        results["retried"] += 1
        await asyncio.sleep(0.5 * 2**attempt)
    results["GAVE_UP"] += 1


async def buy(client, user_id, results):
    for _ in range(3):
        await click(client, user_id, results)


async def run(url, users, concurrency):
    results = Counter()
    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(url, connector=connector) as client:
        start = time.perf_counter()
        await asyncio.gather(*(buy(client, f"load-{i}", results) for i in range(users)))
        took = time.perf_counter() - start
        async with client.get("/api/sale") as res:
            stock_left = (await res.json())["stock_left"]

    print(f"{users * 3} requests from {users} users in {took:.1f}s ({users * 3 / took:.0f} req/s)")
    print("API replies:", dict(results))
    return stock_left


def order_count(db):
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders WHERE product_id = %s", (PRODUCT_ID,))
    count = cursor.fetchone()[0]
    db.commit()
    return count


def wait_for_workers(stock_left, timeout=60):
    db = connect()
    cursor = db.cursor()
    cursor.execute("SELECT total_stock FROM inventory WHERE product_id = %s", (PRODUCT_ID,))
    reserved = cursor.fetchone()[0] - stock_left
    for _ in range(timeout):
        if order_count(db) >= reserved:
            break
        time.sleep(1)
    db.close()


def check_db():
    db = connect()
    cursor = db.cursor()
    cursor.execute("SELECT total_stock, available_stock FROM inventory WHERE product_id = %s", (PRODUCT_ID,))
    total, available = cursor.fetchone()
    cursor.execute("SELECT COUNT(*), COUNT(DISTINCT user_id) FROM orders WHERE product_id = %s", (PRODUCT_ID,))
    orders, buyers = cursor.fetchone()
    db.close()

    print(f"MySQL: {orders} orders, {buyers} distinct buyers, {available}/{total} left")
    ok = orders == buyers == total - available and orders <= total
    print("PASS: no overselling" if ok else "FAIL: inventory and orders don't match")
    return ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=2000)
    parser.add_argument("--concurrency", type=int, default=500)
    args = parser.parse_args()

    stock_left = asyncio.run(run(args.url, args.users, args.concurrency))
    wait_for_workers(stock_left)
    raise SystemExit(0 if check_db() else 1)
