"""encap.py 故事不变量测试：PDU 状态机 ground truth、步骤结构、讲解文案。

对照旧仓库 test_stp 的套路：故事步骤绝不允许偏离「真实」封装语义——
加头顺序、路由器重写次数、解封装逆序都以显式期望值断言。
"""

import json
import unittest

import encap
import generate


def tokens(step):
    return tuple(c["t"] for c in step["pdu"])


class StoryTests(unittest.TestCase):
    def setUp(self):
        self.cross = encap.simulate("cross-net")
        self.same = encap.simulate("same-net")

    def test_cross_net_chain_shape(self):
        chain = self.cross.chain
        self.assertEqual(chain.ids(), ["PC1", "SW1", "R1", "SW2", "PC2"])
        self.assertEqual([(l.a, l.b) for l in chain.links],
                         [("PC1", "SW1"), ("SW1", "R1"),
                          ("R1", "SW2"), ("SW2", "PC2")])
        by_id = {d.id: d for d in chain.devices}
        self.assertEqual(by_id["PC1"].layer_range, (1, 7))
        self.assertEqual(by_id["SW1"].layer_range, (1, 2))
        self.assertEqual(by_id["R1"].layer_range, (1, 3))
        self.assertEqual(len(by_id["R1"].interfaces), 2)

    def test_same_net_chain_shape(self):
        chain = self.same.chain
        self.assertEqual(chain.ids(), ["PC1", "SW1", "PC2"])
        self.assertNotIn("R1", chain.ids())

    def test_step_structure(self):
        for res in (self.cross, self.same):
            steps = res.steps
            self.assertEqual(steps[0]["kind"], "initial")
            self.assertEqual(steps[-1]["kind"], "final")
            ids = set(res.chain.ids())
            kinds = {"initial", "encap", "move", "process", "decap", "final"}
            for st in steps:
                self.assertIn(st["kind"], kinds)
                self.assertTrue(0 <= st["layer"] <= 7)
                self.assertIn(st["device"], ids)
                self.assertGreaterEqual(len(st["bullets"]), 2)
                self.assertTrue(st["description"])
                self.assertTrue(st["pdu_name"])
            moves = [s for s in steps if s["kind"] == "move"]
            self.assertTrue(moves)
            for mv in moves:
                self.assertEqual(len(mv["events"]), 1)
            for st in (s for s in steps if s["kind"] != "move"):
                self.assertEqual(st["events"], [])

    def test_move_steps_use_adjacent_links(self):
        for res in (self.cross, self.same):
            links = {frozenset((l.a, l.b)) for l in res.chain.links}
            for mv in (s for s in res.steps if s["kind"] == "move"):
                e = mv["events"][0]
                self.assertIn(frozenset((e["from"], e["to"])), links)

    def test_cross_net_pdu_ground_truth(self):
        expected = [
            (), ("data",), ("tcp", "data"), ("ip", "tcp", "data"),
            ("eth", "ip", "tcp", "data", "fcs"), ("bits",),
            ("eth", "ip", "tcp", "data", "fcs"), ("bits",),
            ("ip", "tcp", "data"), ("eth", "ip", "tcp", "data", "fcs"),
            ("bits",), ("eth", "ip", "tcp", "data", "fcs"), ("bits",),
            ("ip", "tcp", "data"), ("tcp", "data"), ("data",), ("data",),
        ]
        self.assertEqual(len(self.cross.steps), len(expected))
        self.assertEqual([tokens(s) for s in self.cross.steps], expected)

    def test_same_net_pdu_ground_truth(self):
        expected = [
            (), ("data",), ("tcp", "data"), ("ip", "tcp", "data"),
            ("eth", "ip", "tcp", "data", "fcs"), ("bits",),
            ("eth", "ip", "tcp", "data", "fcs"), ("bits",),
            ("ip", "tcp", "data"), ("tcp", "data"), ("data",), ("data",),
        ]
        self.assertEqual(len(self.same.steps), len(expected))
        self.assertEqual([tokens(s) for s in self.same.steps], expected)

    def test_sender_pdu_name_evolution(self):
        for res in (self.cross, self.same):
            self.assertEqual(res.sender_pdu_names,
                             ["数据 Data", "段 Segment", "包 Packet",
                              "帧 Frame", "比特 Bits"])

    def test_sender_encapsulation_order(self):
        # 发送方恰好按 L7→L4→L3→L2 各封装一次
        for res in (self.cross, self.same):
            encaps = [s for s in res.steps
                      if s["kind"] == "encap" and s["device"] == "PC1"]
            self.assertEqual([s["layer"] for s in encaps], [7, 4, 3, 2])

    def test_router_rewrites_eth_exactly_once(self):
        rewrites = [s for s in self.cross.steps
                    if s["kind"] == "encap" and s["device"] == "R1"]
        self.assertEqual(len(rewrites), 1)
        self.assertEqual(self.cross.mac_rewrites, 1)

        def chip_lines(step, t):
            return [c for c in step["pdu"] if c["t"] == t][0]["lines"]

        sw1 = next(s for s in self.cross.steps
                   if s["kind"] == "process" and s["device"] == "SW1")
        sw2 = next(s for s in self.cross.steps
                   if s["kind"] == "process" and s["device"] == "SW2")
        # 路由器前后：eth 内容改变（MAC 重写），ip 内容不变
        self.assertNotEqual(chip_lines(sw1, "eth"), chip_lines(sw2, "eth"))
        self.assertEqual(chip_lines(sw1, "ip"), chip_lines(sw2, "ip"))
        self.assertEqual(chip_lines(sw1, "ip"),
                         ["源 192.168.1.10", "目 192.168.2.10"])

    def test_same_net_eth_never_changes(self):
        all_lines = {json.dumps(c["lines"], ensure_ascii=False)
                     for s in self.same.steps for c in s["pdu"]
                     if c["t"] == "eth"}
        self.assertEqual(len(all_lines), 1)
        self.assertEqual(self.same.mac_rewrites, 0)

    def test_decapsulation_is_reverse_of_encapsulation(self):
        for res in (self.cross, self.same):
            decaps = [s for s in res.steps
                      if s["kind"] == "decap" and s["device"] == "PC2"]
            self.assertEqual([s["layer"] for s in decaps], [2, 3, 4])
            self.assertEqual([len(s["pdu"]) for s in decaps], [3, 2, 1])

    def test_narration_keywords_cross(self):
        text = " ".join(s["description"] for s in self.cross.steps)
        for kw in ("封装", "解封装", "端口", "MAC", "比特", "网关", "路由表",
                   "物数网传会表应"):
            self.assertIn(kw, text)

    def test_narration_keywords_same(self):
        text = " ".join(s["description"] for s in self.same.steps)
        for kw in ("同网段", "封装", "解封装", "端口", "MAC", "比特", "ARP",
                   "物数网传会表应"):
            self.assertIn(kw, text)

    def test_final_summaries_contrast_scenarios(self):
        self.assertIn("IP 端到端不变", self.cross.steps[-1]["description"])
        self.assertIn("MAC 每跳改写", self.cross.steps[-1]["description"])
        self.assertIn("端到端不变", self.same.steps[-1]["description"])

    def test_determinism(self):
        for scenario in encap.SCENARIOS:
            a = encap.simulate(scenario)
            b = encap.simulate(scenario)
            self.assertEqual(
                json.dumps(a.steps, ensure_ascii=False, sort_keys=True),
                json.dumps(b.steps, ensure_ascii=False, sort_keys=True))

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):
            encap.simulate("nonsense")


class DocumentTests(unittest.TestCase):
    def test_document_envelope(self):
        document, result = generate.build_document("encap", "cross-net")
        self.assertEqual(document["topic"], "encap")
        self.assertEqual(document["scenario"], "cross-net")
        self.assertEqual(document["title"], "封装与解封装 · 跨网段场景")
        self.assertIn("PC1 → SW1 → R1", document["subtitle"])
        self.assertIn(f"{len(result.steps)} 步", document["subtitle"])
        self.assertEqual(document["chain"]["devices"][0]["layer_range"], [1, 7])
        self.assertEqual(document["chain"]["links"][0],
                         {"a": "PC1", "b": "SW1"})
        self.assertIn("scenario", document["concept"])

    def test_document_determinism(self):
        a, _ = generate.build_document("encap", "same-net")
        b, _ = generate.build_document("encap", "same-net")
        self.assertEqual(json.dumps(a, sort_keys=True, ensure_ascii=False),
                         json.dumps(b, sort_keys=True, ensure_ascii=False))

    def test_unknown_topic_rejected(self):
        with self.assertRaises(ValueError):
            generate.build_document("stp", "cross-net")


if __name__ == "__main__":
    unittest.main()
