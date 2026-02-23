# Requirements Analysis

## 1. Business Goals
The primary objective is to build a robust analytics solution for an e-commerce company that provides daily dashboards focused on key performance indicators (KPIs) such as revenue, orders, customer metrics, and retention rates. The solution should facilitate data-driven decision-making and enhance visibility into business performance.

## 2. Key Metrics
- **Total Revenue**: Sum of `total_amount` from the `orders` table.
- **Total Orders**: Count of distinct `order_id` from the `orders` table.
- **Total Customers**: Count of distinct `customer_id` from the `customers` table.
- **Customer Retention Rate**: Percentage of returning customers over a defined period.
- **Payment Success Rate**: Ratio of successful payments to total payments processed.

## 3. Core Entities
- **Orders**: Represents customer transactions, including order details and status.
- **Customers**: Contains information about customers, including their contact details and account creation date.
- **Payments**: Tracks payment transactions associated with orders, including payment status and method.

## 4. Data Sources
- **Transactional Database**: 
  - **Orders Table**: `orders(order_id, customer_id, order_date, total_amount, status)`
  - **Customers Table**: `customers(customer_id, name, email, created_at)`
- **Payments API**: 
  - **Payments Table**: `payments(payment_id, order_id, payment_date, amount, method, status)`

## 5. Data Granularity
- **Orders**: Daily granularity based on `order_date`.
- **Customers**: Daily snapshots based on `created_at` for new customers.
- **Payments**: Daily granularity based on `payment_date`.

## 6. Assumptions & Open Questions
- **Assumptions**:
  - The transactional database is updated in real-time or near real-time, allowing for daily data extraction.
  - The payments API provides reliable and consistent data for payment transactions.
  - Customer retention calculations will be based on a defined time period (e.g., monthly, quarterly).

- **Open Questions**:
  - What is the definition of a "returning customer" for retention calculations?
  - Are there any specific data quality checks required for the incoming data from the transactional database and payments API?
  - What are the expected response times for the dashboards, and how will they be accessed (e.g., web application, BI tool)?
  - Are there any additional data sources or metrics that should be considered for a more comprehensive analysis?