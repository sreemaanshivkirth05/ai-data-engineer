# Data Contract for Employee Dataset

## 1. Overview
This document outlines the canonical schema, keys, constraints, data quality expectations, and versioning strategy for the Employee dataset extracted from a CSV file. The dataset contains personal and professional information about employees, including their names, team affiliations, positions, physical attributes, and age.

## 2. Canonical Schema

| Column Name         | Data Type   | Nullable | Description                                      |
|---------------------|-------------|----------|--------------------------------------------------|
| first_name          | STRING      | NO       | The first name of the employee (PII)            |
| last_name           | STRING      | NO       | The last name of the employee (PII)             |
| team                | STRING      | NO       | The team the employee belongs to                 |
| position            | STRING      | NO       | The job position of the employee                 |
| height_inches       | INT         | NO       | The height of the employee in inches             |
| weight_pounds       | INT         | NO       | The weight of the employee in pounds             |
| age                 | FLOAT       | NO       | The age of the employee                           |

## 3. Keys & Constraints

### Primary Key
- **Composite Key**: (first_name, last_name, age) - This combination is unique enough to serve as a primary key, given the uniqueness of names and age.

### Foreign Keys
- None identified in the current dataset.

### Constraints
- **Uniqueness**: 
  - (first_name, last_name, age) must be unique.
- **Range Constraints**:
  - `height_inches`: Must be between 67 and 83.
  - `weight_pounds`: Must be between 150 and 290.
  - `age`: Must be between 21 and 48 (rounded from float).
- **Enumeration**:
  - `team`: Should be one of the predefined team names (30 unique values).
  - `position`: Should be one of the predefined job positions (9 unique values).

## 4. Data Quality Expectations
- **Completeness**: All fields must be populated with no null values (0% null count).
- **Uniqueness**: The primary key must enforce uniqueness across the dataset.
- **Accuracy**: Data should be validated against known ranges and enumerations.
- **Consistency**: Data types must be adhered to as defined in the schema.

## 5. Data Contract Rules (Versioning & Evolution)

### Versioning Strategy
- Use semantic versioning (MAJOR.MINOR.PATCH):
  - MAJOR: Breaking changes (e.g., changing data types, removing fields).
  - MINOR: Non-breaking changes that add new fields or enumerations.
  - PATCH: Non-breaking changes that fix issues or improve documentation.

### Backward Compatibility
- New versions must maintain backward compatibility for existing consumers. For example, adding new optional fields should not affect existing data processing.

### Breaking vs Non-Breaking Changes
- **Breaking Changes**:
  - Changing the data type of an existing field.
  - Removing existing fields from the schema.
- **Non-Breaking Changes**:
  - Adding new fields to the schema.
  - Expanding the range of acceptable values for existing fields.
  - Modifying constraints (e.g., adding new enumerated values).

## 6. Assumptions & Risks
### Assumptions
- The dataset will be consistently updated and maintained.
- Consumers of the dataset will adhere to the defined schema and constraints.
- PII data will be handled according to applicable data protection regulations.

### Risks
- Changes in the dataset structure may lead to breaking changes for existing consumers.
- Inaccurate data entry could lead to violations of uniqueness and range constraints.
- Potential exposure of PII if not properly managed and secured. 

This data contract serves as a guideline to ensure the integrity and usability of the Employee dataset in production environments.