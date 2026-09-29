"""ios.py 故事不变量测试：kind/mode 全序列、prompt↔mode 不变量、终端节拍、
files/pw 面板转换。表值为手写字面量，不从生成器导入。

不变量（一行规则）：输入行 prompt 以 > 或 # 结尾 ⟺ 模式提示行，后缀必须
匹配上一步的 mode；以 : 或 ] 结尾（Password: / [yes/no]: / [confirm]）
及其它形态一律跳过。
"""

import json
import unittest

import generate
import ios

MODE_SUFFIX = {"user": ">", "priv": "#", "config": "(config)#",
               "config-line": "(config-line)#"}
MODE_ORDER = ("setup", "user", "priv", "config", "config-line")

MODES_SEQUENCE = [
    ("initial", "setup"),
    ("cli", "user"), ("cli", "user"), ("cli", "user"),
    ("cli", "priv"), ("cli", "priv"), ("cli", "priv"),
    ("cli", "config"), ("cli", "config"), ("cli", "config"),
    ("cli", "config"), ("cli", "config"),
    ("cli", "priv"), ("cli", "user"),
    ("cli", "priv"), ("cli", "config"), ("cli", "priv"),
    ("final", "priv"),
]
SAVE_SEQUENCE = [
    ("initial", "user"),
    ("cli", "priv"), ("cli", "config"), ("cli", "config"),
    ("cli", "priv"), ("cli", "priv"), ("cli", "priv"), ("cli", "priv"),
    ("cli", "user"),
    ("cli", "priv"), ("cli", "priv"),
    ("cli", "config"), ("cli", "config"),
    ("cli", "priv"), ("cli", "priv"),
    ("cli", "user"),
    ("cli", "priv"), ("cli", "priv"),
    ("cli", "setup"),
    ("cli", "user"),
    ("final", "user"),
]
PASSWORDS_SEQUENCE = [
    ("initial", "user"),
    ("cli", "priv"), ("cli", "config"),
    ("cli", "config-line"), ("cli", "config-line"),
    ("cli", "config"), ("cli", "priv"), ("cli", "user"),
    ("cli", "priv"),
    ("cli", "config"), ("cli", "config-line"), ("cli", "config-line"),
    ("cli", "config"), ("cli", "priv"), ("cli", "user"),
    ("cli", "priv"),
    ("cli", "config"), ("cli", "config"), ("cli", "priv"), ("cli", "priv"),
    ("cli", "config"), ("cli", "config"), ("cli", "priv"), ("cli", "priv"),
    ("cli", "user"),
    ("cli", "priv"),
    ("final", "priv"),
]
SEQUENCES = {"modes": MODES_SEQUENCE, "save": SAVE_SEQUENCE,
             "passwords": PASSWORDS_SEQUENCE}

# save 场景 files 面板：(len(ram), len(nvram)) 逐步全表
SAVE_FILES = [
    (0, 0), (0, 0), (0, 0), (1, 0), (1, 0), (1, 0), (1, 0), (1, 0),
    (0, 0), (0, 0), (0, 0), (0, 0), (1, 0), (1, 0), (1, 1), (1, 1),
    (1, 1), (1, 0), (0, 0), (0, 0), (0, 0),
]


def flat_text(steps):
    """以最后一步的累计 term 拼全文——每行恰好出现一次。"""
    return "\n".join(line.get("prompt", "") + line.get("text", "")
                     if line["k"] == "in" else line["text"]
                     for line in steps[-1]["term"])


class GroundTruthTests(unittest.TestCase):
    def test_kind_mode_sequences(self):
        for scenario, table in SEQUENCES.items():
            result = ios.simulate(scenario)
            self.assertEqual(len(result.steps), len(table), scenario)
            actual = [(s["kind"], s["mode"]) for s in result.steps]
            self.assertEqual(actual, table, scenario)

    def test_prompt_mode_invariant(self):
        for scenario in ios.SCENARIOS:
            steps = ios.simulate(scenario).steps
            for i, step in enumerate(steps):
                if i == 0:
                    continue          # 首步无上一步模式；其输入均为非模式提示
                prev = steps[i - 1]
                for ln in step["term"][len(prev["term"]):]:
                    if ln["k"] != "in" or not ln["prompt"].endswith((">", "#")):
                        continue
                    self.assertTrue(
                        ln["prompt"].endswith(MODE_SUFFIX[prev["mode"]]),
                        f"{scenario} step {i}: {ln['prompt']!r} vs "
                        f"{prev['mode']}")

    def test_term_monotonic(self):
        for scenario in ios.SCENARIOS:
            steps = ios.simulate(scenario).steps
            self.assertGreater(len(steps[0]["term"]), 0)
            for a, b in zip(steps, steps[1:]):
                self.assertGreaterEqual(len(b["term"]), len(a["term"]),
                                        scenario)


