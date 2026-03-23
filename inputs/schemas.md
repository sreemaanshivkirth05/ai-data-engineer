orders(
  order_id    INT PRIMARY KEY,
  customer_id INT,
  status      VARCHAR(20),
  total       DECIMAL(12,2),
  region      VARCHAR(50),
  created_at  TIMESTAMP
)

customers(
  customer_id INT PRIMARY KEY,
  email       VARCHAR(255),
  tier        VARCHAR(20),
  signup_date DATE,
  country     VARCHAR(50)
)

order_items(
  item_id    INT PRIMARY KEY,
  order_id   INT,
  product_id INT,
  quantity   INT,
  unit_price DECIMAL(10,2)
)

products(
  product_id INT PRIMARY KEY,
  name       VARCHAR(255),
  category   VARCHAR(100),
  cost       DECIMAL(10,2)
)