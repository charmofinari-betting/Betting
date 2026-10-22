import json
import unittest
from pathlib import Path

from log_picks import plan, read_tsv

FIX = Path(__file__).parent / "fixtures"
VOCAB = {
    "tennis_tours": ["ATP", "Challenger", "WTA"],
    "league_sport": {"Superettan": "Football", "Euroleague": "Basketball", "SuperLiga România": "Football"},
    "league_aliases": {"SuperLiga României": "SuperLiga România"},
    "team_aliases": {"Norrkoping": "IFK Norrköping"},
}
# Existing Sheet1 rows: A ID .. L Line (only the columns plan() reads matter)
EXISTING = [
    ["T-0041", "", "Football", "Sweden", "Superettan", "IFK Norrköping vs OIF Sundsvall",
     "IFK Norrköping", "OIF Sundsvall", "Total", "FT", "Over", "3.5"],
]


class PlanTest(unittest.TestCase):
    def test_new_row_gets_next_id_and_fields(self):
        p = plan([["International", "Euroleague", "Bayern München vs Virtus Bologna", "OVER 167.5", "1.85"]], EXISTING, VOCAB)
        self.assertEqual(p.problems, [])
        self.assertEqual(p.new, [["T-0042", None, "Basketball", "International", "Euroleague",
                                  "Bayern München vs Virtus Bologna", "Bayern München", "Virtus Bologna",
                                  "Total", "FT", "Over", 167.5, "OVER 167.5", 1.85, None, None]])

    def test_duplicate_of_existing_ignores_accents_and_case(self):
        p = plan([["Sweden", "Superettan", "IFK Norrkoping vs OIF SUNDSVALL", "OVER 3.5", "2.15"]], EXISTING, VOCAB)
        self.assertEqual([d[1] for d in p.duplicates], ["T-0041"])
        self.assertEqual(p.new, [])

    def test_team_alias_makes_duplicate(self):
        p = plan([["Sweden", "Superettan", "Norrkoping vs OIF Sundsvall", "OVER 3.50", "2.15"]], EXISTING, VOCAB)
        self.assertEqual(len(p.duplicates), 1)

    def test_same_line_twice_in_batch(self):
        pick = ["International", "Euroleague", "BC Dubai vs KK Crvena zvezda", "UNDER 171.5", "1.85"]
        p = plan([pick, pick], EXISTING, VOCAB)
        self.assertEqual((len(p.new), p.duplicates[0][1]), (1, "this batch"))

    def test_different_line_same_match_is_new(self):
        p = plan([["Sweden", "Superettan", "IFK Norrköping vs OIF Sundsvall", "OVER 3.25", "1.95"]], EXISTING, VOCAB)
        self.assertEqual(len(p.new), 1)

    def test_ladder_logs_every_line_with_its_own_odds(self):
        p = plan([["Sweden", "Superettan", "Varbergs BoIS vs Helsingborgs IF", "HOME (-0.5*, 0, 0)", "2.40 / 1.70 / 1.70"]],
                 EXISTING, VOCAB)
        self.assertEqual(p.problems, [])
        self.assertEqual([(r[11], r[12], r[13]) for r in p.new], [(-0.5, "HOME -0.5*", 2.4), (0.0, "HOME 0", 1.7)])
        self.assertEqual(p.duplicates[0][1], "this batch")

    def test_ladder_line_already_logged_is_skipped(self):
        p = plan([["Sweden", "Superettan", "IFK Norrköping vs OIF Sundsvall", "OVER (3.25, 3.5*)", "1.95 / 2.15"]],
                 EXISTING, VOCAB)
        self.assertEqual(([r[12] for r in p.new], [d[1] for d in p.duplicates]), (["OVER 3.25"], ["T-0041"]))

    def test_ladder_odds_count_mismatch_is_a_problem(self):
        p = plan([["Sweden", "Superettan", "A vs B", "UNDER (2.5, 3*)", "2.45"]], EXISTING, VOCAB)
        self.assertEqual((len(p.new), len(p.problems)), (0, 1))
        self.assertIn("2 lines but 1 odds", p.problems[0][1])

    def test_league_alias_and_tennis_tour(self):
        p = plan([["Romania", "SuperLiga României", "FC Universitatea Cluj vs FC Rapid București", "AWAY 0.0", "1.96"],
                  ["Challenger", "Somewhere New, Peru", "A Player vs B Player", "ML HOME", "1.80", "2026-10-09 21:30"]],
                 EXISTING, VOCAB)
        self.assertEqual(p.problems, [])
        self.assertEqual(p.new[0][4], "SuperLiga România")
        self.assertEqual(p.new[1][2], "Tennis")
        self.assertAlmostEqual(p.new[1][1], 46304.895833, places=5)  # 9 Oct 2026 21:30 as a Sheets date

    def test_problems_are_reported_not_guessed(self):
        p = plan([["Mars", "Red League", "A vs B", "OVER 2.5", "1.9"],
                  ["Sweden", "Superettan", "No separator here", "OVER 2.5", "1.9"],
                  ["Sweden", "Superettan", "A vs B", "CORRECT SCORE 2-1", "9.0"],
                  ["Sweden", "Superettan", "A vs B", "OVER 2.5", "abc"]], EXISTING, VOCAB)
        self.assertEqual(p.new, [])
        self.assertEqual([n for n, _ in p.problems], [1, 2, 3, 4])

    def test_near_spelling_of_existing_team_warns(self):
        p = plan([["Sweden", "Superettan", "IFK Norrkopings vs OIF Sundsvall", "OVER 2.5", "1.9"]], EXISTING, VOCAB)
        self.assertEqual(len(p.new), 1)
        self.assertIn("IFK Norrköping", p.warnings[0][1])

    def test_sample_screenshots_parse_cleanly(self):
        vocab = json.loads((FIX / "vocab.json").read_text(encoding="utf-8"))
        p = plan(read_tsv(FIX / "sample_screenshots.tsv"), [], vocab)
        self.assertEqual(p.problems, [])
        self.assertEqual(len(p.new), 35)


if __name__ == "__main__":
    unittest.main()
