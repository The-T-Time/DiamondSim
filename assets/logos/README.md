# Team Logo PNGs

Drop each team's logo here, named by its MLB team id: `{team_id}.png`.

Example: the Yankees (MLB team id 147) go in as `147.png`.

Team ids match `Team.id` in `models/team.py` / `data/teams.py`'s
`TEAM_REGISTRY` — e.g. `TEAM_REGISTRY['New York Yankees'].id == 147`.

A missing PNG is not an error — `gui/logos/`'s `get_team_logo()` just
returns `None` for that team and the GUI skips the image, so nothing
breaks before all 30 are added.

## Team ID reference

| File          | Team                   | Division    |
|---------------|------------------------|-------------|
| `147.png`     | New York Yankees       | AL East     |
| `139.png`     | Tampa Bay Rays         | AL East     |
| `141.png`     | Toronto Blue Jays      | AL East     |
| `110.png`     | Baltimore Orioles      | AL East     |
| `111.png`     | Boston Red Sox         | AL East     |
| `145.png`     | Chicago White Sox      | AL Central  |
| `114.png`     | Cleveland Guardians    | AL Central  |
| `142.png`     | Minnesota Twins        | AL Central  |
| `116.png`     | Detroit Tigers         | AL Central  |
| `118.png`     | Kansas City Royals     | AL Central  |
| `136.png`     | Seattle Mariners       | AL West     |
| `133.png`     | Athletics              | AL West     |
| `140.png`     | Texas Rangers          | AL West     |
| `117.png`     | Houston Astros         | AL West     |
| `108.png`     | Los Angeles Angels     | AL West     |
| `144.png`     | Atlanta Braves         | NL East     |
| `143.png`     | Philadelphia Phillies  | NL East     |
| `146.png`     | Miami Marlins          | NL East     |
| `120.png`     | Washington Nationals   | NL East     |
| `121.png`     | New York Mets          | NL East     |
| `158.png`     | Milwaukee Brewers      | NL Central  |
| `138.png`     | St. Louis Cardinals    | NL Central  |
| `112.png`     | Chicago Cubs           | NL Central  |
| `134.png`     | Pittsburgh Pirates     | NL Central  |
| `113.png`     | Cincinnati Reds        | NL Central  |
| `119.png`     | Los Angeles Dodgers    | NL West     |
| `135.png`     | San Diego Padres       | NL West     |
| `109.png`     | Arizona Diamondbacks   | NL West     |
| `137.png`     | San Francisco Giants   | NL West     |
| `115.png`     | Colorado Rockies       | NL West     |

This table is generated from `data/teams.py`'s `_RAW_TEAM_DATA` — if a
team's id ever needs to change, update it there first and mirror the
change here.

