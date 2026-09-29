"""troubleshoot.py 故事不变量测试：检查序列 ground truth、故障可见性分段、
ping 事件规则、讲解文案。表值为手写字面量，不从生成器导入——故事想偏离
「自底向上、恰好一个 fail、修后必验」的排错语义会直接红。
"""

import json
import unittest

import generate
import troubleshoot as ts

# verdict 缩写：t=todo p=pass f=fail
CABLE = [
    ("symptom", 0, ("t", "t", "t", "t")),
    ("check",   1, ("f", "t", "t", "t")),
    ("fix",     1, ("f", "t", "t", "t")),
    ("verify",  1, ("p", "t", "t", "t")),
    ("verify",  7, ("p", "t", "t", "p")),
    ("final",   0, ("p", "t", "t", "p")),
]
IP_CONFIG = [
    ("symptom", 0, ("t", "t", "t", "t")),
    ("check",   1, ("p", "t", "t", "t")),
    ("check",   2, ("p", "p", "t", "t")),
    ("check",   3, ("p", "p", "f", "t")),
    ("fix",     3, ("p", "p", "f", "t")),
    ("verify",  3, ("p", "p", "p", "t")),
    ("verify",  7, ("p", "p", "p", "p")),
    ("final",   0, ("p", "p", "p", "p")),
]
SERVICE = [
    ("symptom", 0, ("t", "t", "t", "t")),
    ("check",   1, ("p", "t", "t", "t")),
    ("check",   2, ("p", "p", "t", "t")),
    ("check",   3, ("p", "p", "p", "t")),
    ("check",   7, ("p", "p", "p", "f")),
    ("fix",     7, ("p", "p", "p", "f")),
    ("verify",  7, ("p", "p", "p", "p")),
    ("verify",  7, ("p", "p", "p", "p")),
    ("final",   0, ("p", "p", "p", "p")),
]
TABLES = {"cable": CABLE, "ip-config": IP_CONFIG, "service": SERVICE}
EXPAND = {"t": "todo", "p": "pass", "f": "fail"}


class GroundTruthTests(unittest.TestCase):
    def test_kind_layer_verdict_sequences(self):
        for scenario, table in TABLES.items():
            result = ts.simulate(scenario)
            self.assertEqual(len(result.steps), len(table), scenario)
            actual = [(s["kind"], s["layer"],
                       tuple(c["verdict"] for c in s["checks"]))
                      for s in result.steps]
            expected = [(k, l, tuple(EXPAND[v] for v in vs))
                        for k, l, vs in table]
            self.assertEqual(actual, expected, scenario)

    def test_exactly_one_fail_at_fault_layer(self):
        for scenario, fault_layer in (("cable", 1), ("ip-config", 3),
                                      ("service", 7)):
            result = ts.simulate(scenario)
            self.assertEqual(result.fault_layer, fault_layer)
            fails = [s for s in result.steps
                     if s["kind"] == "check"
                     and any(c["verdict"] == "fail" for c in s["checks"])]
            self.assertEqual(len(fails), 1, scenario)
            self.assertEqual(fails[0]["layer"], fault_layer, scenario)
            # fail 之前：任何行都不得已 fail；此前的检查步自身行均为 pass
            idx = result.steps.index(fails[0])
            for prev in result.steps[:idx]:
                verdicts = [c["verdict"] for c in prev["checks"]]
                self.assertNotIn("fail", verdicts, scenario)
                if prev["kind"] == "check":
                    row = [c for c in prev["checks"]
                           if c["layer"] == prev["layer"]][0]
                    self.assertEqual(row["verdict"], "pass", scenario)

    def test_fix_then_two_verifies(self):
        for scenario in TABLES:
            result = ts.simulate(scenario)
            fix_at = next(i for i, s in enumerate(result.steps)
                          if s["kind"] == "fix")
            after = result.steps[fix_at + 1:]
            verifies = [s for s in after if s["kind"] == "verify"]
            self.assertEqual(len(verifies), 2, scenario)
            # 故障层复查（layer=故障层）在前，应用验证（layer=7）在后
            self.assertEqual(verifies[0]["layer"], result.fault_layer, scenario)
            self.assertEqual(verifies[1]["layer"], 7, scenario)
            # 复查后故障行转 pass
            for c in verifies[0]["checks"]:
                self.assertNotEqual(c["verdict"], "fail", scenario)

    def test_step_structure(self):
        for scenario in TABLES:
            result = ts.simulate(scenario)
            steps = result.steps
            self.assertEqual(steps[0]["kind"], "symptom")
            self.assertEqual(steps[-1]["kind"], "final")
            ids = set(result.chain.ids())
            for st in steps:
                self.assertIn(st["layer"], (0, 1, 2, 3, 7))
                self.assertIn(st["device"], ids)
                self.assertGreaterEqual(len(st["bullets"]), 2)
                self.assertTrue(st["description"])
                self.assertEqual(len(st["checks"]), 4)


