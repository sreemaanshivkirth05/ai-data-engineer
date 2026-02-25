# Analytical Data Model Design for E-commerce Analytics

## 1. Overview of the Data Model
The analytical data model for the e-commerce analytics pipeline is designed to support reporting and analysis of key business metrics such as revenue, order volume, customer demographics, and payment methods. The model follows a star schema architecture, which consists of fact tables that capture quantitative data and dimension tables that provide descriptive attributes related to the facts. This design ensures efficient querying and analysis, while also supporting data quality and performance requirements.

## 2. Fact Tables

### 2.1. Fact Table: `fact_orders`
- **Grain**: Each record represents a single order placed by a customer on a specific date.
- **Columns**:
  - `order_id` (STRING, PK): Unique identifier for the order.
  - `customer_id` (STRING, FK): Foreign key referencing the customer.
  - `order_date` (DATE): Date when the order was placed.
  - `total_amount` (DECIMAL): Total revenue generated from the order.
  - `payment_id` (STRING, FK): Foreign key referencing the payment transaction.
- **Primary Key**: `order_id`
- **Foreign Keys**: 
  - `customer_id` references `dim_customers(customer_id)`
  - `payment_id` references `dim_payments(payment_id)`

### 2.2. Fact Table: `fact_payments`
- **Grain**: Each record represents a single payment transaction associated with an order.
- **Columns**:
  - `payment_id` (STRING, PK): Unique identifier for the payment transaction.
  - `order_id` (STRING, FK): Foreign key referencing the order.
  - `payment_date` (DATE): Date when the payment was processed.
  - `payment_method` (STRING): Method used for payment (e.g., credit card, PayPal).
  - `amount` (DECIMAL): Amount paid in the transaction.
- **Primary Key**: `payment_id`
- **Foreign Keys**: 
  - `order_id` references `fact_orders(order_id)`

## 3. Dimension Tables

### 3.1. Dimension Table: `dim_customers`
- **Columns**:
  - `customer_id` (STRING, PK): Unique identifier for the customer.
  - `first_name` (STRING): First name of the customer.
  - `last_name` (STRING): Last name of the customer.
  - `email` (STRING): Email address of the customer.
  - `registration_date` (DATE): Date when the customer registered.
  - `customer_region` (STRING): Geographic region of the customer.
- **Primary Key**: `customer_id`

### 3.2. Dimension Table: `dim_products`
- **Columns**:
  - `product_id` (STRING, PK): Unique identifier for the product.
  - `product_name` (STRING): Name of the product.
  - `category` (STRING): Category to which the product belongs.
  - `price` (DECIMAL): Price of the product.
- **Primary Key**: `product_id`

## 4. Relationships (fact ↔ dimensions)
- The `fact_orders` table is linked to:
  - `dim_customers` via `customer_id`
  - `dim_products` via a potential join table (if needed) for products associated with each order.
  
- The `fact_payments` table is linked to:
  - `fact_orders` via `order_id`

## 5. Design Decisions & Assumptions
- **Star Schema**: The decision to use a star schema allows for simplified queries and improved performance for analytical workloads. Fact tables are denormalized to optimize read performance.
- **Composite Keys**: The use of unique identifiers for primary keys ensures data integrity and supports efficient joins between fact and dimension tables.
- **Data Quality**: The model assumes that data quality checks during the ETL process will ensure that only valid and complete records are loaded into the fact and dimension tables.
- **Scalability**: The model is designed to accommodate growth in data volume as the e-commerce platform scales, particularly in the number of orders and customers.
- **Business Metrics**: The model supports essential business metrics such as total revenue, order count, and payment methods, which are critical for business analysis and decision-making.

This analytical data model provides a robust framework for e-commerce analytics, enabling timely insights and effective reporting on key business metrics.