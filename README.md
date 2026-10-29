# Flash Sale Checkout

500 phones, 100k people hitting **Buy** at 8:00 PM, and exactly 500 orders at the end.

```
Browser ──► NGINX ──► FastAPI (x3) ──► Redis      "is there stock left?" (atomic Lua)
            rate limit                └─► RabbitMQ ──► Worker (x2) ──► MySQL
            bot filter                                  writes the real order
            static files + cache
```

## Run it

```bash
cp .env.example .env          # set SALE_START, or leave it empty to open the sale now
docker compose up --build
```

- Shop: http://localhost:8080
- RabbitMQ dashboard: http://localhost:15672 (guest / guest)

Load test (fires 5,000 buyers who each click 3 times, then checks MySQL):

```bash
docker compose exec api python reset_sale.py
docker compose exec api python load_test.py --users 5000
```

Unit tests (need Redis + MySQL up; they wipe the sale data):

```bash
docker compose exec api pytest
```

## How a click flows

1. **Browser** locks the button on the first click, so only one request goes out.
2. **NGINX** drops scripts (5 checkout requests/sec per IP, obvious bot user agents get 403) and spreads the rest across the API replicas.
3. **API** runs one Lua script in Redis: if the user already has a reservation, return it. If stock is 0, return `SOLD_OUT`. Otherwise decrement and mark the user `PENDING`. Redis runs the script atomically, so only 500 people can ever get past this point. The other 99,500 get an answer straight from memory and never touch MySQL.
4. Winners get put on a durable RabbitMQ queue, and the API replies **202 Accepted** right away.
5. **Worker** takes each message and runs one MySQL transaction:
   `UPDATE inventory SET available_stock = available_stock - 1 WHERE product_id = ? AND available_stock > 0`, then inserts the order.
   A `UNIQUE (product_id, user_id)` key and a `CHECK (available_stock >= 0)` back this up at the database level.
6. The worker writes `CONFIRMED` back to Redis. The browser has been polling `/api/checkout/{user_id}` and shows it.

## Files

| | |
|---|---|
| `backend/main.py` | API: sale info, checkout, order status |
| `backend/stock.py` | Redis Lua scripts (reserve / release) |
| `backend/worker.py` | Queue consumer, writes orders to MySQL |
| `backend/db.py` | The order transaction |
| `backend/schema.sql` | Tables + the 500-unit product |
| `backend/reset_sale.py` | Reset stock to 500 (dev only) |
| `backend/load_test.py` | Crowd simulation + overselling check |
| `frontend/` | Product page, countdown, buy button. Plain JS, ~8 KB total |
| `nginx/nginx.conf` | Load balancing, rate limits, caching |

## Design notes (interview talking points)

**Why was it overselling before?** The usual pattern is `SELECT stock` → check `> 0` in code → `UPDATE stock = stock - 1`. Two requests can both read `1` before either writes, and both sell. Under 100k requests that gap gets hit constantly. Here the check and the decrement are always one step: one Lua script in Redis, one conditional `UPDATE` in MySQL.

**Why Redis in front of MySQL?** Even a correct SQL update holds a row lock, and 100k transactions queueing on the same inventory row is exactly what caused the lock timeouts. Redis is single-threaded and in memory, so it takes the spike, and MySQL only ever sees about 500 writes.

**Pessimistic vs optimistic locking.** Pessimistic (`SELECT ... FOR UPDATE`) is correct but makes everyone wait in line on one row. Optimistic (version column, retry on conflict) means almost every retry fails when everyone wants the same row. A conditional atomic decrement avoids both: no explicit lock, no retry loop, and the `WHERE available_stock > 0` makes it impossible to go negative.

**Idempotency.** One phone per user. Repeat clicks, browser retries and duplicate queue deliveries all land on the same Redis entry or the same unique key in MySQL, so nothing gets bought twice. That's why it's safe for the frontend to retry automatically.

**Failure handling.**
- RabbitMQ down when publishing: the reservation is released and the client gets `503 TRY_AGAIN`.
- Redis busy: `503 TRY_AGAIN`, and nothing was reserved.
- Worker crashes mid-order: the message was never acked, so RabbitMQ redelivers it.
- Workers down entirely: orders wait in the queue and the API keeps working.

**Polling vs WebSockets.** Sale status is a single number that's the same for everyone, so the page polls it every 4 seconds and NGINX caches it for 1 second. 100k polls then cost about one backend call per second. Holding 100k WebSockets open would cost far more for no real gain. Order status is polled with backoff (1s → 5s) and only by people who actually got a reservation.

**Frontend.** No framework, so the whole page is ~8 KB and becomes interactive almost immediately. Static files get long cache headers. In production they'd sit on a CDN, so the servers only handle API calls. The countdown uses the server's clock, so a user with a wrong PC clock can't get a head start.

## Tested

On a 2-core machine with two API instances and two workers:
- 30,000 checkout requests from 5,000 users hitting both instances at once: **500 orders, 500 distinct buyers, 0 stock left**, no errors.
- Workers stopped during the sale: the API kept answering (~1,200 req/s), orders queued up, and once a worker started there were exactly 500 orders.
- Triple-clicking Buy in a real browser sends one request.

## What I'd add for real production

- Real login. Right now the browser makes a random user id, so a bot could invent new ids. NGINX limits per IP, but a login or CAPTCHA at checkout would close that gap.
- Payment step and a timeout that releases unpaid reservations.
- Redis Sentinel/Cluster and a RabbitMQ cluster instead of single nodes.
- After scaling `api` replicas, restart NGINX so it picks up the new containers.
