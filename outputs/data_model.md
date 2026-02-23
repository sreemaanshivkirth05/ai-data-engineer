# Analytical Data Model Design

## 1. Overview of the Data Model
The analytical data model is designed to support the e-commerce company's reporting and analytics needs, focusing on key performance indicators (KPIs) such as total revenue, customer retention, and payment success rates. The model follows a star schema architecture, consisting of fact tables that capture transactional data and dimension tables that provide context to these transactions. 

## 2. Fact Tables

### 2.1. Fact Orders
- **Grain**: Each record represents a single order placed by a customer.
- **Columns**:
  - `order_id` (Primary Key)
  - `customer_id` (Foreign Key)
  - `order_date` (Date of the order)
  - `total_amount` (Total revenue from the order)
  - `payment_status` (Status of the payment)
  - `order_status` (Current status of the order)
- **Keys**:
  - Primary Key: `order_id`
  - Foreign Key: `customer_id` references `dim_customers(customer_id)`

### 2.2. Fact Payments
- **Grain**: Each record represents a single payment transaction associated with an order.
- **Columns**:
  - `payment_id` (Primary Key)
  - `order_id` (Foreign Key)
  - `payment_date` (Date of the payment)
  - `payment_amount` (Amount paid)
  - `payment_status` (Status of the payment)
- **Keys**:
  - Primary Key: `payment_id`
  - Foreign Key: `order_id` references `fact_orders(order_id)`

### 2.3. Fact Customer Retention
- **Grain**: Each record represents a monthly retention metric for customers.
- **Columns**:
  - `retention_id` (Primary Key)
  - `customer_id` (Foreign Key)
  - `month` (Month of the retention metric)
  - `retained` (Boolean indicating if the customer made a purchase in the month)
- **Keys**:
  - Primary Key: `retention_id`
  - Foreign Key: `customer_id` references `dim_customers(customer_id)`

## 3. Dimension Tables

### 3.1. Dimension Customers
- **Columns**:
  - `customer_id` (Primary Key)
  - `first_name` (Customer's first name)
  - `last_name` (Customer's last name)
  - `email` (Customer's email address)
  - `signup_date` (Date the customer signed up)
  - `country` (Country of the customer)
- **Keys**:
  - Primary Key: `customer_id`

### 3.2. Dimension Products
- **Columns**:
  - `product_id` (Primary Key)
  - `product_name` (Name of the product)
  - `category` (Category of the product)
  - `price` (Price of the product)
  - `stock_quantity` (Current stock level)
- **Keys**:
  - Primary Key: `product_id`

### 3.3. Dimension Time
- **Columns**:
  - `time_id` (Primary Key)
  - `date` (Date)
  - `day` (Day of the month)
  - `month` (Month of the year)
  - `year` (Year)
  - `quarter` (Quarter of the year)
- **Keys**:
  - Primary Key: `time_id`

## 4. Relationships (fact ↔ dimensions)
- **Fact Orders**:
  - `customer_id` (FK) → `dim_customers(customer_id)`
  - `order_date` (FK) → `dim_time(time_id)` (via a time dimension for date analysis)

- **Fact Payments**:
  - `order_id` (FK) → `fact_orders(order_id)`

- **Fact Customer Retention**:
  - `customer_id` (FK) → `dim_customers(customer_id)`
  - `month` (FK) → `dim_time(time_id)` (to analyze retention over time)

## 5. Design Decisions & Assumptions
- **Star Schema**: The star schema is chosen for its simplicity and efficiency in query performance, allowing for straightforward joins between fact and dimension tables.
- **Grain Definition**: Each fact table's grain is defined to ensure that it captures the necessary level of detail for reporting while avoiding redundancy.
- **Data Quality**: The model assumes that data quality checks are implemented during the ETL process to ensure that the data loaded into the warehouse is accurate and consistent.
- **Performance**: Indexing strategies will be applied on foreign keys to optimize query performance, especially for large datasets.
- **Scalability**: The model is designed to accommodate future growth, such as additional metrics or dimensions, without significant restructuring.

This analytical data model provides a robust framework for reporting and analytics, enabling the e-commerce company to derive actionable insights from its data.