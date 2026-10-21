import csv
import unittest
from pathlib import Path

from parse import MARKETS, PERIODS, SIDES, ParseError, Selection, market_detail, parse_selection

FIXTURE = Path(__file__).parent / "fixtures" / "sheet_selections.tsv"

# Rows the old sheet knowingly mislabelled as "Other"; the new labels are intended.
RECLASSIFIED = {"Other": {"Corners Under", "1st-half spread"}}


class ExamplesTest(unittest.TestCase):
    def test_examples(self):
        cases = {
            "AWAY -0.25": Selection("Handicap", "FT", "Away", -0.25),
            "HOME 0.0": Selection("Handicap", "FT", "Home", 0.0),
            "HT HOME -4.5": Selection("Handicap", "1H", "Home", -4.5),
            "OVER 167.5": Selection("Total", "FT", "Over", 167.5),
            "OVER 1.5 FH": Selection("Total", "1H", "Over", 1.5),
            "HT OVER 1.0": Selection("Total", "1H", "Over", 1.0),
            "UNDER 2.75": Selection("Total", "FT", "Under", 2.75),
            "AWAY TEAM OVER 0.5 FH": Selection("Away team total", "1H", "Over", 0.5),
            "HOME TEAM UNDER 0.5": Selection("Home team total", "FT", "Under", 0.5),
            "ML HOME": Selection("Moneyline", "FT", "Home"),
            "AWAY ML": Selection("Moneyline", "FT", "Away"),
            "BTTS YES 2H": Selection("BTTS", "2H", "Yes"),
            "BTTS NO": Selection("BTTS", "FT", "No"),
            "CORNERS UNDER 9.5": Selection("Corners", "FT", "Under", 9.5),
            "CARDS UNDER 4.5": Selection("Cards", "FT", "Under", 4.5),
            "CARDS HOME OVER 1.5": Selection("Home team cards", "FT", "Over", 1.5),
            "CARDS AWAY UNDER 2.5": Selection("Away team cards", "FT", "Under", 2.5),
            "CARDS AWAY -0.5": Selection("Cards handicap", "FT", "Away", -0.5),
            "CARDS HOME 0.5": Selection("Cards handicap", "FT", "Home", 0.5),
            "CORNERS HOME -2.5": Selection("Corners handicap", "FT", "Home", -2.5),
            "Set Handicap +1.5 Home": Selection("Set handicap", "FT", "Home", 1.5),
            "SET HANDICAP -1.5 AWAY": Selection("Set handicap", "FT", "Away", -1.5),
            "HTFT HOME/HOME": Selection("HT/FT", "FT", "Home"),
            "HTFT AWAY/AWAY": Selection("HT/FT", "FT", "Away"),
            "AWAY TEAM TO WIN EITHER HALF": Selection("Win either half", "FT", "Away"),
            "BOTH HALVES OVER 1.5": Selection("Both halves over", "FT", "Over", 1.5),
            "  away   -0.5 ": Selection("Handicap", "FT", "Away", -0.5),
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_selection(text), want)

    def test_rejects_unknown(self):
        for text in ("DRAW", "OVER", "HOME -", "CORRECT SCORE 2-1", ""):
            with self.subTest(text=text), self.assertRaises(ParseError):
                parse_selection(text)


class SheetRowsTest(unittest.TestCase):
    """Every selection already in the sheet parses, stays inside the vocabulary,
    and gets the same Dashboard label as the old formulas (bar known fixes)."""

    def test_all_sheet_rows(self):
        rows = list(csv.DictReader(FIXTURE.open(encoding="utf-8"), delimiter="\t"))
        self.assertGreater(len(rows), 600)
        changed = []
        for r in rows:
            with self.subTest(selection=r["selection"]):
                sel = parse_selection(r["selection"])
                self.assertIn(sel.market, MARKETS)
                self.assertIn(sel.period, PERIODS)
                self.assertIn(sel.side, SIDES)
                new = market_detail(sel, r["sport"])
                if new != r["old_label"]:
                    self.assertIn(new, RECLASSIFIED.get(r["old_label"], set()),
                                  f"{r['selection']} ({r['sport']}): {r['old_label']} -> {new}")
                    changed.append(new)
        self.assertEqual(changed.count("Corners Under"), 19)
        self.assertEqual(changed.count("1st-half spread"), 1)


if __name__ == "__main__":
    unittest.main()
