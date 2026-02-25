# Data Contract for Employee Dataset

## 1. Overview
This document outlines the canonical schema, keys, constraints, data quality expectations, and data contract rules for the Employee dataset extracted from a CSV file. The dataset contains personal and demographic information about employees, which may include personally identifiable information (PII). The goal is to ensure data integrity, consistency, and ease of integration with other systems.

## 2. Canonical Schema

| Column Name         | Data Type   | Nullable | Description                                       |
|---------------------|-------------|----------|---------------------------------------------------|
| first_name          | STRING      | NO       | Employee's first name (PII)                       |
| last_name           | STRING      | NO       | Employee's last name (PII)                        |
| team                | STRING      | NO       | Team the employee belongs to                       |
| position            | STRING      | NO       | Job title or position of the employee             |
| height_inches       | INT         | NO       | Height of the employee in inches                  |
| weight_pounds       | INT         | NO       | Weight of the employee in pounds                  |
| age                 | FLOAT       | NO       | Age of the employee (in years)                    |

## 3. Keys & Constraints

### Primary Key
- **Composite Primary Key**: (first_name, last_name) 
  - This combination is chosen due to the uniqueness of names in the dataset, although it may not be ideal in all cases. A more robust solution would be to introduce a unique employee ID if possible.

### Foreign Keys
- No foreign keys identified in the current dataset profile.

### Constraints
- **Uniqueness**: 
  - `first_name` and `last_name` combination must be unique.
- **Range Constraints**:
  - `height_inches`: Must be between 67 and 83.
  - `weight_pounds`: Must be between 150 and 290.
  - `age`: Must be between 21 and 48 (based on the provided min and max).
- **Enums**: 
  - `team` and `position` can be defined as enumerated types if the values are known and limited.

## 4. Data Quality Expectations
- **Completeness**: All fields must be populated (0% null values).
- **Uniqueness**: No duplicate entries based on the composite key of `first_name` and `last_name`.
- **Validity**: Values must adhere to defined constraints (e.g., height, weight, age).
- **Consistency**: Data should be consistent across different datasets if integrated.

## 5. Data Contract Rules (Versioning & Evolution)

### Versioning Strategy
- Each version of the dataset will be incremented with a semantic versioning approach (MAJOR.MINOR.PATCH).
  - MAJOR: Significant changes that may break backward compatibility.
  - MINOR: Additions of new fields or non-breaking changes.
  - PATCH: Minor fixes or changes that do not affect the schema.

### Backward Compatibility
- New versions should maintain backward compatibility wherever possible. Existing fields should not be removed or renamed in a way that would break existing integrations.

### Breaking vs Non-Breaking Changes
- **Breaking Changes**:
  - Removal of existing fields.
  - Changes in data types of existing fields.
  - Renaming existing fields.
  
- **Non-Breaking Changes**:
  - Adding new fields.
  - Adding new enumerated values for existing fields.
  - Changing constraints (e.g., widening ranges) without removing existing values.

## 6. Assumptions & Risks

### Assumptions
- The dataset is complete and accurately reflects the current state of employee information.
- The uniqueness of the composite key (first_name, last_name) is sufficient for the current use case.

### Risks
- The composite primary key may lead to collisions in cases of common names, which could affect data integrity.
- Changes in data collection methods or sources may introduce inconsistencies in future data versions.
- PII data handling must comply with relevant regulations (e.g., GDPR, CCPA) to mitigate privacy risks.