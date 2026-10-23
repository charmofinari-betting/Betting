import unittest
from datetime import datetime

from log_bets import SlipParseError, TipRow, find_tip, parse_slip_market, plan, slip_offset, to_pht
from parse import Selection


class SlipMarketTest(unittest.TestCase):
    def test_1xbet_markets(self):
        cases = [
            ("1X2: W2: Botosani - UTA Arad", "Football", Selection("Handicap", "FT", "Away", -0.5)),
            ("1X2: W1: Daniel Rincon - Pedro Martinez Portero", "Tennis", Selection("Moneyline", "FT", "Home")),
            ("1X2 (2UP): W2 (2UP): Swansea City - West Ham United", "Football", Selection("Handicap", "FT", "Away", -0.5)),
            ("Handicap 1 (-8.5): Aris Thessaloniki - Burgos (Including Overtime)", "Basketball",
             Selection("Handicap", "FT", "Home", -8.5)),
            ("Asian Handicap 2 (+0.25): A - B", "Football", Selection("Handicap", "FT", "Away", 0.25)),
            ("Total Over (170.5): Bayern Munich - Virtus (Including Overtime)", "Basketball", Selection("Total", "FT", "Over", 170.5)),
            ("Total Under (2.75): A - B", "Football", Selection("Total", "FT", "Under", 2.75)),
            ("1st Half Total Over (1.5): A - B", "Football", Selection("Total", "1H", "Over", 1.5)),
            ("Individual Total 1 Over (1.5): A - B", "Football", Selection("Home team total", "FT", "Over", 1.5)),
            ("Total Under (9.5): Corners Kashima Antlers - Corners Gamba Osaka", "Football", Selection("Corners", "FT", "Under", 9.5)),
            ("Corners: Total Under (9.5)", "Football", Selection("Corners", "FT", "Under", 9.5)),
            ("Total Under (3.5): Cards Le Havre - Cards Auxerre", "Football", Selection("Cards", "FT", "Under", 3.5)),
            ("Total. Cards: Over 4.5", "Football", Selection("Cards", "FT", "Over", 4.5)),
            ("Total. Cards: Total Over (4.5)", "Football", Selection("Cards", "FT", "Over", 4.5)),
            ("Double Chance: 2X: Oldham Athletic - Accrington Stanley", "Football", Selection("Handicap", "FT", "Away", 0.5)),
            ("Double Chance: 1X: A - B", "Football", Selection("Handicap", "FT", "Home", 0.5)),
            ("Handicap: 1 (-11.5)", "Basketball", Selection("Handicap", "FT", "Home", -11.5)),
            ("Team Wins: W1", "Basketball", Selection("Moneyline", "FT", "Home")),
            ("Team Wins: Team 1 Wins", "Basketball", Selection("Moneyline", "FT", "Home")),
            ("Team Wins: Team 2 Wins", "Basketball", Selection("Moneyline", "FT", "Away")),
            ("Total: Over 2.5", "Football", Selection("Total", "FT", "Over", 2.5)),
            ("Total: Under 2.5", "Football", Selection("Total", "FT", "Under", 2.5)),
            ("Both Teams To Score - Yes: A - B", "Football", Selection("BTTS", "FT", "Yes")),
        ]
        for text, sport, want in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_slip_market(text, sport), want)

    def test_unknown_and_draw_raise(self):
        for text in ("1X2: X: A - B", "Double Chance 12: A - B", "Correct Score 2-1"):
            with self.subTest(text=text), self.assertRaises(SlipParseError):
                parse_slip_market(text, "Football")

    def test_1xbet_time_to_pht(self):
        self.assertEqual(to_pht("2026-10-08 00:00", "1xbet"), datetime(2026, 10, 8, 1, 0))


KO = datetime(2026, 10, 9, 2, 0)
TIPS = [TipRow("T-0497", KO, "Basketball", "Bayern München", "Virtus Bologna", Selection("Total", "FT", "Over", 168.5), 1.85, "", "m"),
        TipRow("T-0499", KO, "Basketball", "Bayern München", "Virtus Bologna", Selection("Total", "FT", "Over", 169.5), 1.83, "", "m"),
        TipRow("T-0436", KO, "Football", "Náutico", "Grêmio Novorizontino", Selection("Handicap", "FT", "Away", -0.5), 2.40, "", "m"),
        TipRow("T-0577", KO, "Football", "Náutico", "Grêmio Novorizontino", Selection("Handicap", "FT", "Away", 0.0), 1.87, "", "m")]


