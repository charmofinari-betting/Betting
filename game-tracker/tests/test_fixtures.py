import unittest

from fixtures import Game, match, name_score


def g(home, away, sport="Football", ko=46304.5, gid=1):
    return Game(sport, gid, home, away, ko, "L", "C", "NS", None, None, None, None)


class NameScoreTest(unittest.TestCase):
    def test_short_api_names(self):
        for sheet, api in [("Kashima Antlers", "Kashima"), ("BC Dubai", "Dubai"), ("Náutico", "Nautico Recife"),
                           ("Grêmio Novorizontino", "Novorizontino"), ("HJK", "HJK Helsinki"),
                           ("KK Crvena zvezda", "Crvena Zvezda Meridianbet"), ("SK Slavia Praha B", "Slavia Praha II")]:
            with self.subTest(sheet=sheet):
                self.assertGreaterEqual(name_score(sheet, api), 0.8)

    def test_squad_markers_must_agree(self):
        self.assertEqual(name_score("Slavia Praha", "Slavia Praha II"), 0.0)
        self.assertEqual(name_score("Arsenal", "Arsenal W"), 0.0)
        self.assertEqual(name_score("Barcelona U19", "Barcelona"), 0.0)
        self.assertGreaterEqual(name_score("Arsenal Women", "Arsenal W"), 0.8)

    def test_short_shared_word_is_not_enough(self):
        self.assertLess(name_score("Ark United", "Ark Rovers"), 0.8)


class MatchTest(unittest.TestCase):
    def test_sure_check_none(self):
        pool = [g("Kashima", "Gamba Osaka"), g("Nomme United II", "FCI Levadia II", gid=2)]
        self.assertEqual(match("Football", "Kashima Antlers", "Gamba Osaka", pool)[1], "sure")
        self.assertEqual(match("Football", "Made Up United", "Nobody City", pool), (None, None))

    def test_wrong_sport_or_far_kickoff_excluded(self):
        pool = [g("Kashima", "Gamba Osaka", sport="Basketball"), g("Kashima", "Gamba Osaka", ko=46305.5, gid=2)]
        self.assertEqual(match("Football", "Kashima Antlers", "Gamba Osaka", pool, kickoff=46304.5), (None, None))

    def test_two_equally_good_candidates_need_checking(self):
        pool = [g("Real Sociedad", "Mallorca"), g("Real Sociedad", "Mallorca", gid=2)]
        self.assertEqual(match("Football", "Real Sociedad", "Mallorca", pool)[1], "check")

    def test_confirmed_alias_wins(self):
        pool = [g("Crvena Zvezda Meridianbet", "Partizan")]
        self.assertEqual(match("Football", "Red Star", "Partizan", pool,
                               aliases={"Red Star": "Crvena Zvezda Meridianbet"})[1], "sure")


if __name__ == "__main__":
    unittest.main()
