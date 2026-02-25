# Analytical Data Model for E-commerce Analytics Platform

## 1. Overview of the Data Model
The analytical data model for the e-commerce analytics platform is designed to facilitate reporting and analysis of key business metrics related to revenue, orders, customers, and payments. The model follows a star schema architecture, consisting of fact tables that capture measurable events and dimension tables that provide context to these events. This design supports efficient querying and analysis, ensuring data quality and performance.

## 2. Fact Tables

### Fact Table: `FactOrders`
- **Grain**: One record per order (each order placed by a customer).
- **Columns**:
  - `OrderID` (INT, PK): Unique identifier for each order.
  - `CustomerID` (INT, FK): Foreign key referencing `DimCustomers`.
  - `OrderDate` (DATE): Date when the order was placed.
  - `TotalAmount` (DECIMAL): Total revenue generated from the order.
  - `PaymentID` (INT, FK): Foreign key referencing `FactPayments`.
  - `OrderStatus` (STRING): Status of the order (e.g., Completed, Pending, Canceled).
- **Primary Key**: `OrderID`
- **Foreign Keys**: 
  - `CustomerID` references `DimCustomers(CustomerID)`
  - `PaymentID` references `FactPayments(PaymentID)`

### Fact Table: `FactPayments`
- **Grain**: One record per payment transaction.
- **Columns**:
  - `PaymentID` (INT, PK): Unique identifier for each payment.
  - `OrderID` (INT, FK): Foreign key referencing `FactOrders`.
  - `PaymentDate` (DATE): Date when the payment was made.
  - `PaymentAmount` (DECIMAL): Amount paid.
  - `PaymentMethod` (STRING): Method of payment (e.g., Credit Card, PayPal).
- **Primary Key**: `PaymentID`
- **Foreign Keys**: 
  - `OrderID` references `FactOrders(OrderID)`

## 3. Dimension Tables

### Dimension Table: `DimCustomers`
- **Columns**:
  - `CustomerID` (INT, PK): Unique identifier for each customer.
  - `FirstName` (STRING): Customer's first name.
  - `LastName` (STRING): Customer's last name.
  - `Email` (STRING): Customer's email address.
  - `JoinDate` (DATE): Date when the customer joined.
  - `Country` (STRING): Country of residence.
- **Primary Key**: `CustomerID`

### Dimension Table: `DimProducts`
- **Columns**:
  - `ProductID` (INT, PK): Unique identifier for each product.
  - `ProductName` (STRING): Name of the product.
  - `Category` (STRING): Product category (e.g., Electronics, Apparel).
  - `Price` (DECIMAL): Price of the product.
  - `StockQuantity` (INT): Available stock for the product.
- **Primary Key**: `ProductID`

### Dimension Table: `DimTime`
- **Columns**:
  - `TimeID` (INT, PK): Unique identifier for each time record.
  - `OrderDate` (DATE): Date of the order.
  - `Year` (INT): Year of the order.
  - `Month` (INT): Month of the order.
  - `Day` (INT): Day of the order.
  - `Quarter` (INT): Quarter of the year.
- **Primary Key**: `TimeID`

## 4. Relationships (fact ↔ dimensions)
- `FactOrders` is related to:
  - `DimCustomers` via `CustomerID`
  - `DimTime` via `OrderDate` (can be linked through `DimTime` if a surrogate key is used)
  
- `FactPayments` is related to:
  - `FactOrders` via `OrderID`
  
- `FactOrders` may also have a relationship with `DimProducts` if product details are included in the order fact (e.g., through a bridge table if multiple products per order).

## 5. Design Decisions & Assumptions
- **Star Schema Design**: The star schema was chosen for its simplicity and efficiency in querying, making it suitable for BI tools and reporting.
- **Fact Tables**: Separate fact tables for orders and payments allow for detailed analysis of both order and payment metrics independently.
- **Dimension Tables**: Dimensions are designed to provide rich context for the facts, enabling detailed analysis of customer behavior, product performance, and time-based trends.
- **Data Quality**: Assumptions include that data will be cleaned and validated during the ETL process, ensuring adherence to data quality standards.
- **Performance Considerations**: The model is designed to optimize query performance by minimizing the number of joins and ensuring that fact tables are appropriately indexed.
- **Scalability**: The model is designed to accommodate future growth in data volume and complexity, allowing for additional dimensions or facts as business needs evolve.

This analytical data model provides a robust foundation for e-commerce analytics, enabling stakeholders to derive insights from key business metrics effectively.