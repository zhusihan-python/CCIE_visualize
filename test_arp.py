"""ARP 故事不变量：分镜 ground truth、广播唯一性、写表时序、哑渲染契约。"""

import unittest

import arp

PHASES_EXPECTED = [
    "—",
    "四元素 · 缺目的 MAC",
    "查 ARP 缓存 · 未命中",
    "ARP 请求 · 构造",
    "ARP 请求 · 广播",
    "广播帧 · PC3 丢弃",
    "广播帧 · PC2 认领",
    "ARP 应答 · 构造",
    "ARP 应答 · 单播",
    "写入 ARP 表",
    "ICMP 请求 · 封装",
    "ICMP 请求 · 单播",
    "ICMP 应答 · 生成",
    "ICMP 应答 · 单播",
    "ping 通了",
    "arp -a",
    "查表命中 · 免广播",
    "第二次 ping · 往返",
    "—",
]

KINDS_EXPECTED = [
    "initial",                                    # 0
    "process", "process", "process",              # 1-3 意图/查表/构造请求
    "move",                                       # 4 广播
    "process", "process", "process",              # 5-7 丢弃/认领/构造应答
    "move",                                       # 8 单播应答
    "process", "process",                         # 9-10 写表/封装 ICMP
    "move",                                       # 11 ICMP 请求
    "process",                                    # 12 生成应答
    "move",                                       # 13 ICMP 回程
    "process", "process", "process",              # 14-16 统计/arp -a/查表命中
    "move",                                       # 17 第二次 ping 往返
    "final",                                      # 18
]

IDS = ("PC1", "PC2", "PC3")