class FindTipTest(unittest.TestCase):
    def test_exact_line(self):
        t, note = find_tip(Selection("Total", "FT", "Over", 169.5), "Basketball", "Bayern Munich", "Virtus Granarolo Bologna", KO, TIPS)
        self.assertEqual((t.id, note), ("T-0499", ""))

    def test_line_moved_links_nearest(self):
        t, note = find_tip(Selection("Total", "FT", "Over", 170.5), "Basketball", "Bayern Munich", "Virtus Granarolo Bologna", KO, TIPS)
        self.assertEqual(t.id, "T-0499")
        self.assertIn("line moved", note)

    def test_w2_links_ah_minus_half_not_dnb(self):
        t, note = find_tip(Selection("Handicap", "FT", "Away", -0.5), "Football", "Clube Nautico Capibaribe", "Novorizontino", KO, TIPS)
        self.assertEqual((t.id, note), ("T-0436", ""))

    def test_team_alias_maps_book_name_to_sheet_name(self):
        sel = Selection("Handicap", "FT", "Away", -0.5)
        self.assertIsNone(find_tip(sel, "Football", "Nautico", "Novo", KO, TIPS, aliases={})[0])
        t, _ = find_tip(sel, "Football", "Nautico", "Novo", KO, TIPS,
                        aliases={"Nautico": "Clube Nautico Capibaribe", "Novo": "Novorizontino"})
        self.assertEqual(t.id, "T-0436")

    def test_other_match_or_far_kickoff(self):
        self.assertIsNone(find_tip(Selection("Total", "FT", "Over", 169.5), "Basketball", "Real Madrid", "Virtus Bologna", KO, TIPS)[0])
        far = datetime(2026, 10, 20)
        self.assertIsNone(find_tip(Selection("Total", "FT", "Over", 169.5), "Basketball", "Bayern Munich", "Virtus Bologna", far, TIPS)[0])


SLIP = {"book_slip_no": "1", "placed": "2026-10-07 18:34", "account": "1xbet PHP", "stake": 1000, "total_odds": 3.532,
        "potential": 3531.9, "opening": True, "legs": [
            {"sport": "Football", "home": "Clube Nautico Capibaribe", "away": "Novorizontino", "market": "1X2: W2: x", "odds": 1.83, "kickoff": "2026-10-09 01:00"},
            {"sport": "Basketball", "home": "Bayern Munich", "away": "Virtus Bologna", "market": "Total Over (169.5): x", "odds": 1.93, "kickoff": "2026-10-09 01:00", "status": "Win"}]}
ACCOUNTS = {"1xbet PHP": ("1xbet", "PHP")}


