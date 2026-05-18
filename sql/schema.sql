CREATE DATABASE IF NOT EXISTS redbus_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE redbus_db;

CREATE TABLE IF NOT EXISTS bus_routes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    route_name TEXT NOT NULL,
    route_link TEXT,
    busname TEXT NOT NULL,
    bustype TEXT,
    departing_time TIME NULL,
    duration TEXT,
    reaching_time TIME NULL,
    star_rating FLOAT NULL,
    price DECIMAL(10, 2) NULL,
    seats_available INT NULL,
    is_government TINYINT(1) DEFAULT 0,
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_route_name (route_name(100)),
    INDEX idx_bustype (bustype(50)),
    INDEX idx_price (price),
    INDEX idx_star_rating (star_rating),
    INDEX idx_seats (seats_available)
);
