# ==============================================================================
# tests/test_player_tab_filters.py
#
# Player Tab.
# Covers gui/player_tab/filters.py's filter_rows — pure logic, no Tk.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import importlib.util
import pathlib
import unittest

#gui/player_tab/filters.py has zero Tk dependency itself, but a normal
#`from gui.player_tab.filters import ...` still executes gui/player_tab/
#__init__.py first (which imports tab.py, which needs tkinter — not
#installed in this environment). Loading the file directly via importlib
#skips that package-init chain entirely, so this pure logic is still
#testable without a display.
_FILTERS_PATH = pathlib.Path(__file__).resolve().parent.parent / 'gui' / 'player_tab' / 'filters.py'
_spec = importlib.util.spec_from_file_location('player_tab_filters', _FILTERS_PATH)
_filters = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_filters)
filter_rows = _filters.filter_rows

ROWS = [
    {'name': 'Shohei Ohtani', 'team': 'Los Angeles Dodgers', 'league': 'NL', 'div': 'NL West'},
    {'name': 'Aaron Judge', 'team': 'New York Yankees', 'league': 'AL', 'div': 'AL East'},
    {'name': 'Corbin Burnes', 'team': 'Arizona Diamondbacks', 'league': 'NL', 'div': 'NL West'},
    {'name': 'Gerrit Cole', 'team': 'New York Yankees', 'league': 'AL', 'div': 'AL East'},
]


class TestFilterRows(unittest.TestCase):
    def test_no_filters_returns_everything(self) -> None:
        self.assertEqual(len(filter_rows(ROWS)), 4)

    def test_league_filter(self) -> None:
        result = filter_rows(ROWS, league='AL')
        self.assertEqual({r['name'] for r in result}, {'Aaron Judge', 'Gerrit Cole'})

    def test_division_filter(self) -> None:
        result = filter_rows(ROWS, division='NL West')
        self.assertEqual({r['name'] for r in result}, {'Shohei Ohtani', 'Corbin Burnes'})

    def test_team_filter(self) -> None:
        result = filter_rows(ROWS, team='New York Yankees')
        self.assertEqual({r['name'] for r in result}, {'Aaron Judge', 'Gerrit Cole'})

    def test_search_is_case_insensitive_substring(self) -> None:
        result = filter_rows(ROWS, search='judge')
        self.assertEqual([r['name'] for r in result], ['Aaron Judge'])

    def test_filters_combine_with_and_logic(self) -> None:
        result = filter_rows(ROWS, league='AL', team='New York Yankees', search='cole')
        self.assertEqual([r['name'] for r in result], ['Gerrit Cole'])

    def test_all_filters_at_default_is_all_of_mlb(self) -> None:
        result = filter_rows(ROWS, league='All', division='All', team='All', search='')
        self.assertEqual(len(result), 4)

    def test_no_match_returns_empty(self) -> None:
        result = filter_rows(ROWS, search='nonexistent player xyz')
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
