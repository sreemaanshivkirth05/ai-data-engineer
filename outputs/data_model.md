# Analytical Data Model for MLB Employee Data

## 1. Overview of the Data Model
The analytical data model is designed to support the analysis of MLB employee data, focusing on employee demographics, team affiliations, and performance metrics. The model follows a star schema architecture, which includes fact and dimension tables to facilitate efficient querying and reporting. The model aims to ensure data quality, performance, and compliance with regulations, particularly concerning PII.

## 2. Fact Tables

### Employee Fact Table
- **Table Name**: `fact_employee`
- **Grain**: One record per employee per day (captures daily snapshots of employee data).
- **Columns**:
  - `employee_id` (INT, PK): Unique identifier for each employee.
  - `first_name` (STRING): Employee's first name (PII).
  - `last_name` (STRING): Employee's last name (PII).
  - `team_id` (INT, FK): Foreign key referencing the `dim_team` table.
  - `position_id` (INT, FK): Foreign key referencing the `dim_position` table.
  - `height_inches` (INT): Height of the employee in inches.
  - `weight_pounds` (INT): Weight of the employee in pounds.
  - `age` (FLOAT): Age of the employee (in years).
  - `record_date` (DATE): Date of the record (for daily snapshots).
- **Primary Key**: `employee_id`
- **Foreign Keys**: 
  - `team_id` references `dim_team(team_id)`
  - `position_id` references `dim_position(position_id)`

## 3. Dimension Tables

### Team Dimension Table
- **Table Name**: `dim_team`
- **Columns**:
  - `team_id` (INT, PK): Unique identifier for each team.
  - `team_name` (STRING): Name of the team.
  - `league` (STRING): League to which the team belongs (e.g., AL, NL).
- **Primary Key**: `team_id`

### Position Dimension Table
- **Table Name**: `dim_position`
- **Columns**:
  - `position_id` (INT, PK): Unique identifier for each position.
  - `position_name` (STRING): Name of the position (e.g., Pitcher, Catcher).
- **Primary Key**: `position_id`

## 4. Relationships (fact ↔ dimensions)
- The `fact_employee` table is connected to the `dim_team` and `dim_position` tables through foreign keys:
  - `fact_employee.team_id` → `dim_team.team_id`
  - `fact_employee.position_id` → `dim_position.position_id`
  
This relationship allows for detailed analysis of employee data by team and position, enabling metrics such as average height, weight, and age by team or position.

## 5. Design Decisions & Assumptions
### Design Decisions
- **Grain Definition**: The grain of the `fact_employee` table is defined as one record per employee per day to capture daily snapshots, which allows for temporal analysis of employee data.
- **Composite Key Handling**: Instead of relying on the composite key of `first_name` and `last_name`, a unique `employee_id` is introduced to ensure uniqueness and avoid collisions.
- **Dimension Tables**: Separate dimension tables for team and position provide flexibility for analysis and reporting, allowing for easy aggregation and filtering.

### Assumptions
- The dataset will maintain consistency in the naming conventions for teams and positions.
- Employee data will be updated regularly, and the `record_date` will accurately reflect the date of the data snapshot.
- PII data will be handled in compliance with relevant regulations, ensuring that sensitive information is protected.

### Risks
- The reliance on `first_name` and `last_name` for identity could lead to potential collisions; hence the introduction of a unique `employee_id` mitigates this risk.
- Changes in team or position names may require updates to the dimension tables, which should be managed through a versioning strategy to maintain data integrity.

This analytical data model provides a robust framework for analyzing MLB employee data, supporting various business metrics while ensuring data quality and compliance with regulations.