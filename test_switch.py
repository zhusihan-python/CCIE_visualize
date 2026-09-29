"""交换机故事不变量：分镜 ground truth、泛洪不回入口、学习时序、老化生命周期。"""

import unittest

import switch

LEARN_PHASES_EXPECTED = [
    "—",
    "ICMP 帧 · 构造",
    "学习 · MAC1→g0/1",
    "查表 · 未知单播",
    "泛洪 · 除入口外",
    "PC3 · 丢弃",
    "PC2 · 收下并回应",
    "学习 · MAC2→g0/2",
    "查表 · 已知单播",
    "精准转发",
    "ping 通 · 表 2 行",
    "ARP 广播 · 构造",
    "刷新 · 广播判定",
    "泛洪 · 广播帧",
    "认领与沉默",
    "应答 · 精准回程",
    "—",
]

LEARN_KINDS_EXPECTED = [
    "initial",                                    # 0
    "process", "process", "process",              # 1-3 构造/学习/查表
    "move",                                       # 4 泛洪
    "process", "process", "process",              # 5-7 丢弃/回应/学习
    "process",                                    # 8 查表命中
    "move",                                       # 9 精准转发
    "process", "process", "process",              # 10-12 ping通/广播构造/刷新
    "move",                                       # 13 泛洪（广播）
    "process",                                    # 14 认领与沉默
    "move",                                       # 15 应答精准回程
    "final",                                      # 16
]

AGING_PHASES_EXPECTED = [
    "—",
    "⏩ 老化计时",
    "⏩ 老化计时",
    "归零 · 表项删除",
    "PC1 再 ping",
    "学习+未知单播",
    "泛洪 · 除入口外",
    "PC2 · 收下并回应",
    "重学习 · 命中",
    "精准转发",
    "—",
]

IDS = ("SW1", "PC1", "PC2", "PC3")


class SwitchLearnTests(unittest.TestCase):
    def setUp(self):
        self.result = switch.simulate("learn")
        self.steps = self.result.steps

    def test_step_count_and_phases(self):
        self.assertEqual(len(self.steps), 17)
        self.assertEqual(self.result.phase_names, LEARN_PHASES_EXPECTED)

    def test_kind_sequence(self):
        self.assertEqual([s["kind"] for s in self.steps], LEARN_KINDS_EXPECTED)

    def test_layers_contract(self):
        for i, s in enumerate(self.steps):
            self.assertIsInstance(s["layer"], int, f"step {i}")
            if s["kind"] in ("initial", "final"):
                self.assertEqual(s["layer"], 0, f"step {i}")
            elif s["kind"] == "move":
                self.assertEqual(s["layer"], 1, f"step {i}")
            else:
                self.assertTrue(1 <= s["layer"] <= 7, f"step {i}")
        for i in (1, 10):                    # PC1 构造 ICMP / ping 统计 = L3
            self.assertEqual(self.steps[i]["layer"], 3, f"step {i}")
        for i in (2, 3, 5, 6, 7, 8, 11, 12, 14):   # 交换机/收发判定步 = L2
            self.assertEqual(self.steps[i]["layer"], 2, f"step {i}")

    def test_floods_never_back_to_ingress(self):
        """泛洪恰两步（未知单播 + 广播帧），均只发往 PC2/PC3——
        事件集绝不含 SW1→PC1（泛洪第一条铁律：不回入口）。"""
        self.assertEqual(self.result.flood_steps, [4, 13])
        for i in (4, 13):
            events = self.steps[i]["events"]
            self.assertEqual(len(events), 2, f"step {i}")
            self.assertEqual({(e["from"], e["to"]) for e in events},
                             {("SW1", "PC2"), ("SW1", "PC3")}, f"step {i}")
            for e in events:
                self.assertEqual(e["kind"], "frame")
        self.assertEqual(self.steps[4]["events"][0]["hue"], "icmp")
        self.assertEqual(self.steps[13]["events"][0]["hue"], "arp")

    def test_precise_forwarding_single_events(self):
        self.assertEqual(
            [(e["from"], e["to"]) for e in self.steps[9]["events"]],
            [("SW1", "PC1")])
        # 应答精准回程：两段异源航线（PC2→SW1 → SW1→PC1），非泛洪
        legs = [(e["from"], e["to"], e.get("delay", 0))
                for e in self.steps[15]["events"]]
        self.assertEqual(legs, [("PC2", "SW1", 0), ("SW1", "PC1", 1)])

    def test_learning_rows_monotonic(self):
        """学习恰两行新增（idx2 MAC1→g0/1、idx7 MAC2→g0/2），单调存在。"""
        self.assertEqual(self.result.learn_steps, [2, 7])
        for i in range(0, 2):
            self.assertEqual(len(self.steps[i]["mac_table"]), 0, f"step {i}")
        for i in range(2, 7):
            self.assertEqual(len(self.steps[i]["mac_table"]), 1, f"step {i}")
        for i in range(7, 17):
            self.assertEqual(len(self.steps[i]["mac_table"]), 2, f"step {i}")
        row1 = self.steps[2]["mac_table"][0]
        self.assertEqual((row1["mac"], row1["port"], row1["type"]),
                         (switch.PC1_MAC, switch.PORT_PC1, "动态"))
        row2 = self.steps[7]["mac_table"][1]
        self.assertEqual((row2["mac"], row2["port"]),
                         (switch.PC2_MAC, switch.PORT_PC2))

    def test_refresh_no_new_row(self):
        """广播 beat 的学习动作 = 刷新老化（不新增行），age 标注刷新。"""
        table = self.steps[12]["mac_table"]
        self.assertEqual(len(table), 2)
        self.assertFalse(any(r.get("new") for r in table))
        self.assertIn("刷新", table[0]["age"])

    def test_frame_type_fields(self):
        by_key1 = {f["k"]: f for f in self.steps[1]["fields"]}
        self.assertIn("0x0800", by_key1["类型"]["v"])
        by_key11 = {f["k"]: f for f in self.steps[11]["fields"]}
        self.assertIn(switch.BROADCAST_MAC,
                      by_key11["以太网头 · 目的 MAC"]["v"])
        self.assertEqual(by_key11["以太网头 · 目的 MAC"]["tone"], "bcast")
        self.assertIn("0x0806", by_key11["类型"]["v"])

    def test_flash_verdicts(self):
        discards = [i for i, s in enumerate(self.steps)
                    if s["flash"].get("PC3", {}).get("ok") is False]
        self.assertEqual(discards, [5, 14])
        accepts = [i for i, s in enumerate(self.steps)
                   if s["flash"].get("PC2", {}).get("ok") is True]
        self.assertEqual(accepts, [6, 14])

    def test_dumb_render_contract(self):
        for i, s in enumerate(self.steps):
            self.assertTrue(s["description"].strip(), f"step {i}")
            self.assertTrue(s["bullets"] and
                            all(b.strip() for b in s["bullets"]), f"step {i}")
            self.assertIn(s["device"], IDS, f"step {i}")
            self.assertIsInstance(s["mac_table"], list, f"step {i}")
            if s["kind"] not in ("initial", "final"):
                self.assertGreaterEqual(len(s["fields"]), 3, f"step {i}")
            if s["kind"] == "move":
                self.assertTrue(s["events"], f"step {i}")
            else:
                self.assertEqual(s["events"], [], f"step {i}")
            for e in s["events"]:
                self.assertEqual(e["kind"], "frame", f"step {i}")
                self.assertIn(e["from"], IDS)
                self.assertIn(e["to"], IDS)

    def test_chain_shape(self):
        chain = self.result.chain
        self.assertEqual(chain.ids(), list(IDS))
        kinds = {d.id: d.kind for d in chain.devices}
        self.assertEqual(kinds["SW1"], "switch")
        data = chain.serialize()
        ports = {l["b"]: l["port"] for l in data["links"]}
        self.assertEqual(ports, {"PC1": "g0/1", "PC2": "g0/2", "PC3": "g0/3"})
        self.assertTrue(all(l["a"] == "SW1" for l in data["links"]))

    def test_result_summary(self):
        self.assertEqual(self.result.flood_steps, [4, 13])
        self.assertEqual(self.result.learn_steps, [2, 7])