class PlanTest(unittest.TestCase):
    def test_ticket_legs_and_opening_line(self):
        p = plan([SLIP], TIPS, {}, 1, {"PHP": 1.0}, ACCOUNTS)
        self.assertEqual(p.problems, [])
        self.assertEqual(p.bets[0][0], "S-0001")
        self.assertEqual([l[2] for l in p.legs], ["T-0436", "T-0499"])
        self.assertEqual(p.legs[1][8], "Won")
        self.assertEqual(p.ledger[0][2:4], ["Opening balance", 1000])

    def test_placed_by_holder_keeps_pot_paolo(self):
        p = plan([dict(SLIP, placed_by="Tish")], TIPS, {}, 1, {"PHP": 1.0}, ACCOUNTS)
        self.assertEqual(p.bets[0][6:8], ["Paolo", "Tish"])

    def test_duplicate_slip_skipped(self):
        p = plan([SLIP], TIPS, {"1": "S-0007"}, 8, {"PHP": 1.0}, ACCOUNTS)
        self.assertEqual(p.bets, [])

    def test_bad_totals_and_unmatched_leg_are_problems(self):
        bad = dict(SLIP, total_odds=4.0, legs=SLIP["legs"] + [{"sport": "Football", "home": "Nobody", "away": "Else",
                                                               "market": "1X2: W1: x", "odds": 1.0, "kickoff": "2026-10-09 01:00"}])
        p = plan([bad], TIPS, {}, 1, {"PHP": 1.0}, ACCOUNTS)
        self.assertTrue(any("multiply" in x for x in p.problems))
        self.assertTrue(any("Own pick?" in x for x in p.problems))

    def test_own_pick_accepted(self):
        own = dict(SLIP, total_odds=3.532 * 1.5, potential=None,
                   legs=SLIP["legs"] + [{"sport": "Football", "home": "Nobody", "away": "Else", "market": "1X2: W1: x",
                                         "odds": 1.5, "kickoff": "2026-10-09 01:00", "own": True}])
        p = plan([own], TIPS, {}, 1, {"PHP": 1.0}, ACCOUNTS)
        self.assertEqual(p.problems, [])
        self.assertEqual(p.legs[2][3], "Yes")


    def test_slip_number_checks_and_own_key(self):
        from slip_no import learn
        accts = dict(ACCOUNTS, bet88=("bet88", "PHP"), **{"bet88 Tish": ("bet88", "PHP")})
        formats = learn([["S-1", "", "bet88"] + [""] * 16 + ["2719626337345221478"]] * 5
                        + [["S-2", "", "1xbet PHP"] + [""] * 16 + ["88399886893"]] * 5, accts)
        p = plan([dict(SLIP, book_slip_no="88399886893")], TIPS, {}, 1, {"PHP": 1.0}, accts, formats=formats)
        self.assertEqual(p.problems, [])
        p = plan([dict(SLIP, book_slip_no="8839988689")], TIPS, {}, 1, {"PHP": 1.0}, accts, formats=formats)
        self.assertTrue(any("doesn't look like a 1xbet number" in x for x in p.problems))
        p = plan([dict(SLIP, book_slip_no="2724974928796459412", account="?")], TIPS, {}, 1, {"PHP": 1.0}, accts,
                 formats=formats)
        self.assertIn("The slip number fits bet88 = bet88, bet88 Tish", p.problems[0])
        self.assertIn("Accounts: 1xbet PHP, bet88, bet88 Tish", p.problems[0])
        p = plan([dict(SLIP, book_slip_no=None)], TIPS, {}, 1, {"PHP": 1.0}, accts, formats=formats)
        self.assertEqual(p.problems, [])
        self.assertEqual(p.bets[0][10], "1xbet-php-double-1007-1834")
        self.assertTrue(any("own key 1xbet-php-double-1007-1834" in l for l in p.lines))
        p = plan([dict(SLIP, book_slip_no=None)], TIPS, {"1xbet-php-double-1007-1834": "S-0009"}, 1, {"PHP": 1.0}, accts)
        self.assertEqual(p.bets, [])


def _with_ko(*kos):
    return dict(SLIP, legs=[dict(l, kickoff=k) for l, k in zip(SLIP["legs"], kos)])


class SlipTimeZoneTest(unittest.TestCase):
    """1xbet slips show UTC+7 or PHT; the tips' known PHT kickoffs (KO = 02:00) decide."""

    def test_one_hour_earlier_means_utc7(self):
        self.assertEqual(slip_offset("1xbet", _with_ko("2026-10-09 01:00", "2026-10-09 01:00"), TIPS)[0], 7)

    def test_same_time_means_pht(self):
        off, why = slip_offset("1xbet", _with_ko("2026-10-09 02:00", "2026-10-09 02:00"), TIPS)
        self.assertEqual((off, why), (8, "2 kickoff(s) agree"))
        p = plan([dict(_with_ko("2026-10-09 02:00", "2026-10-09 02:00"), placed="2026-10-07 18:34")],
                 TIPS, {}, 1, {"PHP": 1.0}, ACCOUNTS)
        self.assertEqual(p.problems, [])
        self.assertAlmostEqual(p.bets[0][1] % 1, (18 * 60 + 34) / 1440)  # placed kept as shown, no shift

    def test_disagreeing_kickoffs_ask(self):
        off, why = slip_offset("1xbet", _with_ko("2026-10-09 01:00", "2026-10-09 02:00"), TIPS)
        self.assertEqual((off, why), (None, "kickoffs disagree"))
        p = plan([_with_ko("2026-10-09 01:00", "2026-10-09 02:00")], TIPS, {}, 1, {"PHP": 1.0}, ACCOUNTS)
        self.assertTrue(any("time zone" in pr for pr in p.problems))

    def test_no_known_kickoff_asks_and_override_wins(self):
        own = dict(SLIP, legs=[dict(l, own=True, home="Unknown FC", away="Nobody") for l in SLIP["legs"]])
        self.assertIsNone(slip_offset("1xbet", own, TIPS)[0])
        self.assertEqual(slip_offset("1xbet", dict(own, tz=8), TIPS), (8, "set on the slip"))

    def test_rescheduled_leg_ignored_when_others_agree(self):
        off, why = slip_offset("1xbet", _with_ko("2026-10-09 01:00", "2026-10-09 05:00"), TIPS)
        self.assertEqual(off, 7)
        self.assertIn("ignored", why)

    def test_other_books_unchanged(self):
        self.assertEqual(slip_offset("bet88", SLIP, TIPS), (8, ""))