class ModesTests(unittest.TestCase):
    def setUp(self):
        self.steps = ios.simulate("modes").steps

    def test_hostname_prefix_bidirectional(self):
        # hostname R1 后提示符变 R1；no hostname 后回退 Router；重配再用 R1
        self.assertEqual(self.steps[9]["term"][-2]["prompt"], "R1(config)#")
        self.assertEqual(self.steps[10]["term"][-5]["prompt"],
                         "Router(config)#")
        self.assertEqual(self.steps[12]["term"][-2]["prompt"], "R1(config)#")

    def test_error_marker_beat(self):
        term = self.steps[10]["term"]
        texts = [ln["text"] for ln in term]
        self.assertIn("% Invalid input detected at '^' marker.", texts)
        # 脱字符行：与 prompt 等宽对齐（Router(config)# = 15 字符）
        self.assertIn(" " * 15 + "^", texts)

    def test_key_beat_literals(self):
        flat = flat_text(self.steps)
        self.assertIn("[Tab] 补全 → configure", flat)
        self.assertIn("[Ctrl+Z]", flat)
        self.assertIn("--- System Configuration Dialog ---", flat)
        # Ctrl+Z 步的输入是按键字面量
        self.assertEqual(self.steps[16]["term"][-2]["text"], "[Ctrl+Z]")

    def test_narration_keywords(self):
        text = " ".join(s["description"] for s in self.steps)
        for kw in ("用户模式", "特权模式", "全局配置", "Tab", "no", "Ctrl+Z"):
            self.assertIn(kw, text)


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.steps = ios.simulate("save").steps

    def test_files_transitions(self):
        self.assertEqual(len(self.steps), len(SAVE_FILES))
        for i, (ram, nvram) in enumerate(SAVE_FILES):
            self.assertEqual(len(self.steps[i]["files"]["ram"]), ram, i)
            self.assertEqual(len(self.steps[i]["files"]["nvram"]), nvram, i)

    def test_write_sync_and_restore(self):
        # write 后两盒同条目；第二次 reload 后 RAM 从 NVRAM 恢复
        write = self.steps[14]["files"]
        self.assertEqual(write["ram"], ["hostname R2"])
        self.assertEqual(write["nvram"], ["hostname R2"])
        reloaded = self.steps[15]["files"]
        self.assertEqual(reloaded["ram"], ["hostname R2"])
        # erase+reload 后双清零（恢复出厂）
        erased = self.steps[18]["files"]
        self.assertEqual(erased["ram"], [])
        self.assertEqual(erased["nvram"], [])

    def test_confirm_lines(self):
        flat = flat_text(self.steps)
        self.assertEqual(flat.count("[confirm]"), 4)   # reload×3 + write erase

    def test_setup_dialog_replay(self):
        # write erase 后的 reload 再现开机向导（mode=setup），答 no 回 user
        step18 = self.steps[18]
        self.assertEqual(step18["mode"], "setup")
        texts = [ln["text"] for ln in step18["term"]]
        self.assertIn("--- System Configuration Dialog ---", texts)
        self.assertEqual(self.steps[19]["mode"], "user")

    def test_prompt_prefix_around_loss(self):
        # 丢失前 R2(config)#，重启后 Router>，恢复保存后 R2>
        self.assertEqual(self.steps[4]["term"][-2]["prompt"], "R2(config)#")
        self.assertEqual(self.steps[9]["term"][-2]["prompt"], "Router>")
        self.assertEqual(self.steps[16]["term"][-2]["prompt"], "R2>")

    def test_narration_keywords(self):
        text = " ".join(s["description"] for s in self.steps)
        for kw in ("RAM", "NVRAM", "write", "丢", "running-config",
                   "startup-config"):
            self.assertIn(kw, text)


