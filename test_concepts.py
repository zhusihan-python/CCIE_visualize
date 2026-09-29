"""concepts.py 原理卡 schema 与内容测试。"""

import unittest

import concepts


class ConceptTests(unittest.TestCase):
    def test_schema_keys(self):
        card = concepts.for_topic("encap", "cross-net")
        for key in ("title", "problem", "idea", "rules", "glossary", "scenario"):
            self.assertIn(key, card)
            self.assertTrue(card[key])

    def test_rules_and_glossary_minima(self):
        card = concepts.for_topic("encap", "cross-net")
        self.assertGreaterEqual(len(card["rules"]), 3)
        self.assertGreaterEqual(len(card["glossary"]), 3)
        for term, definition in card["glossary"]:
            self.assertTrue(term and definition)

    def test_scenario_notes_differ_and_prefixed(self):
        cross = concepts.for_topic("encap", "cross-net")
        same = concepts.for_topic("encap", "same-net")
        self.assertIn("场景看点", cross["scenario"])
        self.assertIn("场景看点", same["scenario"])
        self.assertNotEqual(cross["scenario"], same["scenario"])

    def test_unknown_scenario_falls_back(self):
        card = concepts.for_topic("encap", "bogus")
        self.assertEqual(
            card["scenario"],
            concepts.for_topic("encap", "cross-net")["scenario"])

    def test_unknown_topic_rejected(self):
        with self.assertRaises(ValueError):
            concepts.for_topic("rstp", "cross-net")

    def test_glossary_covers_standards_orgs(self):
        text = " ".join(term for term, _ in
                        concepts.for_topic("encap", "cross-net")["glossary"])
        for org in ("IEEE", "IETF", "ISO"):
            self.assertIn(org, text)

    def test_scenario_merge_does_not_pollute_static_content(self):
        concepts.for_topic("encap", "same-net")
        self.assertNotIn("scenario", concepts.ENCAPE)


class TroubleshootConceptTests(unittest.TestCase):
    def test_schema_keys(self):
        card = concepts.for_topic("troubleshoot", "cable")
        for key in ("title", "problem", "idea", "rules", "glossary", "scenario"):
            self.assertIn(key, card)
            self.assertTrue(card[key])
        self.assertGreaterEqual(len(card["rules"]), 3)
        self.assertGreaterEqual(len(card["glossary"]), 3)

    def test_scenario_notes_differ_and_prefixed(self):
        notes = [concepts.for_topic("troubleshoot", s)["scenario"]
                 for s in ("cable", "ip-config", "service")]
        for note in notes:
            self.assertIn("场景看点", note)
        self.assertEqual(len(set(notes)), 3)

    def test_unknown_scenario_falls_back_to_cable(self):
        card = concepts.for_topic("troubleshoot", "bogus")
        self.assertEqual(
            card["scenario"],
            concepts.for_topic("troubleshoot", "cable")["scenario"])


if __name__ == "__main__":
    unittest.main()
