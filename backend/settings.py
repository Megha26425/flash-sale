import os
from datetime import datetime, timezone

PRODUCT_ID = os.getenv("PRODUCT_ID", "PHONE-001")
QUEUE_NAME = "checkouts"

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

DB = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "root"),
    "database": os.getenv("DB_NAME", "flash_sale"),
}

_start = os.getenv("SALE_START", "")
SALE_START = datetime.fromisoformat(_start) if _start else datetime.now(timezone.utc)

STOCK_KEY = f"sale:{PRODUCT_ID}:stock"
ORDERS_KEY = f"sale:{PRODUCT_ID}:orders"