if __name__ == "__main__":
    unittest.main()


class Bet88AndSystemTest(unittest.TestCase):
    def test_mswph_markets(self):
        from log_bets import parse_slip_market as p
        self.assertEqual(p("Win/Draw/Win - Regular Time: NK Varazdin", "Football", "NK Lokomotiva Zagreb", "NK Varazdin"),
                         Selection("Handicap", "FT", "Away", -0.5))
        self.assertEqual(p("Head to Head - Match: Turk Telekom", "Basketball", "Turk Telekom", "Besiktas Sompo Japan"),
                         Selection("Moneyline", "FT", "Home"))
        self.assertEqual(p("Both Teams To Score - Regular Time: Yes", "Football", "A", "B"), Selection("BTTS", "FT", "Yes"))
        self.assertEqual(p("Over/Under - Regular Time: Under 2.5,3", "Football", "A", "B"), Selection("Total", "FT", "Under", 2.75))
        self.assertEqual(p("Over/Under - Regular Time: Over 2.5", "Football", "A", "B"), Selection("Total", "FT", "Over", 2.5))
        self.assertEqual(p("Asian Handicap - First Half: Oita Trinita (0)", "Football", "Oita Trinita", "Niigata Albirex"),
                         Selection("Handicap", "1H", "Home", 0.0))
        self.assertEqual(p("Asian Handicap - Match: Niigata Albirex (-0.25)", "Football", "Oita Trinita", "Niigata Albirex"),
                         Selection("Handicap", "FT", "Away", -0.25))

    def test_solaire_spread(self):
        from log_bets import parse_slip_market as p
        self.assertEqual(p("[80:76]Live Betting Spread: Girona -4.5", "Basketball", "Girona", "Leyma Coruna"),
                         Selection("Handicap", "FT", "Home", -4.5))

    def test_solaire_moneyline_and_multis(self):
        from log_bets import parse_slip_market as p
        self.assertEqual(p("[3:0]Live Betting Moneyline: Gladiators Trier", "Basketball", "Fraport Skyliners", "Gladiators Trier"),
                         Selection("Moneyline", "FT", "Away"))
        self.assertEqual(p("FT 1x2: Barletta", "Football", "Barletta", "AZ Picerno ASD"),
                         Selection("Handicap", "FT", "Home", -0.5))
        self.assertEqual(p("FT O/U: Over 2.75", "Football", "Pescara", "Ostia Mare"),
                         Selection("Total", "FT", "Over", 2.75))
        self.assertEqual(p("FT Asian Handicap: Aris Limassol 0", "Football", "Aris Limassol", "AEK Larnaca"),
                         Selection("Handicap", "FT", "Home", 0.0))
        self.assertEqual(p("FT Spread: Crvena Zvezda +4.5", "Basketball", "KK Partizan Beograd", "Crvena Zvezda"),
                         Selection("Handicap", "FT", "Away", 4.5))
        self.assertEqual(p("FT Moneyline: Alba Berlin", "Basketball", "Alba Berlin", "Brose Bamberg"),
                         Selection("Moneyline", "FT", "Home"))
        self.assertEqual(p("Corners FT O/U: Under 9.0", "Football", "Braga", "Gil Vicente"),
                         Selection("Corners", "FT", "Under", 9.0))
        self.assertEqual(p("Cards FT O/U: Under 3.5", "Football", "Monza", "Cagliari"),
                         Selection("Cards", "FT", "Under", 3.5))
        self.assertEqual(p("FT Winner: Neel / Olmos", "Tennis", "Neel / Olmos", "Y T Cho / I-H Cho"),
                         Selection("Moneyline", "FT", "Home"))
        self.assertEqual(p("[0:0] Live Betting Winner: Catherine McNally", "Tennis", "Catherine McNally", "Sinja Kraus"),
                         Selection("Moneyline", "FT", "Home"))
        self.assertEqual(p("Tottenham: Team Total Cards O/U: Over 1.5", "Football", "Tottenham", "Coventry"),
                         Selection("Home team cards", "FT", "Over", 1.5))

    def test_bet88_markets(self):
        from log_bets import parse_slip_market as p
        self.assertEqual(p("Over/Under - Match: Over 173.5", "Basketball", "Hapoel Tel-Aviv", "Virtus Bologna"),
                         Selection("Total", "FT", "Over", 173.5))
        self.assertEqual(p("Asian Handicap Sets - Match: La Serna, Juan Manuel (+1.5)", "Tennis", "Dellien, Hugo", "La Serna, Juan Manuel"),
                         Selection("Set handicap", "FT", "Away", 1.5))
        self.assertEqual(p("Total corners over 9.5", "Football", "FC Cincinnati", "Columbus Crew"),
                         Selection("Corners", "FT", "Over", 9.5))
        self.assertEqual(p("Draw no bet Always Ready", "Football", "The Strongest", "Always Ready"),
                         Selection("Handicap", "FT", "Away", 0.0))
        self.assertEqual(p("Double chance draw or CF Rayo Majadahonda", "Football", "Real Jaen CF", "CF Rayo Majadahonda"),
                         Selection("Handicap", "FT", "Away", 0.5))
        self.assertEqual(p("Double chance Real Jaen CF or draw", "Football", "Real Jaen CF", "CF Rayo Majadahonda"),
                         Selection("Handicap", "FT", "Home", 0.5))
        self.assertEqual(p("1x2 KS Lechia Gdansk", "Football", "ZKS Stal Rzeszow", "KS Lechia Gdansk"),
                         Selection("Handicap", "FT", "Away", -0.5))
        self.assertEqual(p("Handicap (incl. overtime) BC Aris Thessaloniki (-8.5)", "Basketball",
                           "BC Aris Thessaloniki", "CB San Pablo Burgos"), Selection("Handicap", "FT", "Home", -8.5))
        self.assertEqual(p("Total under 2.5", "Football", "A", "B"), Selection("Total", "FT", "Under", 2.5))
        # bet88 tennis "Winner Surname, First"
        self.assertEqual(p("Winner Joint, Maya", "Tennis", "Sawangkaew, Mananchaya", "Joint, Maya"),
                         Selection("Moneyline", "FT", "Away"))
        # 747-live
        self.assertEqual(p("Points Handicap NB Staoueli (Wom) (-1.5)", "Basketball", "NB Staoueli (Wom)", "EL Annaba (Wom)"),
                         Selection("Handicap", "FT", "Home", -1.5))
        self.assertEqual(p("Match Winner Alibek Kachmazov", "Tennis", "Evan Zhu", "Alibek Kachmazov"),
                         Selection("Moneyline", "FT", "Away"))
        self.assertEqual(p("Total Points Over (168.5)", "Basketball", "A", "B"), Selection("Total", "FT", "Over", 168.5))
        with self.assertRaises(SlipParseError):
            p("1x2 Someone Else", "Football", "ZKS Stal Rzeszow", "KS Lechia Gdansk")

    def test_system_return_matches_bet88_potential(self):
        from log_bets import system_return
        # bet88 slip 2719626337345221478: system 3/5, ₱4,000, potential win ₱30,060.33
        self.assertAlmostEqual(system_return([1.87, 1.87, 2.10, 1.90, 2.06], 3, 4000), 30060.33, delta=0.05)

    def test_system_return_with_lost_void_and_half(self):
        from log_bets import system_return
        # 2/3 system, 300 stake (100 per double): legs won 2.0, lost, void
        self.assertEqual(system_return([2.0, 0, 1], 2, 300), 200.0)
        # half won leg factor (odds+1)/2
        self.assertEqual(system_return([2.0, 1.5, 1], 2, 300), 100 * (2.0 * 1.5 + 2.0 + 1.5))