class SwitchAgingTests(unittest.TestCase):
    def setUp(self):
        self.result = switch.simulate("aging")
        self.steps = self.result.steps

    def test_step_count_and_phases(self):
        self.assertEqual(len(self.steps), 11)
        self.assertEqual(self.result.phase_names, AGING_PHASES_EXPECTED)

    def test_layers_contract(self):
        for i, s in enumerate(self.steps):
            if s["kind"] in ("initial", "final"):
                self.assertEqual(s["layer"], 0, f"step {i}")
            elif s["kind"] == "move":
                self.assertEqual(s["layer"], 1, f"step {i}")
            else:
                self.assertTrue(1 <= s["layer"] <= 7, f"step {i}")
        self.assertEqual(self.steps[4]["layer"], 3)      # PC1 构造帧 = L3

    def test_table_lifecycle(self):
        """2 行(300)→2(180)→2(0)→0（删除恰 idx3-4）→1（重学 idx5）
        →2（idx8）；新增恰 [5, 8]；age 递减 ground truth。"""
        sizes = [len(s["mac_table"]) for s in self.steps]
        self.assertEqual(sizes, [2, 2, 2, 0, 0, 1, 1, 1, 2, 2, 2])
        self.assertEqual(self.result.learn_steps, [5, 8])
        ages = [tuple(r["age"] for r in s["mac_table"])
                for s in self.steps[:3]]
        self.assertEqual(ages[0], ("300s", "300s"))
        self.assertEqual(ages[1], ("180s", "180s"))
        self.assertEqual(ages[2], ("0s", "0s"))

    def test_single_flood_not_back_to_ingress(self):
        self.assertEqual(self.result.flood_steps, [6])
        self.assertEqual(
            {(e["from"], e["to"]) for e in self.steps[6]["events"]},
            {("SW1", "PC2"), ("SW1", "PC3")})
        self.assertEqual(
            [(e["from"], e["to"]) for e in self.steps[9]["events"]],
            [("SW1", "PC1")])

    def test_two_tables_distinction(self):
        """idx4 必须点破「ARP 表在 PC / MAC 表在交换机」的两张表错位。"""
        text = self.steps[4]["description"] + "".join(self.steps[4]["bullets"])
        self.assertIn("ARP 表", text)
        self.assertIn("MAC 表", text)

    def test_homework_keywords(self):
        """作业 2 三问答案与五条理由的关键词。"""
        deleted = self.steps[3]["description"] + "".join(self.steps[3]["bullets"])
        self.assertIn("删除", deleted)
        final = self.steps[10]["description"] + "".join(self.steps[10]["bullets"])
        for kw in ("300", "重新学习", "五条"):
            self.assertIn(kw, final)

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):
            switch.simulate("discard")


if __name__ == "__main__":
    unittest.main()
