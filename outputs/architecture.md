# Requirements Analysis

## 1. Business Goals
The primary business goal is to enable analytics for revenue, orders, customers, and payments in order to support decision-making and performance tracking for the e-commerce company. The company aims to create daily dashboards that provide insights into key metrics, ensuring the architecture is scalable and based on AWS technologies.

## 2. Key Metrics
- **Total Revenue**: Sum of all payments received.
- **Total Orders**: Count of all orders placed.
- **Total Customers**: Count of unique customers who have placed orders.
- **Payment Status**: Breakdown of payment statuses (e.g., completed, pending, failed).
- **Average Order Value**: Total revenue divided by the total number of orders.
- **Customer Retention Rate**: Percentage of customers who make repeat purchases over a defined period.

## 3. Core Entities
- **Orders**: Represents customer orders with attributes such as order ID, customer ID, total amount, creation date, and status.
- **Customers**: Represents customer information with attributes including customer ID, email, region, and signup date.
- **Payments**: Represents payment transactions with attributes such as payment ID, order ID, amount, status, and payment date.

## 4. Data Sources
- **Orders Table**: 
  - Schema: `orders(id, customer_id, total_amount, created_at, status)`
- **Customers Table**: 
  - Schema: `customers(id, email, region, signup_date)`
- **Payments Table**: 
  - Schema: `payments(id, order_id, amount, status, paid_at)`

## 5. Data Granularity
- **Orders**: Daily granularity based on the `created_at` timestamp.
- **Customers**: Daily updates reflecting new signups.
- **Payments**: Daily granularity based on the `paid_at` timestamp.

## 6. Assumptions & Open Questions
### Assumptions
- The data from the source tables will be consistently available and updated on a daily basis.
- The existing schemas for orders, customers, and payments will remain stable, with no major changes expected in the near term.
- Data quality checks will be implemented to ensure accuracy and completeness.

### Open Questions
- What specific AWS services are preferred for data ingestion, storage, and processing (e.g., AWS Glue, Redshift, S3)?
- Are there any specific compliance requirements related to customer data (e.g., GDPR, CCPA)?
- What are the expected volumes of data, and how will this impact performance and scalability?
- How will data quality be monitored, and what thresholds will be set for alerts?