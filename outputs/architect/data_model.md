# Analytical Data Model Design for Online Retail Analytics Platform

## 1. Overview of the Data Model
The analytical data model for the online retail analytics platform is designed to support various business goals, including daily sales reporting, customer lifetime value (LTV) analysis, churn prediction, inventory management, and marketing attribution. The model follows a star schema architecture, consisting of fact tables that capture quantitative data and dimension tables that provide contextual information.

## 2. Fact Tables

### 2.1. Sales Fact Table
- **Grain**: Each record represents a unique sales transaction.
- **Columns**:
  - `TransactionId` (INT, PK): Unique identifier for each transaction.
  - `TransactionDate` (DATE): Date of the transaction.
  - `CustomerId` (INT, FK): Identifier for the customer making the purchase.
  - `ProductId` (INT, FK): Identifier for the purchased product.
  - `QuantitySold` (INT): Number of units sold.
  - `TotalSaleAmount` (FLOAT): Total amount of the sale.
  - `DiscountAmount` (FLOAT): Amount of discount applied.
  - `SalesChannel` (STRING): Channel through which the sale was made (e.g., online, in-store).
  - `Region` (STRING): Geographic region of the sale.
  
- **Primary Key**: `TransactionId`
- **Foreign Keys**: `CustomerId`, `ProductId`

### 2.2. Inventory Fact Table
- **Grain**: Each record represents a snapshot of inventory status at a specific time.
- **Columns**:
  - `InventoryId` (INT, PK): Unique identifier for the inventory record.
  - `ProductId` (INT, FK): Identifier for the product.
  - `InventoryDate` (DATE): Date of the inventory snapshot.
  - `StockLevel` (INT): Current stock level of the product.
  - `ReorderLevel` (INT): Minimum stock level before reorder is necessary.
  
- **Primary Key**: `InventoryId`
- **Foreign Keys**: `ProductId`

### 2.3. Marketing Campaign Fact Table
- **Grain**: Each record represents a unique marketing campaign performance.
- **Columns**:
  - `CampaignId` (INT, PK): Unique identifier for the marketing campaign.
  - `CampaignStartDate` (DATE): Start date of the campaign.
  - `CampaignEndDate` (DATE): End date of the campaign.
  - `TotalSpent` (FLOAT): Total amount spent on the campaign.
  - `TotalSalesGenerated` (FLOAT): Total sales attributed to the campaign.
  - `CustomerReach` (INT): Number of customers reached by the campaign.
  
- **Primary Key**: `CampaignId`

## 3. Dimension Tables

### 3.1. Customer Dimension Table
- **Columns**:
  - `CustomerId` (INT, PK): Unique identifier for each customer.
  - `FirstName` (STRING): Customer's first name.
  - `LastName` (STRING): Customer's last name.
  - `Email` (STRING): Customer's email address.
  - `JoinDate` (DATE): Date when the customer joined.
  - `DemographicId` (INT, FK): Foreign key linking to demographic data.
  
- **Primary Key**: `CustomerId`
- **Foreign Keys**: `DemographicId` (links to Population Demographics dataset)

### 3.2. Product Dimension Table
- **Columns**:
  - `ProductId` (INT, PK): Unique identifier for each product.
  - `ProductName` (STRING): Name of the product.
  - `Category` (STRING): Category of the product.
  - `Price` (FLOAT): Price of the product.
  - `SupplierId` (INT, FK): Identifier for the supplier.
  
- **Primary Key**: `ProductId`
- **Foreign Keys**: `SupplierId` (links to supplier information)

### 3.3. Time Dimension Table
- **Columns**:
  - `DateId` (DATE, PK): Unique identifier for each date.
  - `Year` (INT): Year of the date.
  - `Month` (INT): Month of the date.
  - `Day` (INT): Day of the date.
  - `Quarter` (INT): Quarter of the year.
  
- **Primary Key**: `DateId`

### 3.4. Demographic Dimension Table
- **Columns**:
  - `DemographicId` (INT, PK): Unique identifier for demographic data.
  - `TractId` (INT): Identifier for the tract.
  - `State` (STRING): State of the tract.
  - `County` (STRING): County of the tract.
  - `TotalPop` (INT): Total population in the tract.
  - `Income` (FLOAT): Median income in the tract.
  
- **Primary Key**: `DemographicId`

## 4. Relationships (fact ↔ dimensions)
- **Sales Fact Table**:
  - `CustomerId` → `Customer Dimension`
  - `ProductId` → `Product Dimension`
  - `TransactionDate` → `Time Dimension`
  
- **Inventory Fact Table**:
  - `ProductId` → `Product Dimension`
  - `InventoryDate` → `Time Dimension`
  
- **Marketing Campaign Fact Table**:
  - `CampaignId` → `Time Dimension`

## 5. Design Decisions & Assumptions
- **Star Schema Design**: The star schema is chosen for its simplicity and efficiency in querying, which is essential for real-time analytics.
- **Grain Definition**: The grain of each fact table is defined to ensure that it captures the necessary details for analysis without redundancy.
- **Data Quality**: Assumptions are made that data from various sources will be validated and cleansed during the ETL process to maintain high data quality.
- **Historical Data**: The model is designed to retain historical data for trend analysis, particularly for sales and inventory.
- **Scalability**: The model can be extended with additional dimensions or facts as new business requirements arise, such as adding a `Supplier Dimension` for enhanced supplier analysis.

This analytical data model provides a robust foundation for the online retail analytics platform, enabling comprehensive insights into sales performance, customer behavior, and inventory management.