import json
import time

import pika
import redis

from db import available_stock, connect, create_order
from settings import ORDERS_KEY, QUEUE_NAME, RABBITMQ_URL, REDIS_URL, STOCK_KEY


def main():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    db = connect()

    if r.set(STOCK_KEY, available_stock(db), nx=True):
        print(f"Loaded {r.get(STOCK_KEY)} units into Redis")

    rabbit = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = rabbit.channel()
    channel.queue_declare(QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=10)

    def handle(ch, method, _props, body):
        try:
            user_id = json.loads(body)["user_id"]
        except (ValueError, KeyError):
            print("Dropping bad message:", body[:100])
            ch.basic_nack(method.delivery_tag, requeue=False)
            return

        try:
            db.ping(reconnect=True, attempts=3, delay=1)
            status = create_order(db, user_id)
        except Exception as e:
            print(f"Order for {user_id} failed, will retry: {e}")
            time.sleep(1)
            ch.basic_nack(method.delivery_tag, requeue=True)
            return

        r.hset(ORDERS_KEY, user_id, status)
        ch.basic_ack(method.delivery_tag)
        print(user_id, status)

    channel.basic_consume(QUEUE_NAME, handle)
    print("Worker waiting for orders...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        pass
    finally:
        rabbit.close()
        db.close()


if __name__ == "__main__":
    main()
