# Data Contract for Population Demographics Dataset

## 1. Overview
This document outlines the canonical schema, keys, constraints, data quality expectations, and data contract rules for the Population Demographics dataset. The dataset contains demographic information at the tract level, including population counts, income statistics, and employment data.

## 2. Canonical Schema

| Column Name           | Data Type   | Nullable | Description                                           |
|----------------------|-------------|----------|-------------------------------------------------------|
| TractId              | INT         | NO       | Unique identifier for each tract                      |
| State                | STRING      | NO       | State where the tract is located                      |
| County               | STRING      | NO       | County where the tract is located                     |
| TotalPop             | INT         | NO       | Total population in the tract                          |
| Men                  | INT         | NO       | Number of men in the tract                             |
| Women                | INT         | NO       | Number of women in the tract                           |
| Hispanic             | FLOAT       | YES      | Percentage of Hispanic population                      |
| White                | FLOAT       | YES      | Percentage of White population                         |
| Black                | FLOAT       | YES      | Percentage of Black population                         |
| Native               | FLOAT       | YES      | Percentage of Native American population               |
| Asian                | FLOAT       | YES      | Percentage of Asian population                         |
| Pacific              | FLOAT       | YES      | Percentage of Pacific Islander population              |
| VotingAgeCitizen     | INT         | NO       | Number of voting-age citizens in the tract            |
| Income               | FLOAT       | YES      | Median income in the tract                            |
| IncomeErr            | FLOAT       | YES      | Error margin for median income                         |
| IncomePerCap         | FLOAT       | YES      | Per capita income in the tract                        |
| IncomePerCapErr      | FLOAT       | YES      | Error margin for per capita income                     |
| Poverty              | FLOAT       | YES      | Percentage of population living in poverty            |
| ChildPoverty         | FLOAT       | YES      | Percentage of children living in poverty              |
| Professional         | FLOAT       | YES      | Percentage of population in professional jobs         |
| Service              | FLOAT       | YES      | Percentage of population in service jobs              |
| Office               | FLOAT       | YES      | Percentage of population in office jobs               |
| Construction         | FLOAT       | YES      | Percentage of population in construction jobs         |
| Production           | FLOAT       | YES      | Percentage of population in production jobs           |
| Drive                | FLOAT       | YES      | Percentage of population driving to work              |
| Carpool              | FLOAT       | YES      | Percentage of population carpooling to work           |
| Transit              | FLOAT       | YES      | Percentage of population using public transit         |
| Walk                 | FLOAT       | YES      | Percentage of population walking to work              |
| OtherTransp          | FLOAT       | YES      | Percentage of population using other transportation    |
| WorkAtHome           | FLOAT       | YES      | Percentage of population working from home             |
| MeanCommute          | FLOAT       | YES      | Mean commute time in minutes                          |
| Employed             | INT         | NO       | Number of employed individuals in the tract           |
| PrivateWork          | FLOAT       | YES      | Percentage of employed in private sector              |
| PublicWork           | FLOAT       | YES      | Percentage of employed in public sector               |
| SelfEmployed         | FLOAT       | YES      | Percentage of self-employed individuals               |
| FamilyWork           | FLOAT       | YES      | Percentage of family workers                           |
| Unemployment         | FLOAT       | YES      | Percentage of unemployed individuals                   |

## 3. Keys & Constraints
- **Primary Key**: 
  - `TractId`
  
- **Constraints**:
  - `TotalPop`, `Men`, `Women`, `VotingAgeCitizen`, `Employed`: Must be non-negative integers.
  - `Hispanic`, `White`, `Black`, `Native`, `Asian`, `Pacific`, `Poverty`, `ChildPoverty`, `Professional`, `Service`, `Office`, `Construction`, `Production`, `Drive`, `Carpool`, `Transit`, `Walk`, `OtherTransp`, `WorkAtHome`, `PrivateWork`, `PublicWork`, `SelfEmployed`, `FamilyWork`, `Unemployment`: Must be percentages (0.0 to 100.0).
  - `Income`, `IncomeErr`, `IncomePerCap`, `IncomePerCapErr`: Must be non-negative floats.

## 4. Data Quality Expectations
- **Completeness**: All rows must contain values for `TractId`, `State`, `County`, `TotalPop`, `Men`, `Women`, `VotingAgeCitizen`, and `Employed`.
- **Accuracy**: Data should be validated against authoritative sources for demographic statistics.
- **Consistency**: Ensure that percentage fields sum up to 100% where applicable (e.g., racial demographics).
- **Timeliness**: Data should be updated periodically to reflect the most current demographic information.

## 5. Data Contract Rules (Versioning & Evolution)
- **Versioning Strategy**: 
  - Use semantic versioning (MAJOR.MINOR.PATCH).
  - Increment MAJOR version for breaking changes, MINOR for non-breaking changes, and PATCH for bug fixes.

- **Backward Compatibility**: 
  - New versions should maintain backward compatibility where possible. Consumers of the data should not break with the introduction of new fields or changes in data types unless a MAJOR version change occurs.

- **Breaking vs Non-Breaking Changes**:
  - **Breaking Changes**: Changes to existing field types, removal of fields, or changes to primary keys.
  - **Non-Breaking Changes**: Addition of new fields, changes to field descriptions, or updates to constraints that do not affect existing data.

## 6. Assumptions & Risks
- **Assumptions**:
  - Data sources are reliable and regularly updated.
  - Consumers of the data will adhere to the defined schema and constraints.

- **Risks**:
  - Changes in data collection methods may affect data quality and consistency.
  - External factors (e.g., changes in demographic reporting standards) may necessitate schema adjustments.
  - Potential for data privacy issues if any fields are misclassified as PII in future versions.