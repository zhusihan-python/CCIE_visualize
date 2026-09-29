"""渲染管线与 CLI 集成测试：单文件 HTML 打包契约、转义、产物标记。"""

import json
import tempfile
import unittest
from pathlib import Path

import generate

REPO = Path(__file__).resolve().parent
# 播放器必须引用到的外壳 DOM id（template.html 与 player.js 的契约）
SHELL_IDS = ("title", "subtitle", "stage", "stacks", "stackgrid", "stack-note",
             "canvas-row", "term", "modebox", "ios-side", "term-col",
             "btn-first", "btn-prev", "btn-play", "btn-next", "btn-last",
             "speed", "btn-concept", "counter", "desc", "events",
             "concept-modal", "concept-body", "concept-close")


class PackagingTests(unittest.TestCase):
    def test_template_placeholders(self):
        template = (REPO / "template.html").read_text(encoding="utf-8")
        self.assertIn(generate.DATA_PLACEHOLDER, template)
        self.assertIn(generate.PLAYER_PLACEHOLDER, template)

    def test_player_has_no_data_placeholder(self):
        player = (REPO / "player.js").read_text(encoding="utf-8")
        self.assertNotIn(generate.DATA_PLACEHOLDER, player)
        self.assertIn("bootPlayer", player)
        self.assertIn("window.PLAYER", player)

    def test_shell_dom_ids(self):
        template = (REPO / "template.html").read_text(encoding="utf-8")
        player = (REPO / "player.js").read_text(encoding="utf-8")
        for dom_id in SHELL_IDS:
            self.assertIn(f'id="{dom_id}"', template)
            # stacks 面板由 CSS/HTML 承载，player 只用其内部两个 id；
            # stacks 面板由 CSS/HTML 承载，player 只用其内部两个 id
            if dom_id != "stacks":
                self.assertIn(dom_id, player)

    def test_render_escapes_closing_script_tag(self):
        document, _ = generate.build_document("encap", "cross-net")
        document["steps"][0]["description"] = "注入 </script> 尝试"
        template = (REPO / "template.html").read_text(encoding="utf-8")
        html = generate.render_html(document, template)
        self.assertIn("注入 <\\/script> 尝试", html)
        self.assertNotIn("注入 </script> 尝试", html)

    def test_render_missing_placeholder_rejected(self):
        document, _ = generate.build_document("encap", "cross-net")
        with self.assertRaises(RuntimeError):
            generate.render_html(document, "<html>no placeholders</html>")


class CliTests(unittest.TestCase):
    def run_cli(self, argv):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.html"
            generate.main(argv + ["-o", str(out)])
            return out.read_text(encoding="utf-8")

    def test_cli_cross_net(self):
        html = self.run_cli(["-p", "encap"])
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertNotIn("__DATA__", html)
        self.assertIn("封装与解封装 · 跨网段场景", html)
        self.assertIn("17 步", html)
        self.assertIn('"id": "R1"', html)

    def test_cli_same_net(self):
        html = self.run_cli(["-p", "encap", "-t", "same-net"])
        self.assertIn("封装与解封装 · 同网段场景", html)
        self.assertIn("12 步", html)
        self.assertNotIn('"id": "R1"', html)

    def test_cli_troubleshoot_three_scenarios(self):
        for scenario, title, name in (
            ("cable", "分层排错 · 物理层故障", "troubleshoot.html"),
            ("ip-config", "分层排错 · 网络层故障", "troubleshoot-ip.html"),
            ("service", "分层排错 · 应用层故障", "troubleshoot-service.html"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / name
                generate.main(["-p", "troubleshoot", "-t", scenario,
                               "-o", str(out)])
                html = out.read_text(encoding="utf-8")
                self.assertNotIn("__DATA__", html)
                self.assertIn(title, html)
                self.assertIn('"topic": "troubleshoot"', html)

    def test_cli_ios_three_scenarios(self):
        for scenario, title, name in (
            ("modes", "IOS 模式漫游", "ios.html"),
            ("save", "IOS 配置保存", "ios-save.html"),
            ("passwords", "IOS 密码", "ios-passwords.html"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / name
                generate.main(["-p", "ios", "-t", scenario, "-o", str(out)])
                html = out.read_text(encoding="utf-8")
                self.assertNotIn("__DATA__", html)
                self.assertIn(title, html)
                self.assertIn('"topic": "ios"', html)
                self.assertIn("终端回放", html)

    def test_cli_arp_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "arp.html"
            generate.main(["-p", "arp", "-t", "resolve", "-o", str(out)])
            html = out.read_text(encoding="utf-8")
            self.assertNotIn("__DATA__", html)
            self.assertIn("ARP 地址解析 · 首次通信全流程", html)
            self.assertIn('"topic": "arp"', html)
            self.assertIn("19 步", html)
            self.assertIn("共享总线广播域", html)
            self.assertIn('"id": "PC3"', html)

    def test_cli_default_output_names(self):
        # 默认输出名按 TOPICS 映射（encap→encap.html，troubleshoot→cable）
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                import os
                os.chdir(tmp)
                generate.main(["-p", "troubleshoot"])
                self.assertTrue((Path(tmp) / "troubleshoot.html").exists())
            finally:
                os.chdir(cwd)

    def test_cli_json_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.html"
            doc = Path(tmp) / "doc.json"
            generate.main(["-t", "same-net", "-o", str(out),
                           "--json", str(doc)])
            data = json.loads(doc.read_text(encoding="utf-8"))
            self.assertEqual(data["topic"], "encap")
            self.assertEqual(data["scenario"], "same-net")
            self.assertEqual(len(data["steps"]), 12)
            self.assertIn("chain", data)
            self.assertIn("concept", data)


if __name__ == "__main__":
    unittest.main()
