"""Needs Redis and MySQL running (docker compose up redis mysql). Wipes the sale data."""
import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from db import available_stock, connect, create_order
from reset_sale import reset
from stock import Stock, redis_client


@pytest.fixture(autouse=True)
def fresh_sale():
    reset(500)


def run(coro):
    return asyncio.run(coro)


async def crowd(users, clicks_each):
    r = redis_client()
    stock = Stock(r)
    calls = [stock.reserve(f"user-{u}") for u in range(users) for _ in range(clicks_each)]
    results = await asyncio.gather(*calls)
    left = await stock.remaining()
    await r.aclose()
    return results, left


def test_redis_never_hands_out_more_than_stock():
    results, left = run(crowd(users=2000, clicks_each=3))

    assert results.count("RESERVED") == 500
    assert left == 0
    # Repeat clicks from winners just see their existing reservation.
    assert results.count("PENDING") == 500 * 2


def test_release_puts_stock_back():
    async def scenario():
        r = redis_client()
        stock = Stock(r)
        assert await stock.reserve("alice") == "RESERVED"
        await stock.release("alice")
        await stock.release("alice")  # second release must not add stock again
        left, status = await stock.remaining(), await stock.status("alice")
        await r.aclose()
        return left, status

    assert run(scenario()) == (500, None)


def place(user_id):
    db = connect()
    try:
        return create_order(db, user_id)
    finally:
        db.close()


def test_mysql_never_oversells_under_concurrency():
    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(place, [f"user-{i}" for i in range(600)]))

    assert results.count("CONFIRMED") == 500
    assert results.count("FAILED") == 100
    db = connect()
    assert available_stock(db) == 0
    db.close()


def test_duplicate_message_does_not_buy_twice():
    assert place("bob") == "CONFIRMED"
    assert place("bob") == "CONFIRMED"

    db = connect()
    assert available_stock(db) == 499
    db.close()
