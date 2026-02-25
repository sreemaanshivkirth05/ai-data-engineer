# Data Contract for Employee Dataset

## 1. Overview
This document outlines the canonical schema, keys, constraints, data quality expectations, and data contract rules for the Employee dataset. The dataset consists of 1034 rows and 7 columns, capturing personal and professional attributes of employees. The schema is designed to ensure data integrity, facilitate data processing, and maintain compliance with data governance policies.

## 2. Canonical Schema

| Column Name         | Data Type   | Nullable | Description                                         |
|---------------------|-------------|----------|-----------------------------------------------------|
| First Name          | STRING      | NO       | The first name of the employee (PII)               |
| Last Name           | STRING      | NO       | The last name of the employee (PII)                |
| Team                | STRING      | NO       | The team to which the employee belongs              |
| Position            | STRING      | NO       | The job position of the employee                    |
| Height(inches)     | INTEGER     | NO       | The height of the employee in inches                |
| Weight(pounds)      | INTEGER     | NO       | The weight of the employee in pounds                |
| Age                 | FLOAT       | NO       | The age of the employee                              |

## 3. Keys & Constraints

- **Primary Key**: 
  - There is no single primary key identified in the dataset. However, a composite key could be formed using `First Name`, `Last Name`, and `Age` to ensure uniqueness.

- **Foreign Keys**: 
  - No foreign keys are identified in the current dataset profile.

- **Constraints**:
  - **Uniqueness**: 
    - `First Name`, `Last Name`, and `Age` combination should be unique.
  - **Range Constraints**:
    - `Height(inches)` should be between 67 and 83.
    - `Weight(pounds)` should be between 150 and 290.
    - `Age` should be between 21 and 48 (rounded from float).
  - **Enumerations**: 
    - `Team` and `Position` can be defined as enumerated types if a fixed list of values is established.

## 4. Data Quality Expectations
- All fields must be populated (no null values).
- Data types must be strictly adhered to as defined in the schema.
- Values must conform to specified ranges and uniqueness constraints.
- Personal Identifiable Information (PII) must be handled according to data governance policies.

## 5. Data Contract Rules (Versioning & Evolution)

- **Versioning Strategy**:
  - Each version of the dataset will be incremented with a semantic versioning approach (e.g., MAJOR.MINOR.PATCH).
  - MAJOR version for breaking changes, MINOR for backward-compatible changes, and PATCH for non-breaking fixes.

- **Backward Compatibility**:
  - New fields may be added without removing existing fields to maintain backward compatibility.
  - Changes to data types or constraints that do not affect existing data will be considered backward compatible.

- **Breaking vs Non-Breaking Changes**:
  - **Breaking Changes**: Removal of existing fields, changing data types that affect existing data, or altering primary key definitions.
  - **Non-Breaking Changes**: Adding new fields, changing constraints that do not affect existing data, or modifying enumerations.

## 6. Assumptions & Risks
- **Assumptions**:
  - The dataset will continue to be maintained and updated regularly.
  - All stakeholders understand the importance of data governance, especially concerning PII.

- **Risks**:
  - Potential for data quality issues if constraints are not enforced during data entry.
  - Changes in business requirements may necessitate frequent updates to the schema, leading to potential compatibility issues.
  - Mismanagement of PII could lead to compliance issues with data protection regulations. 

This data contract aims to provide a clear framework for managing the Employee dataset effectively while ensuring data integrity and compliance with relevant regulations.