class ArpStoryTests(unittest.TestCase):
    def setUp(self):
        self.result = arp.simulate("resolve")
        self.steps = self.result.steps

    # ---- 分镜 ground truth -------------------------------------------

    def test_step_count_and_phases(self):
        self.assertEqual(len(self.steps), 19)
        self.assertEqual(self.result.phase_names, PHASES_EXPECTED)

    def test_kind_sequence(self):
        self.assertEqual([s["kind"] for s in self.steps], KINDS_EXPECTED)

    def test_layers_contract(self):
        """每步带 layer：initial/final=0，move=1（物理传输），
        process 步落 1..7——ARP 解析步 L2、ICMP 步 L3。"""
        for i, s in enumerate(self.steps):
            self.assertIsInstance(s["layer"], int, f"step {i}")
            if s["kind"] in ("initial", "final"):
                self.assertEqual(s["layer"], 0, f"step {i}")
            elif s["kind"] == "move":
                self.assertEqual(s["layer"], 1, f"step {i}")
            else:
                self.assertLessEqual(s["layer"], 7, f"step {i}")
                self.assertGreaterEqual(s["layer"], 1, f"step {i}")
        for i in (2, 3, 5, 6, 7, 9, 15, 16):   # 查表/构造请求/丢弃/认领/应答/写表/arp -a/命中
            self.assertEqual(self.steps[i]["layer"], 2, f"step {i}")
        for i in (10, 12, 14):                  # ICMP 封装/生成应答/统计
            self.assertEqual(self.steps[i]["layer"], 3, f"step {i}")

    # ---- 广播唯一性与扇出 --------------------------------------------

    def test_unique_broadcast_fanout(self):
        self.assertEqual(self.result.fanout_steps, [4])
        events = self.steps[4]["events"]
        self.assertEqual(len(events), 2)
        self.assertEqual({e["from"] for e in events}, {"PC1"})
        self.assertEqual({e["to"] for e in events}, {"PC2", "PC3"})
        for e in events:
            self.assertEqual(e["kind"], "frame")
            self.assertEqual(e["hue"], "arp")
            self.assertIn("广播", e["label"])

    def test_no_fanout_after_broadcast_step(self):
        """广播之后任何步不得再出现同源多目的（第二次 ping 是异源往返）。"""
        for i, s in enumerate(self.steps[5:], start=5):
            if len(s["events"]) > 1:
                self.assertGreater(
                    len({e["from"] for e in s["events"]}), 1,
                    f"unexpected fanout at step {i}")

    def test_second_ping_roundtrip_events(self):
        events = self.steps[17]["events"]
        self.assertEqual(
            [(e["from"], e["to"], e.get("delay", 0)) for e in events],
            [("PC1", "PC2", 0), ("PC2", "PC1", 1)])
        for e in events:
            self.assertEqual(e["hue"], "icmp")

    # ---- 报文字段 ground truth ----------------------------------------

    def test_request_fields(self):
        fields = self.steps[3]["fields"]
        by_key = {f["k"]: f for f in fields}
        self.assertIn(arp.BROADCAST_MAC, by_key["以太网头 · 目的 MAC"]["v"])
        self.assertEqual(by_key["以太网头 · 目的 MAC"]["tone"], "bcast")
        self.assertIn(arp.PC1_MAC, by_key["以太网头 · 源 MAC"]["v"])
        self.assertIn("请求", by_key["ARP · 操作码"]["v"])
        self.assertIn(arp.PC2_IP, by_key["ARP · 目标 IP"]["v"])
        self.assertEqual(by_key["ARP · 目标 MAC"]["tone"], "unk")
        self.assertIn("全 0", by_key["ARP · 目标 MAC"]["v"])

    def test_reply_is_unicast_to_pc1(self):
        fields = self.steps[7]["fields"]
        by_key = {f["k"]: f for f in fields}
        dst = by_key["以太网头 · 目的 MAC"]
        self.assertIn(arp.PC1_MAC, dst["v"])
        self.assertEqual(dst["tone"], "uni")
        self.assertIn("应答", by_key["ARP · 操作码"]["v"])
        for f in fields:       # 应答帧里不得再出现广播地址
            self.assertNotIn(arp.BROADCAST_MAC, f["v"])
        self.assertEqual(
            [(e["from"], e["to"]) for e in self.steps[8]["events"]],
            [("PC2", "PC1")])

    def test_icmp_fields(self):
        req = {f["k"]: f for f in self.steps[10]["fields"]}
        self.assertIn(arp.PC2_MAC, req["以太网头 · 目的 MAC"]["v"])
        self.assertIn("刚查到", req["以太网头 · 目的 MAC"]["v"])
        self.assertEqual(req["IP 头 · 源 IP"]["v"], arp.PC1_IP)
        self.assertEqual(req["IP 头 · 目的 IP"]["v"], arp.PC2_IP)
        rep = {f["k"]: f for f in self.steps[12]["fields"]}
        self.assertIn(arp.PC1_MAC, rep["以太网头 · 目的 MAC"]["v"])
        self.assertIn("查表命中", rep["以太网头 · 目的 MAC"]["v"])
        self.assertEqual(rep["IP 头 · 源 IP"]["v"], arp.PC2_IP)

    # ---- ARP 表时序 ----------------------------------------------------

    def test_pc1_table_lifecycle(self):
        def has(steps, who, ip):
            return any(r["ip"] == ip
                       for s in steps for r in s["arp_tables"][who])
        # 写表前无、写表后有（单调），恰在第 9 步（0 基）新增
        self.assertFalse(has(self.steps[:9], "PC1", arp.PC2_IP))
        self.assertTrue(all(
            any(r["ip"] == arp.PC2_IP for r in s["arp_tables"]["PC1"])
            for s in self.steps[9:]))
        new_rows = [i for i, s in enumerate(self.steps)
                    if any(r.get("new") for r in s["arp_tables"]["PC1"])]
        self.assertEqual(new_rows, [9])
        row = self.steps[9]["arp_tables"]["PC1"][0]
        self.assertEqual((row["ip"], row["mac"], row["type"]),
                         (arp.PC2_IP, arp.PC2_MAC, "dynamic"))

    def test_pc2_learns_pc1_from_request(self):
        """应答方从请求「发送方」字段顺手学到请求者——恰在认领步新增。"""
        first = next(i for i, s in enumerate(self.steps)
                     if any(r["ip"] == arp.PC1_IP
                            for r in s["arp_tables"]["PC2"]))
        self.assertEqual(first, 6)
        self.assertEqual(self.steps[6]["arp_tables"]["PC2"][0]["mac"],
                         arp.PC1_MAC)
        self.assertTrue(all(
            any(r["ip"] == arp.PC1_IP for r in s["arp_tables"]["PC2"])
            for s in self.steps[6:]))

    def test_broadcast_mac_only_in_arp_phase(self):
        """第二次 ping 阶段（写表之后）不得再出现广播地址。"""
        idx = {i for i, s in enumerate(self.steps)
               if any(arp.BROADCAST_MAC in f["v"] for f in s["fields"])}
        self.assertTrue(idx.issubset({3, 4, 5, 6}), f"got {idx}")

    # ---- 接收判定胶囊 --------------------------------------------------

    def test_flash_verdicts(self):
        discards = [i for i, s in enumerate(self.steps)
                    if s["flash"].get("PC3", {}).get("ok") is False]
        self.assertEqual(discards, [5, 11])
        self.assertIn("IP", self.steps[5]["flash"]["PC3"]["text"])
        self.assertIn("MAC", self.steps[11]["flash"]["PC3"]["text"])
        accepts = [i for i, s in enumerate(self.steps)
                   if s["flash"].get("PC2", {}).get("ok") is True]
        self.assertEqual(accepts, [6])

    # ---- 哑渲染契约 ----------------------------------------------------

    def test_dumb_render_contract(self):
        for i, s in enumerate(self.steps):
            self.assertTrue(s["description"].strip(), f"step {i}")
            self.assertTrue(s["bullets"] and
                            all(b.strip() for b in s["bullets"]), f"step {i}")
            self.assertIn(s["device"], IDS, f"step {i}")
            tables = s["arp_tables"]
            self.assertEqual(sorted(tables), ["PC1", "PC2"], f"step {i}")
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

    def test_no_alert_devices_used(self):
        """arp 的接收判定走 flash 胶囊，不用 alert_devices（避让 ⚠ 徽标）。"""
        for i, s in enumerate(self.steps):
            self.assertNotIn("alert_devices", s, f"step {i}")

    # ---- 拓扑与摘要 ----------------------------------------------------

    def test_chain_shape(self):
        chain = self.result.chain
        self.assertEqual(chain.ids(), list(IDS))
        self.assertTrue(all(d.kind == "pc" for d in chain.devices))
        self.assertEqual(chain.links, [])
        data = chain.serialize()
        self.assertEqual(data["links"], [])
        self.assertTrue(all(d["ip"] and d["mac"] for d in data["devices"]))

    def test_result_summary(self):
        self.assertEqual(self.result.fanout_steps, [4])
        self.assertEqual(self.result.table_writes, 2)

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):
            arp.simulate("gratuitous")


