-- Average price by route
SELECT route_name, ROUND(AVG(price), 2) AS avg_price, COUNT(*) AS bus_count
FROM bus_routes
GROUP BY route_name
ORDER BY avg_price;

-- Government vs private count
SELECT
    CASE WHEN is_government = 1 THEN 'Government' ELSE 'Private' END AS operator_type,
    COUNT(*) AS total
FROM bus_routes
GROUP BY is_government;

-- Top rated buses (min 10 reviews proxy: rating >= 4)
SELECT route_name, busname, bustype, star_rating, price, seats_available
FROM bus_routes
WHERE star_rating >= 4.0
ORDER BY star_rating DESC, price ASC
LIMIT 20;