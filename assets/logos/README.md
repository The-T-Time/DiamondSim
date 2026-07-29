# Team Logo PNGs

Drop each team's logo here, named by its MLB team id: `{team_id}.png`.

Example: the Yankees (MLB team id 147) go in as `147.png`.

Team ids match `Team.id` in `models/team.py` / `data/teams.py`'s
`TEAM_REGISTRY` — e.g. `TEAM_REGISTRY['New York Yankees'].id == 147`.

A missing PNG is not an error — `gui/logos/`'s `get_team_logo()` just
returns `None` for that team and the GUI skips the image, so nothing
breaks before all 30 are added.
