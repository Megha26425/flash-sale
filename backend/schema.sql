CREATE DATABASE IF NOT EXISTS flash_sale;
USE flash_sale;

CREATE TABLE IF NOT EXISTS inventory (
    product_id      VARCHAR(32)  PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    price           INT          NOT NULL,
    total_stock     INT          NOT NULL,
    available_stock INT          NOT NULL,
    CONSTRAINT stock_not_negative CHECK (available_stock >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    product_id VARCHAR(32) NOT NULL,
    user_id    VARCHAR(64) NOT NULL,
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY one_per_user (product_id, user_id),
    FOREIGN KEY (product_id) REFERENCES inventory (product_id)
);

INSERT IGNORE INTO inventory (product_id, name, price, total_stock, available_stock)
VALUES ('PHONE-001', 'Nova X Pro 5G', 49999, 500, 500);
