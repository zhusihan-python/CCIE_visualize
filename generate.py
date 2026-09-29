#!/usr/bin/env python3
"""Generate a self-contained step-animation HTML file (CCNA visualizer).

Examples:
    python3 generate.py                                   # encap cross-net
    python3 generate.py -t same-net                       # encap 同网段
    python3 generate.py -p troubleshoot                   # 排错·网线中断
    python3 generate.py -p troubleshoot -t service        # 排错·服务未启动
    python3 generate.py --json doc.json
"""

import argparse
import json
from pathlib import Path

import concepts
import encap
import ios
import troubleshoot

TEMPLATE_PATH = Path(__file__).with_name("template.html")
PLAYER_PATH = Path(__file__).with_name("player.js")
DATA_PLACEHOLDER = "__DATA__"
PLAYER_PLACEHOLDER = "/*__PLAYER__*/"

# 每个 topic 的场景表、标题与默认输出名统一收口在此
TOPICS = {
    "encap": {
        "scenarios": encap.SCENARIOS,
        "titles": {
            "cross-net": "封装与解封装 · 跨网段场景",
            "same-net": "封装与解封装 · 同网段场景",
        },
        "default_output": {"cross-net": "encap.html", "same-net": "encap-same.html"},
        "build": encap.simulate,
    },
    "troubleshoot": {
        "scenarios": troubleshoot.SCENARIOS,
        "titles": {
            "cable": "分层排错 · 物理层故障（网线中断）",
            "ip-config": "分层排错 · 网络层故障（IP 错配）",
            "service": "分层排错 · 应用层故障（服务未启动）",
        },
        "default_output": {
            "cable": "troubleshoot.html",
            "ip-config": "troubleshoot-ip.html",
            "service": "troubleshoot-service.html",
        },
        "build": troubleshoot.simulate,
    },
    "ios": {
        "scenarios": ios.SCENARIOS,
        "titles": {
            "modes": "IOS 模式漫游 · 三种模式与基本操作",
            "save": "IOS 配置保存 · running vs startup",
            "passwords": "IOS 密码 · Console 与 enable 双关卡",
        },
        "default_output": {
            "modes": "ios.html",
            "save": "ios-save.html",
            "passwords": "ios-passwords.html",
        },
        "build": ios.simulate,
    },
}


def _subtitle(topic, result):
    chain_ids = " → ".join(result.chain.ids())
    if topic == "ios":
        return f"{len(result.steps)} 步 · 终端回放"
    if topic == "troubleshoot":
        return f"{len(result.steps)} 步 · 自底向上逐层排查 · 设备链 {chain_ids}"
    return f"{len(result.steps)} 步 · 设备链 {chain_ids}"


def build_document(topic: str = "encap", scenario: str = None):
    """Run the story builder and return (embedded document, result).

    Shared by the CLI and the tests, mirroring the stpAlgorithmVisualizer
    convention."""
    if topic not in TOPICS:
        raise ValueError(f"unknown topic: {topic!r} "
                         f"(choose from {', '.join(TOPICS)})")
    spec = TOPICS[topic]
    if scenario is None:
        scenario = spec["scenarios"][0]
    if scenario not in spec["scenarios"]:
        raise ValueError(f"unknown scenario: {scenario!r} for topic {topic!r} "
                         f"(choose from {', '.join(spec['scenarios'])})")
    result = spec["build"](scenario)
    document = {
        "topic": topic,
        "scenario": scenario,
        "title": spec["titles"][scenario],
        "subtitle": _subtitle(topic, result),
        "chain": result.chain.serialize(),
        "concept": concepts.for_topic(topic, scenario),
        "steps": result.steps,
    }
    return document, result


def render_html(document: dict, template: str, player_js: str = None) -> str:
    if DATA_PLACEHOLDER not in template:
        raise RuntimeError("template.html is missing the __DATA__ placeholder")
    if player_js is None:
        player_js = PLAYER_PATH.read_text(encoding="utf-8")
    if PLAYER_PLACEHOLDER not in template:
        raise RuntimeError("template.html is missing the player placeholder")
    if DATA_PLACEHOLDER in player_js:
        raise RuntimeError("player.js must not contain the data placeholder")
    payload = json.dumps(document, ensure_ascii=False).replace("</", "<\\/")
    return (template
            .replace(DATA_PLACEHOLDER, payload)
            .replace(PLAYER_PLACEHOLDER, player_js))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-p", "--topic", choices=tuple(TOPICS), default="encap",
        help="visualization topic (default: encap)",
    )
    parser.add_argument(
        "-t", "--scenario", default=None,
        help="story scenario (default: encap→cross-net, troubleshoot→cable)",
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="output HTML file (default: per-topic/scenario name, see TOPICS)",
    )
    parser.add_argument(
        "--json", metavar="FILE",
        help="also dump the raw step data as JSON",
    )
    args = parser.parse_args(argv)
    spec = TOPICS[args.topic]
    if args.scenario is not None and args.scenario not in spec["scenarios"]:
        parser.error(f"-t/--scenario must be one of: "
                     f"{', '.join(spec['scenarios'])} (for topic {args.topic!r})")
    scenario = args.scenario or spec["scenarios"][0]
    output = args.output or spec["default_output"][scenario]

    document, result = build_document(args.topic, scenario)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    Path(output).write_text(render_html(document, template), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8")

    print(f"written: {output}")
    print(f"  topic={args.topic} scenario={scenario} "
          f"devices={len(result.chain.devices)} "
          f"links={len(result.chain.links)}")
    if args.topic == "troubleshoot":
        print(f"  steps={len(result.steps)} fault=L{result.fault_layer} "
              f"checks_until_hit={result.checks_until_hit}")
    elif args.topic == "ios":
        print(f"  steps={len(result.steps)} mode_changes={result.mode_changes}")
    else:
        print(f"  steps={len(result.steps)} "
              f"pdu={' → '.join(result.sender_pdu_names)} "
              f"mac_rewrites={result.mac_rewrites}")
    if args.json:
        print(f"written: {args.json}")


if __name__ == "__main__":
    main()
