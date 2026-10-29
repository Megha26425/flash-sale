# Flash Sale Checkout System

This project simulates an e-commerce flash sale where 500 phones are available and a large number of users try to buy them at the same time.

The main goal is to handle a sudden increase in checkout requests without overselling the available stock. Even if thousands of users click the Buy button together, the system should allow only valid reservations and ensure that no more than 500 orders are confirmed.

## Architecture

The system uses FastAPI for handling checkout requests, Redis for managing stock reservations, RabbitMQ for queuing requests, and MySQL for storing confirmed orders.

```text
Browser -> NGINX -> FastAPI (3 instances)
                       |
                       v
                     Redis
                  Stock checks
                       |
                       v
                    RabbitMQ
                       |
                       v
                Checkout Workers (2)
                       |
                       v
                     MySQL
```

NGINX handles incoming traffic, applies rate limits, and distributes requests across the API instances. Redis checks and reserves stock, while RabbitMQ holds checkout requests until a worker can process them. MySQL stores the final order records.

## How checkout works

1. The user opens the product page and clicks the Buy button. The frontend disables the button after the first click to avoid sending repeated requests from the same interaction.
2. NGINX applies rate limits and forwards requests to one of the FastAPI instances.
3. The API checks Redis to see whether the user already has a reservation and whether stock is available. The stock reservation is handled atomically so that multiple requests cannot reserve the same remaining unit.
4. If stock is available, the reservation is created and the checkout request is sent to RabbitMQ. The API returns a `202 Accepted` response while the order is being processed.
5. A worker consumes the message and uses a MySQL transaction to update inventory and insert the order. Database constraints provide an additional layer of protection against duplicate orders and negative stock.
6. After processing, the worker updates the checkout status in Redis. The frontend polls the status endpoint to check whether the order has been confirmed or marked as sold out.

Requests that arrive after all 500 units have been reserved should receive a sold-out response without creating an additional reservation.

## Technologies used

- **FastAPI:** Checkout API and order status endpoints.
- **Redis:** Fast stock checks and atomic reservations.
- **RabbitMQ:** Queue for processing checkout requests asynchronously.
- **MySQL:** Persistent inventory and order records.
- **NGINX:** Load balancing, rate limiting, bot filtering, and static file delivery.
- **Docker Compose:** Runs the services together.
- **HTML, CSS and JavaScript:** Product page, countdown, and Buy button.

## Project structure


 `backend/main.py` 
 `backend/stock.py` 
 `backend/worker.py` 
 `backend/db.py` 
 `backend/schema.sql` 
 `backend/reset_sale.py`
 `backend/load_test.py`
 `frontend/` 
 `nginx/nginx.conf` 
 `docker-compose.yml` 

## Running the project

Make sure Docker Desktop is running, then open a terminal in the project directory.

Create the environment file:

```bash
cp .env.example .env
```

Configure the required environment variables, including the sale start time if needed. Leave `SALE_START` empty to open the sale immediately, as supported by the application.

Start the services:

```bash
docker compose up --build
```

Open the following URLs:

- Shop: http://localhost:8080
- RabbitMQ dashboard: http://localhost:15672

The RabbitMQ dashboard uses `guest` / `guest` with the default local configuration.

## Testing

Before running the load test, reset the sale data:

```bash
docker compose exec api python reset_sale.py
```

Simulate 5,000 users, with each user attempting to click Buy three times:

```bash
docker compose exec api python load_test.py --users 5000
```

The load test checks the checkout results and verifies that the system does not oversell the 500 available units.

To run the automated tests:

```bash
docker compose exec api pytest
```

**Note:** The reset script and tests modify or clear sale data, so use them only in the development environment.

## Known issue

There is currently a bug in the frontend stock display. Even after the available stock reaches zero, the product page can continue showing **"500 left"**.

The backend stock reservation logic and the frontend stock display are not staying in sync. The frontend needs to fetch and display the latest stock information instead of continuing to show the initial value. This needs to be fixed and tested during the next round of development.