class FaultVisibilityTests(unittest.TestCase):
    def test_cable_down_links_segments(self):
        steps = ts.simulate("cable").steps
        self.assertEqual(steps[0]["down_links"], ["PC1-SW1"])
        self.assertEqual(steps[1]["down_links"], ["PC1-SW1"])
        for st in steps[2:]:
            self.assertEqual(st["down_links"], [])

    def test_alert_devices_segments(self):
        ip_steps = ts.simulate("ip-config").steps
        self.assertEqual(ip_steps[0]["alert_devices"], [])
        self.assertEqual(ip_steps[3]["alert_devices"], ["PC1"])   # ✗ 检查
        self.assertEqual(ip_steps[4]["alert_devices"], ["PC1"])   # fix
        for st in ip_steps[5:]:
            self.assertEqual(st["alert_devices"], [])
        svc_steps = ts.simulate("service").steps
        self.assertEqual(svc_steps[0]["alert_devices"], [])
        self.assertEqual(svc_steps[4]["alert_devices"], ["PC2"])
        self.assertEqual(svc_steps[5]["alert_devices"], ["PC2"])
        for st in svc_steps[6:]:
            self.assertEqual(st["alert_devices"], [])
        cable_steps = ts.simulate("cable").steps
        for st in cable_steps:
            self.assertEqual(st["alert_devices"], [])

    def test_chain_fault_declarations(self):
        cable = ts.simulate("cable").chain.serialize()
        first = cable["links"][0]
        self.assertEqual(first, {"a": "PC1", "b": "SW1", "state": "down"})
        for link in cable["links"][1:]:
            self.assertEqual(set(link.keys()), {"a", "b"})
        ip_doc = ts.simulate("ip-config").chain.serialize()
        pc1 = ip_doc["devices"][0]
        self.assertEqual(pc1["ip"], "192.168.3.10")
        svc = ts.simulate("service").chain.serialize()
        for link in svc["links"]:
            self.assertEqual(set(link.keys()), {"a", "b"})

    def test_step0_no_spoiler_markers(self):
        for scenario in ("ip-config", "service"):
            st = ts.simulate(scenario).steps[0]
            self.assertEqual(st["down_links"], [])
            self.assertEqual(st["alert_devices"], [])


class PingEventTests(unittest.TestCase):
    def test_ping_events_use_chain_devices(self):
        for scenario in TABLES:
            result = ts.simulate(scenario)
            ids = set(result.chain.ids())
            for st in result.steps:
                for e in st.get("events", []):
                    self.assertIn(e["from"], ids)
                    self.assertIn(e["to"], ids)
                    self.assertNotEqual(e["from"], e["to"])
                    self.assertEqual(e["kind"], "ping")

    def test_drop_only_on_fail_check(self):
        ip_steps = ts.simulate("ip-config").steps
        drop_steps = [s for s in ip_steps
                      if any("drop" in e for e in s["events"])]
        self.assertEqual(len(drop_steps), 1)
        self.assertEqual(drop_steps[0]["kind"], "check")
        self.assertTrue(any(c["verdict"] == "fail"
                            for c in drop_steps[0]["checks"]))
        for scenario in ("cable", "service"):
            for st in ts.simulate(scenario).steps:
                self.assertFalse(any("drop" in e for e in st["events"]))

    def test_round_trip_events(self):
        ip_verify = ts.simulate("ip-config").steps[5]
        self.assertEqual(len(ip_verify["events"]), 2)
        self.assertEqual(ip_verify["events"][1]["delay"], 1.0)
        svc_check = ts.simulate("service").steps[3]
        self.assertEqual(len(svc_check["events"]), 2)


class NarrationAndMetaTests(unittest.TestCase):
    def test_common_keywords(self):
        for scenario in TABLES:
            text = " ".join(s["description"] for s in ts.simulate(scenario).steps)
            for kw in ("排错", "自底向上", "物理层", "ping", "排除"):
                self.assertIn(kw, text, f"{scenario}: {kw}")

    def test_scenario_keywords(self):
        cable = " ".join(s["description"] for s in ts.simulate("cable").steps)
        self.assertIn("换", cable)           # 换线
        ip = " ".join(s["description"] for s in ts.simulate("ip-config").steps)
        self.assertIn("192.168.3.10", ip)
        svc = " ".join(s["description"] for s in ts.simulate("service").steps)
        self.assertIn("服务", svc)

    def test_determinism(self):
        for scenario in ts.SCENARIOS:
            a = ts.simulate(scenario)
            b = ts.simulate(scenario)
            self.assertEqual(
                json.dumps(a.steps, ensure_ascii=False, sort_keys=True),
                json.dumps(b.steps, ensure_ascii=False, sort_keys=True))

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):
            ts.simulate("nonsense")

    def test_result_meta(self):
        self.assertEqual(ts.simulate("cable").checks_until_hit, 1)
        self.assertEqual(ts.simulate("ip-config").checks_until_hit, 3)
        self.assertEqual(ts.simulate("service").checks_until_hit, 4)

    def test_document_envelope(self):
        document, result = generate.build_document("troubleshoot", "cable")
        self.assertEqual(document["topic"], "troubleshoot")
        self.assertEqual(document["scenario"], "cable")
        self.assertEqual(document["title"],
                         "分层排错 · 物理层故障（网线中断）")
        self.assertIn("自底向上逐层排查", document["subtitle"])
        self.assertEqual(len(document["steps"]), len(result.steps))
        self.assertIn("scenario", document["concept"])

    def test_document_determinism(self):
        a, _ = generate.build_document("troubleshoot", "service")
        b, _ = generate.build_document("troubleshoot", "service")
        self.assertEqual(json.dumps(a, sort_keys=True, ensure_ascii=False),
                         json.dumps(b, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
