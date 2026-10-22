import unittest

from log_bets import leg_selection, parse_slip_market, plan
from parse import Selection
from slip_check import check_leg, wording_of
from vocab import VocabError, from_rows, parse_wording, rows_from_json

ROWS = [
    ["slip wording", "msw.ph: ~/~ - regular time: ~ #,#", "Total FT", "split"],
    ["slip wording", "msw.ph: ~/~ - regular time: ~ #", "Total FT", ""],
    ["slip wording", "msw.ph: win/draw/win - regular time: @", "Handicap FT", "sport=Football, line=-0.5"],
    ["slip wording", "msw.ph: win/draw/win - regular time: @", "Moneyline FT", ""],
    ["slip wording", "1xbet: handicap # (#): @ (including overtime)", "Handicap FT", ""],
    ["slip wording", "Solaire: @: team total cards o/u: ~ #", "Team cards FT", ""],
    ["team alias", "Ekenas", "EIF", ""],
]
VOCAB = from_rows(ROWS)
WORDS = VOCAB["slip_wordings"]


def leg(market, sel, sport="Football", home="Oita Trinita", away="Kofu", **kw):
    return dict(market=market, sport=sport, home=home, away=away, sel=sel, **kw)


def sel(market, period, side, line=None):
    return {"market": market, "period": period, "side": side, "line": line}


class WordingTest(unittest.TestCase):
    def test_masks_teams_numbers_and_sides(self):
        self.assertEqual(wording_of("Over/Under - Regular Time: Under 2.5,3"), "~/~ - regular time: ~ #,#")
        self.assertEqual(wording_of("Handicap 1 (-8.5): Aris Thessaloniki - Burgos (Including Overtime)"),
                         "handicap # (#): @ (including overtime)")
        self.assertEqual(wording_of("1X2: W2: Brentford - Liverpool"), "#x#: w~: @")
        self.assertEqual(wording_of("[80:76]Live Betting Spread: Girona -4.5"), "live betting spread: @ #")
        self.assertEqual(wording_of("1X2 (2UP): W1 (2UP): Brentford - Liverpool"), "#x# (#up): w~ (#up): @")
        self.assertEqual(wording_of("1st Set - Winner Joint, Maya"), "#st set - winner @")

    def test_same_wording_for_any_match(self):
        self.assertEqual(wording_of("Win/Draw/Win - Regular Time: FC Tokyo"),
                         wording_of("Win/Draw/Win - Regular Time: Oita Trinita"))


class VocabTest(unittest.TestCase):
    def test_rows_load_by_kind(self):
        self.assertEqual(VOCAB["team_aliases"], {"Ekenas": "EIF"})
        self.assertEqual(len(WORDS["msw.ph: win/draw/win - regular time: @"]), 2)

    def test_bad_meaning_or_flag_refused(self):
        with self.assertRaises(VocabError):
            parse_wording("Goals FT", "")
        with self.assertRaises(VocabError):
            parse_wording("Total FT", "maybe")

    def test_json_round_trip(self):
        v = {"league_sport": {"Superettan": "Football"}, "league_aliases": {}, "team_aliases": {"A": "B"},
             "api_team_aliases": {"C": "D"}, "tennis_tours": ["ATP"]}
        back = from_rows(rows_from_json(v))
        for k, val in v.items():
            self.assertEqual(back[k], val)


