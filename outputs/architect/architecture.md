# Requirements Analysis

## 1. Business Goals
- **Daily Sales Dashboard**: Provide insights on revenue segmented by region, product category, and sales representative.
- **Customer Lifetime Value (LTV) and Churn Prediction**: Analyze customer data to predict future value and potential churn rates.
- **Inventory Alerts**: Implement a system to notify stakeholders when stock levels fall below predefined reorder thresholds.
- **Marketing Attribution**: Track and analyze the effectiveness of marketing efforts across various channels.

## 2. Key Metrics
- **Revenue**: Total sales revenue segmented by region, product category, and sales representative.
- **Customer Lifetime Value (LTV)**: Average revenue generated from a customer over their entire relationship with the business.
- **Churn Rate**: Percentage of customers who stop using the service over a specific period.
- **Inventory Levels**: Current stock levels of products, with alerts for items below reorder thresholds.
- **Marketing Attribution Metrics**: Performance metrics for each marketing channel (e.g., conversion rates, ROI).

## 3. Core Entities
- **Orders**: Represents individual customer orders, including order details and total revenue.
- **Customers**: Contains customer information, including demographics and purchase history.
- **Order Items**: Details of each product within an order, including quantity and price.
- **Products**: Information about products available for sale, including categories and costs.
- **Sales Representatives**: Information about sales personnel responsible for customer interactions.

## 4. Data Sources
- **Orders Table**: Contains order_id, customer_id, status, total, region, and created_at.
- **Customers Table**: Contains customer_id, email, tier, signup_date, and country.
- **Order Items Table**: Contains item_id, order_id, product_id, quantity, and unit_price.
- **Products Table**: Contains product_id, name, category, and cost.

## 5. Data Granularity
- **Order Level**: Data is captured at the individual order level, allowing for detailed analysis of sales and customer behavior.
- **Daily Aggregation**: Sales data will be aggregated daily for dashboard reporting, ensuring timely insights.
- **Historical Data**: Retain 3 years of historical data for trend analysis and forecasting.

## 6. Assumptions & Open Questions
- **Assumptions**:
  - Data from the source systems is accurate and updated in a timely manner.
  - The existing schema is sufficient to meet the reporting needs without significant changes.
  - Analysts and stakeholders have the necessary access and tools to utilize the data effectively.

- **Open Questions**:
  - What specific thresholds for inventory alerts should be defined?
  - How will customer churn be calculated (e.g., what timeframe and criteria)?
  - Are there additional data sources or external datasets that should be integrated for marketing attribution?
  - What specific metrics or dimensions are needed for the LTV analysis?