class PasswordsTests(unittest.TestCase):
    def setUp(self):
        self.steps = ios.simulate("passwords").steps

    def test_pw_transitions(self):
        # 坑一：password 配了但 login 未配
        pit1 = self.steps[7]["pw"]
        self.assertEqual(pit1["console_pw"], "CCNA")
        self.assertFalse(pit1["console_login"])
        # 补 login 后生效
        self.assertTrue(self.steps[11]["pw"]["console_login"])
        # 明文 password → 密文 secret 依次上线，最终并存
        self.assertEqual(self.steps[17]["pw"]["enable_password"], "123456")
        final_pw = self.steps[-1]["pw"]
        self.assertEqual(final_pw["enable_secret"], "Cisco@123")

    def test_silent_lines(self):
        silent = [ln for ln in self.steps[-1]["term"] if ln.get("silent")]
        self.assertEqual(len(silent), 4)      # CCNA×2 + 123456 + Cisco@123
        self.assertEqual({ln["text"] for ln in silent},
                         {"CCNA", "123456", "Cisco@123"})
        self.assertTrue(all(ln["prompt"] == "Password:" for ln in silent))

    def test_login_flow_beats(self):
        flat = flat_text(self.steps)
        self.assertEqual(flat.count("User Access Verification"), 2)
        self.assertIn("% Bad secrets", flat)
        self.assertIn("enable secret 5 $1$9Q8O$mVCMssrcoibWUb9CioLol.",
                      flat)
        # Console 密码只以配置输入出现一次；show run 节选用省略号跳过该段
        self.assertEqual(flat.count("password CCNA"), 1)

    def test_config_line_submode(self):
        for i in (3, 4, 10, 11):
            self.assertEqual(self.steps[i]["mode"], "config-line", i)

    def test_narration_keywords(self):
        text = " ".join(s["description"] for s in self.steps)
        for kw in ("login", "secret", "Console", "明文", "密文"):
            self.assertIn(kw, text)


class DocumentTests(unittest.TestCase):
    def test_structure_and_modes(self):
        for scenario in ios.SCENARIOS:
            steps = ios.simulate(scenario).steps
            self.assertEqual(steps[0]["kind"], "initial")
            self.assertEqual(steps[-1]["kind"], "final")
            for st in steps:
                self.assertIn(st["mode"], MODE_ORDER)
                self.assertGreaterEqual(len(st["bullets"]), 2)
                self.assertTrue(st["description"])

    def test_ios_documents_have_empty_chain(self):
        for scenario in ios.SCENARIOS:
            document, _ = generate.build_document("ios", scenario)
            self.assertEqual(document["chain"],
                             {"devices": [], "links": []}, scenario)
            self.assertEqual(document["topic"], "ios")
            self.assertIn("终端回放", document["subtitle"])
            self.assertIn("scenario", document["concept"])

    def test_old_topics_chain_unchanged(self):
        document, _ = generate.build_document("encap", "cross-net")
        self.assertEqual(len(document["chain"]["devices"]), 5)

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):
            ios.simulate("nonsense")

    def test_determinism(self):
        for scenario in ios.SCENARIOS:
            a = ios.simulate(scenario)
            b = ios.simulate(scenario)
            self.assertEqual(
                json.dumps(a.steps, ensure_ascii=False, sort_keys=True),
                json.dumps(b.steps, ensure_ascii=False, sort_keys=True))

    def test_document_determinism(self):
        a, _ = generate.build_document("ios", "save")
        b, _ = generate.build_document("ios", "save")
        self.assertEqual(json.dumps(a, sort_keys=True, ensure_ascii=False),
                         json.dumps(b, sort_keys=True, ensure_ascii=False))

    def test_result_meta(self):
        self.assertEqual(ios.simulate("modes").mode_changes, 8)
        self.assertGreater(ios.simulate("save").mode_changes, 0)


if __name__ == "__main__":
    unittest.main()