class CheckLegTest(unittest.TestCase):
    def check(self, l, book="msw.ph"):
        return check_leg(l, book, WORDS, parse_slip_market)

    def test_clean_split_total(self):
        s, probs = self.check(leg("Over/Under - Regular Time: Under 2.5,3", sel("Total", "FT", "Under", 2.75)))
        self.assertEqual(probs, [])
        self.assertEqual(s, Selection("Total", "FT", "Under", 2.75))

    def test_wrong_split_line(self):
        _, probs = self.check(leg("Over/Under - Regular Time: Under 2.5,3", sel("Total", "FT", "Under", 2.5)))
        self.assertTrue(any("split line" in p for p in probs))

    def test_side_not_on_text(self):
        _, probs = self.check(leg("Over/Under - Regular Time: Under 2.5", sel("Total", "FT", "Over", 2.5)))
        self.assertTrue(any("doesn't say Over" in p for p in probs))

    def test_football_1x2_fixed_line_and_team_side(self):
        ok = leg("Win/Draw/Win - Regular Time: Oita Trinita", sel("Handicap", "FT", "Home", -0.5))
        self.assertEqual(self.check(ok)[1], [])
        _, probs = self.check(dict(ok, sel=sel("Handicap", "FT", "Away", -0.5)))
        self.assertTrue(any("points to Home" in p for p in probs))
        _, probs = self.check(dict(ok, sel=sel("Handicap", "FT", "Home", 0.0)))
        self.assertTrue(any("fixes the line" in p for p in probs))

    def test_same_wording_basketball_is_moneyline(self):
        l = leg("Win/Draw/Win - Regular Time: Oita Trinita", sel("Moneyline", "FT", "Home"), sport="Basketball")
        self.assertEqual(self.check(l)[1], [])

    def test_line_sign_must_match(self):
        l = leg("Handicap 1 (-8.5): Aris - Burgos (Including Overtime)", sel("Handicap", "FT", "Home", 8.5),
                sport="Basketball", home="Aris", away="Burgos")
        _, probs = self.check(l, "1xbet")
        self.assertTrue(any("not on the slip" in p for p in probs))

    def test_new_wording_is_a_problem(self):
        _, probs = self.check(leg("Asian Handicap - Match: Oita Trinita (0)", sel("Handicap", "FT", "Home", 0.0)))
        self.assertTrue(probs[0].startswith("NEW WORDING 'msw.ph: asian handicap - match: @ (#)'"))

    def test_bad_shape(self):
        _, probs = self.check(leg("Over/Under - Regular Time: Under 2.5", sel("Total", "FT", "Home", 2.5)))
        self.assertTrue(any("doesn't fit Total" in p for p in probs))
        _, probs = self.check(leg("Over/Under - Regular Time: Under 2.6", sel("Total", "FT", "Under", 2.6)))
        self.assertTrue(any("steps of 0.25" in p for p in probs))

    def test_team_cards_side_from_named_team(self):
        l = leg("Tottenham: Team Total Cards O/U: Over 1.5", sel("Home team cards", "FT", "Over", 1.5),
                home="Tottenham", away="Coventry")
        self.assertEqual(self.check(l, "Solaire")[1], [])
        _, probs = self.check(dict(l, sel=sel("Away team cards", "FT", "Over", 1.5)), "Solaire")
        self.assertTrue(any("names the home team" in p for p in probs))

    def test_old_parser_disagreement_flagged(self):
        def old(*_):
            return Selection("Total", "FT", "Under", 3.0)
        _, probs = check_leg(leg("Over/Under - Regular Time: Under 2.5,3", sel("Total", "FT", "Under", 2.75)),
                             "msw.ph", WORDS, old)
        self.assertTrue(any(p.startswith("old parser reads") for p in probs))

    def test_own_pick_needs_no_sel(self):
        self.assertEqual(leg_selection({"market": "1X2: X: A - B", "sport": "Football", "home": "A", "away": "B",
                                        "own": True}, "1xbet", WORDS), (None, []))

    def test_missing_sel_on_tip_leg(self):
        _, probs = leg_selection({"market": "Over/Under - Regular Time: Under 2.5", "sport": "Football",
                                  "home": "A", "away": "B"}, "msw.ph", WORDS)
        self.assertTrue(probs and "no \"sel\"" in probs[0])


class PlanWithVocabTest(unittest.TestCase):
    def test_new_wording_blocks_the_ticket(self):
        slip = {"book_slip_no": "9", "placed": "2026-10-20 12:00", "account": "msw.ph Pat", "stake": 100,
                "total_odds": 1.9, "potential": 190, "legs": [
                    leg("Asian Handicap - Match: Oita Trinita (0)", sel("Handicap", "FT", "Home", 0.0),
                        odds=1.9, kickoff="2026-10-21 12:00", own=False)]}
        p = plan([slip], [], {}, 1, {"PHP": 1.0}, {"msw.ph Pat": ("msw.ph", "PHP")}, VOCAB)
        self.assertTrue(any("NEW WORDING" in pr for pr in p.problems))


if __name__ == "__main__":
    unittest.main()