CONFLICT_PHASES_EXPECTED = [
    "—",
    "误配同 IP",
    "免费 ARP · 构造",
    "免费 ARP · 广播",
    "PC1 · 表被改写",
    "PC2 · 发现冲突",
    "冲突应答 · 构造",
    "冲突应答 · 单播",
    "IP 冲突 · 告警",
    "暗伤 · 表指向 PC3",
    "修复① · PC3 改回 .3",
    "修复② · 防守免费 ARP",
    "防守广播",
    "PC1 · 表被纠正",
    "PC3 · 沉默",
    "—",
]

CONFLICT_KINDS_EXPECTED = [
    "initial",                                    # 0
    "process", "process",                         # 1-2 误配/构造免费 ARP
    "move",                                       # 3 广播扇出
    "process", "process", "process",              # 4-6 改写/发现/构造应答
    "move",                                       # 7 单播应答
    "process", "process", "process", "process",   # 8-11 告警/暗伤/修复①②
    "move",                                       # 12 防守广播扇出
    "process", "process",                         # 13-14 纠正/沉默
    "final",                                      # 15
]


class ArpConflictTests(unittest.TestCase):
    def setUp(self):
        self.result = arp.simulate("conflict")
        self.steps = self.result.steps

    def test_step_count_and_phases(self):
        self.assertEqual(len(self.steps), 16)
        self.assertEqual(self.result.phase_names, CONFLICT_PHASES_EXPECTED)

    def test_kind_sequence(self):
        self.assertEqual([s["kind"] for s in self.steps],
                         CONFLICT_KINDS_EXPECTED)

    def test_layers_contract(self):
        for i, s in enumerate(self.steps):
            self.assertIsInstance(s["layer"], int, f"step {i}")
            if s["kind"] in ("initial", "final"):
                self.assertEqual(s["layer"], 0, f"step {i}")
            elif s["kind"] == "move":
                self.assertEqual(s["layer"], 1, f"step {i}")
            else:
                self.assertTrue(1 <= s["layer"] <= 7, f"step {i}")
        for i in (1, 10):              # 两次配置动作步 = L3
            self.assertEqual(self.steps[i]["layer"], 3, f"step {i}")
        for i in (2, 4, 5, 6, 8, 9, 11, 13, 14):   # ARP 处理步 = L2
            self.assertEqual(self.steps[i]["layer"], 2, f"step {i}")

    def test_two_broadcast_fanouts(self):
        self.assertEqual(self.result.fanout_steps, [3, 12])
        self.assertEqual(
            {(e["from"], e["to"]) for e in self.steps[3]["events"]},
            {("PC3", "PC1"), ("PC3", "PC2")})
        self.assertEqual(
            {(e["from"], e["to"]) for e in self.steps[12]["events"]},
            {("PC2", "PC1"), ("PC2", "PC3")})
        for i in (3, 12):
            for e in self.steps[i]["events"]:
                self.assertEqual(e["kind"], "frame")
                self.assertEqual(e["hue"], "arp")

    def test_conflict_reply_is_unicast_to_pc3(self):
        self.assertEqual(
            [(e["from"], e["to"]) for e in self.steps[7]["events"]],
            [("PC2", "PC3")])
        fields = self.steps[6]["fields"]
        by_key = {f["k"]: f for f in fields}
        self.assertIn(arp.PC3_MAC, by_key["以太网头 · 目的 MAC"]["v"])
        self.assertEqual(by_key["以太网头 · 目的 MAC"]["tone"], "uni")
        self.assertIn("应答", by_key["ARP · 操作码"]["v"])
        for f in fields:       # 冲突应答帧里不得出现广播地址
            self.assertNotIn(arp.BROADCAST_MAC, f["v"])

    def test_gratuitous_identity(self):
        """两次免费 ARP：发送方 IP 与目标 IP 都是 192.168.1.2 且 OP=请求。"""
        for i in (2, 11):
            by_key = {f["k"]: f for f in self.steps[i]["fields"]}
            self.assertIn(arp.PC2_IP, by_key["ARP · 发送方 IP"]["v"],
                          f"step {i}")
            self.assertIn(arp.PC2_IP, by_key["ARP · 目标 IP"]["v"],
                          f"step {i}")
            self.assertIn("请求", by_key["ARP · 操作码"]["v"], f"step {i}")
            self.assertIn(arp.BROADCAST_MAC,
                          by_key["以太网头 · 目的 MAC"]["v"], f"step {i}")

    def test_pc1_table_trajectory(self):
        """MAC2 →（恰 idx4）MAC3 →（恰 idx13）MAC2；恰两次变更且行高亮。"""
        def mac_at(i):
            rows = self.steps[i]["arp_tables"]["PC1"]
            self.assertEqual(len(rows), 1)
            return rows[0]["mac"]
        self.assertEqual(mac_at(0), arp.PC2_MAC)
        for i in range(4, 13):
            self.assertEqual(mac_at(i), arp.PC3_MAC, f"step {i}")
        for i in (13, 14, 15):
            self.assertEqual(mac_at(i), arp.PC2_MAC, f"step {i}")
        flagged = [i for i, s in enumerate(self.steps)
                   if any(r.get("new") for r in s["arp_tables"]["PC1"])]
        self.assertEqual(flagged, [4, 13])

    def test_alert_window(self):
        """⚠ 告警恰在 idx8、idx9（告警步与暗伤步），修复①起消失。"""
        for i, s in enumerate(self.steps):
            if i in (8, 9):
                self.assertEqual(s.get("alert_devices"), ["PC3"], f"step {i}")
            else:
                self.assertNotIn("alert_devices", s, f"step {i}")

    def test_dev_ip_window(self):
        """误配覆盖恰在 idx1..idx9；idx0 与修复①（idx10）起不出现。"""
        expect = {"PC3": arp.PC2_IP}
        for i, s in enumerate(self.steps):
            if 1 <= i <= 9:
                self.assertEqual(s.get("dev_ip"), expect, f"step {i}")
            else:
                self.assertNotIn("dev_ip", s, f"step {i}")

    def test_pc3_table_empty_throughout(self):
        for i, s in enumerate(self.steps):
            self.assertEqual(s["arp_tables"].get("PC3", []), [], f"step {i}")

    def test_dumb_render_contract(self):
        for i, s in enumerate(self.steps):
            self.assertTrue(s["description"].strip(), f"step {i}")
            self.assertTrue(s["bullets"] and
                            all(b.strip() for b in s["bullets"]), f"step {i}")
            self.assertIn(s["device"], IDS, f"step {i}")
            self.assertEqual(sorted(s["arp_tables"]), ["PC1", "PC2"],
                             f"step {i}")
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

    def test_result_summary(self):
        self.assertEqual(self.result.fanout_steps, [3, 12])
        self.assertEqual(self.result.table_writes, 2)


if __name__ == "__main__":
    unittest.main()
