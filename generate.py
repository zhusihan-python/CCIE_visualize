#!/usr/bin/env python3
"""Generate a self-contained encapsulation-animation HTML file.

Examples:
    python3 generate.py                                # cross-net -> encap.html
    python3 generate.py -t same-net -o encap-same.html # 同网段对照场景
    python3 generate.py --json doc.json
"""

import argparse
import json
from pathlib import Path

import concepts
import encap

TEMPLATE_PATH = Path(__file__).with_name("template.html")
PLAYER_PATH = Path(__file__).with_name("player.js")
DATA_PLACEHOLDER = "__DATA__"
PLAYER_PLACEHOLDER = "/*__PLAYER__*/"

SCENARIO_TITLES = {
    "cross-net": "封装与解封装 · 跨网段场景",
    "same-net": "封装与解封装 · 同网段场景",
}


def build_document(topic: str = "encap", scenario: str = "cross-net"):
    """Run the story builder and return (embedded document, result).

    Shared by the CLI and the tests, mirroring the stpAlgorithmVisualizer
    convention."""
    if topic != "encap":
        raise ValueError(f"unknown topic: {topic!r}")
    result = encap.simulate(scenario)
    chain_ids = " → ".join(result.chain.ids())
    document = {
        "topic": topic,
        "scenario": scenario,
        "title": SCENARIO_TITLES[scenario],
        "subtitle": f"{len(result.steps)} 步 · 设备链 {chain_ids}",
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
        "-p", "--topic", choices=("encap",), default="encap",
        help="visualization topic (default: encap)",
    )
    parser.add_argument(
        "-t", "--scenario", choices=encap.SCENARIOS, default="cross-net",
        help="story scenario (default: cross-net)",
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="output HTML file (default: encap.html / encap-same.html)",
    )
    parser.add_argument(
        "--json", metavar="FILE",
        help="also dump the raw step data as JSON",
    )
    args = parser.parse_args(argv)
    output = args.output or ("encap.html" if args.scenario == "cross-net"
                             else "encap-same.html")

    document, result = build_document(args.topic, args.scenario)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    Path(output).write_text(render_html(document, template), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8")

    print(f"written: {output}")
    print(f"  topic={args.topic} scenario={args.scenario} "
          f"devices={len(result.chain.devices)} "
          f"links={len(result.chain.links)}")
    print(f"  steps={len(result.steps)} "
          f"pdu={' → '.join(result.sender_pdu_names)} "
          f"mac_rewrites={result.mac_rewrites}")
    if args.json:
        print(f"written: {args.json}")


if __name__ == "__main__":
    main()
