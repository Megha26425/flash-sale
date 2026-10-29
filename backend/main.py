import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import aio_pika
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from settings import PRODUCT_ID, QUEUE_NAME, RABBITMQ_URL, SALE_START
from stock import Stock, redis_client


@asynccontextmanager
async def lifespan(app):
    redis = redis_client()
    rabbit = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await rabbit.channel(publisher_confirms=True)
    await channel.declare_queue(QUEUE_NAME, durable=True)

    app.state.stock = Stock(redis)
    app.state.channel = channel
    yield
    await rabbit.close()
    await redis.aclose()


app = FastAPI(title="Flash Sale API", lifespan=lifespan)


class CheckoutIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=64, pattern=r"^[\w-]+$")


def reply(status, code=200):
    return JSONResponse({"status": status}, status_code=code)


@app.exception_handler(RedisError)
async def redis_busy(request, exc):
    # Nothing was reserved, so the client can safely retry with the same user id.
    return reply("TRY_AGAIN", 503)


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/api/sale")
async def sale_info():
    return {
        "product_id": PRODUCT_ID,
        "starts_at": SALE_START.isoformat(),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "stock_left": await app.state.stock.remaining(),
    }


@app.post("/api/checkout")
async def checkout(body: CheckoutIn):
    if datetime.now(timezone.utc) < SALE_START:
        return reply("NOT_STARTED", 425)

    stock = app.state.stock
    result = await stock.reserve(body.user_id)

    if result not in ("RESERVED", "PENDING"):
        return reply(result)  # SOLD_OUT, CONFIRMED or FAILED

    # PENDING here means a retry. We queue it again in case the first attempt never
    # made it; the worker ignores duplicates, so this can't create a second order.
    message = aio_pika.Message(
        json.dumps({"user_id": body.user_id}).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    try:
        await app.state.channel.default_exchange.publish(message, routing_key=QUEUE_NAME)
    except Exception:
        if result == "RESERVED":
            # Couldn't hand it to the queue, so put the phone back for someone else.
            await stock.release(body.user_id)
        return reply("TRY_AGAIN", 503)
    return reply("PENDING", 202)


@app.get("/api/checkout/{user_id}")
async def checkout_status(user_id: str):
    status = await app.state.stock.status(user_id)
    if status is None:
        return reply("NOT_FOUND", 404)
    return reply(status, 202 if status == "PENDING" else 200)
