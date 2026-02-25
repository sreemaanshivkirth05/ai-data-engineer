# Requirements Analysis

## 1. Business Goals
The primary business goal is to establish a robust analytics framework for an e-commerce company that focuses on revenue, orders, customers, and payments. The company aims to create daily dashboards to monitor key performance indicators (KPIs) and gain insights into business operations. The architecture should be scalable and based on AWS to accommodate future growth and data processing needs.

## 2. Key Metrics
- **Total Revenue**: Sum of all `total_amount` from the orders.
- **Total Orders**: Count of all orders placed.
- **Total Customers**: Count of unique customers based on `customer_id`.
- **Payment Status**: Breakdown of payment statuses (e.g., successful, failed).
- **Daily Active Users**: Count of unique customers who made purchases on a given day.

## 3. Core Entities
- **Orders**: Represents individual orders placed by customers.
- **Customers**: Represents customers who place orders, including their details.
- **Payments**: Represents payment transactions related to orders.

## 4. Data Sources
- **Orders Table**: 
  - Schema: `orders(id, customer_id, total_amount, created_at, status)`
- **Customers Table**: 
  - Schema: `customers(id, email, region, signup_date)`
- **Payments Table**: 
  - Schema: `payments(id, order_id, amount, status, paid_at)`

## 5. Data Granularity
- **Orders**: Daily granularity based on the `created_at` timestamp. Each row represents a single order.
- **Customers**: Data is captured at the time of signup, with unique entries for each customer.
- **Payments**: Daily granularity based on the `paid_at` timestamp. Each row represents a single payment transaction.

## 6. Assumptions & Open Questions
- **Assumptions**:
  - The data from the source systems is reliable and updated regularly.
  - There will be no significant changes to the structure of the source schemas in the near term.
  - Data governance policies will be in place to manage PII effectively.

- **Open Questions**:
  - What is the expected frequency of updates to the source data? Is it real-time or batch?
  - Are there any additional data sources that need to be integrated (e.g., product details, shipping information)?
  - What specific compliance requirements exist regarding PII handling and data retention?
  - How will data quality be monitored and enforced in the pipeline?

This structured analysis provides a clear overview of the requirements needed to design a production-grade data pipeline for the e-commerce company, ensuring that it meets business goals while maintaining data quality and performance.