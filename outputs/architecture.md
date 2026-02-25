# Requirements Analysis

## 1. Business Goals
The primary goal is to enable the baseball team to perform comprehensive analyses on the overall MLB season. This includes evaluating player performance, team statistics, and demographic insights to enhance decision-making and strategic planning. The analysis should support various use cases, such as scouting, player development, and fan engagement.

## 2. Key Metrics
- **Player Performance Metrics**: Batting average, on-base percentage, slugging percentage, strikeouts, and home runs.
- **Team Statistics**: Wins, losses, win percentage, runs scored, and earned run average (ERA).
- **Demographic Insights**: Average age, height, and weight of players by team and position.
- **Player Availability**: Injury reports and player transactions.

## 3. Core Entities
- **Player**: Represents individual players with attributes such as name, team, position, height, weight, and age.
- **Team**: Represents the teams in the MLB, including team name and overall statistics.
- **Game**: Represents individual games played, including date, teams involved, and scores.
- **Season**: Represents the overall season context, including start and end dates, and season statistics.

## 4. Data Sources
- **Player Dataset**: Contains player information (first name, last name, team, position, height, weight, age).
- **Game Dataset**: Contains game results, including teams, scores, and dates.
- **Team Dataset**: Contains aggregated team statistics and performance metrics.
- **Injury Reports**: Contains data on player injuries and availability.

## 5. Data Granularity
- **Player Level**: Data should be captured at the individual player level for detailed analysis.
- **Game Level**: Each game should be recorded with results and statistics for performance tracking.
- **Season Level**: Aggregated data should be available for the entire season to analyze trends and overall performance.

## 6. Assumptions & Open Questions
### Assumptions
- The player dataset is complete and accurately reflects the current roster of players.
- The composite key of (first_name, last_name) will sufficiently identify players without significant collisions.
- Data will be collected and updated regularly to maintain freshness and relevance for analysis.

### Open Questions
- What is the frequency of data updates for player statistics and game results?
- Are there any additional data sources or external APIs that should be integrated for richer analysis?
- How will PII data be handled in compliance with relevant regulations, and what measures are in place for data security?
- What specific analytical tools or platforms will be used for data visualization and reporting?