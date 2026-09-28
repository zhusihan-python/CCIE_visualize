"""封装/解封装故事生成器（CCNA 第 02 课：网络参考模型）。

纯逻辑、无 I/O——沿用 stpAlgorithmVisualizer 的约定：每个步骤都是
完整快照（所在设备、PDU 形态、OSI 层号）并附中文讲解；播放器只做
哑渲染，不做任何故事逻辑。

故事：PC1 向 PC2 发送一条 HTTP 请求。
- scenario "cross-net"：PC1 → SW1 → R1（网关）→ SW2 → PC2。
  路由器校验并剥掉二层、按三层选路、重写 MAC 重新封装
  （IP 端到端不变、MAC 每跳改写——本场景核心对照点）。
- scenario "same-net"：PC1 → SW1 → PC2。
  全程无路由器，MAC 端到端不变，与跨网段场景互为对照。
"""

from dataclasses import dataclass

SCENARIOS = ("cross-net", "same-net")

# ---- 教学示意值（非真实抓包，仅保证自洽可读） --------------------------

PC1_IP = "192.168.1.10"
PC2_IP_CROSS = "192.168.2.10"
PC2_IP_SAME = "192.168.1.20"
PC1_MAC = "0200.0000.0001"
PC2_MAC = "0200.0000.0002"
R1_IFACES = (
    {"name": "G0/0", "ip": "192.168.1.1", "mac": "0200.0000.0011"},
    {"name": "G0/1", "ip": "192.168.2.1", "mac": "0200.0000.0012"},
)
SRC_PORT, DST_PORT = "1025", "80"
HTTP_REQ = "GET /index.html"


# ---- PDU 芯片（每一层的头/尾都是一个芯片，内容供画布直接绘制） ----------

def _chip(t, title, lines):
    return {"t": t, "title": title, "lines": list(lines)}


def data_chip(text=HTTP_REQ):
    return _chip("data", "数据", [text])


def tcp_chip(src=SRC_PORT, dst=DST_PORT):
    return _chip("tcp", "TCP 头", [f"源端口 {src}", f"目的端口 {dst}"])


def ip_chip(src, dst):
    return _chip("ip", "IP 头", [f"源 {src}", f"目 {dst}"])


def eth_chip(dst, src):
    # 目的 MAC 在前：真实以太网帧头就是「目的|源|类型」的顺序
    return _chip("eth", "以太网头", [f"目的 {dst}", f"源 {src}"])


def fcs_chip():
    return _chip("fcs", "FCS", ["校验"])


def bits_chip():
    return _chip("bits", "比特流", ["10110010 11000101 …"])


# ---- 设备链 ------------------------------------------------------------

@dataclass(frozen=True)
class Device:
    id: str
    kind: str                 # pc | switch | router
    label: str
    layer_range: tuple        # (1,7) / (1,2) / (1,3)
    ip: str = None
    mac: str = None
    interfaces: tuple = ()    # 仅路由器


@dataclass(frozen=True)
class Link:
    a: str
    b: str


@dataclass
class Chain:
    devices: list
    links: list

    def ids(self):
        return [d.id for d in self.devices]

    def serialize(self):
        return {
            "devices": [
                {
                    "id": d.id, "kind": d.kind, "label": d.label,
                    "layer_range": [d.layer_range[0], d.layer_range[1]],
                    "ip": d.ip, "mac": d.mac,
                    "interfaces": [dict(i) for i in d.interfaces],
                }
                for d in self.devices
            ],
            "links": [{"a": l.a, "b": l.b} for l in self.links],
        }


def cross_net_chain():
    return Chain(
        devices=[
            Device("PC1", "pc", "发送方 PC", (1, 7), PC1_IP, PC1_MAC),
            Device("SW1", "switch", "接入交换机", (1, 2)),
            Device("R1", "router", "网关路由器", (1, 3),
                   interfaces=R1_IFACES),
            Device("SW2", "switch", "对端交换机", (1, 2)),
            Device("PC2", "pc", "接收方 PC", (1, 7), PC2_IP_CROSS, PC2_MAC),
        ],
        links=[Link("PC1", "SW1"), Link("SW1", "R1"),
               Link("R1", "SW2"), Link("SW2", "PC2")],
    )


def same_net_chain():
    return Chain(
        devices=[
            Device("PC1", "pc", "发送方 PC", (1, 7), PC1_IP, PC1_MAC),
            Device("SW1", "switch", "接入交换机", (1, 2)),
            Device("PC2", "pc", "接收方 PC", (1, 7), PC2_IP_SAME, PC2_MAC),
        ],
        links=[Link("PC1", "SW1"), Link("SW1", "PC2")],
    )


CHAIN_BUILDERS = {"cross-net": cross_net_chain, "same-net": same_net_chain}


# ---- 步骤构造 -----------------------------------------------------------

def _step(kind, layer, device, pdu, pdu_name, description, bullets,
          events=None):
    return {
        "kind": kind,             # initial|encap|move|process|decap|final
        "layer": layer,           # OSI 层号 1..7；0 = 不高亮
        "device": device,         # PDU 当前所在设备
        "pdu": list(pdu),         # 芯片快照；move 步为 [bits]
        "pdu_name": pdu_name,     # 数据/段/包/帧/比特
        "description": description,
        "bullets": list(bullets),
        "events": events or [],   # 仅 move 步：比特流飞行动画
    }


def _sender_steps(dst_ip, eth, l2_note, l2_bullet):
    """PC1 自上而下的封装：L7 → L4 → L3 → L2，再变成比特出网线。"""
    data = data_chip()
    tcp = tcp_chip()
    ip = ip_chip(PC1_IP, dst_ip)
    return [
        _step("encap", 7, "PC1", [data], "数据 Data",
              "PC1 的应用层产生待发送的数据（这里以一条 HTTP 请求为例）。"
              "OSI 在这里细分为三层：应用层为程序提供网络服务，表示层做"
              "编码/压缩/加密，会话层负责建立/管理/终止会话；TCP/IP 模型"
              "把它们合并为一个「应用层」。无论用哪套模型数，这一层都是"
              "离用户最近的一层。",
              ["OSI 5–7 层 ≈ TCP/IP 应用层（合并看待）",
               "应用层：浏览器 / 邮件 / DNS 等程序产生数据",
               "当前 PDU：数据（Data）"]),
        _step("encap", 4, "PC1", [tcp, data], "段 Segment",
              "传输层给数据加上 TCP 头：源端口 1025、目的端口 80——"
              "端口号用来标明「哪个程序发的、交给哪个程序」（80 = HTTP）。"
              "TCP 就像顺丰快递，负责端到端的可靠交付（排序、重传等细节"
              "后续课程展开）。加了 TCP 头，数据变成了「段」。",
              ["TCP 头：源端口 1025 → 目的端口 80（HTTP）",
               "传输层管「端到端」：程序 ⇄ 程序",
               "当前 PDU：段（Segment）"]),
        _step("encap", 3, "PC1", [ip, tcp, data], "包 Packet",
              f"网络层再加 IP 头：源 IP {PC1_IP}、目的 IP {dst_ip}。"
              "IP 回答「我在哪、要去哪」——跨网段的路就靠它来指。"
              "记住这个对照点：这两个地址一旦写好，在整个旅程中都不会"
              "再改变（稍后在 R1 上可以验证）。",
              [f"IP 头：源 {PC1_IP} → 目的 {dst_ip}",
               "网络层管「跨网段」：负责选路与转发",
               "当前 PDU：包（Packet）"]),
        _step("encap", 2, "PC1", [eth, ip, tcp, data, fcs_chip()],
              "帧 Frame", l2_note,
              [f"以太网头：{l2_bullet}",
               "帧尾追加 FCS：接收方用它校验传输是否出错",
               "当前 PDU：帧（Frame）"]),
        _step("move", 1, "SW1", [bits_chip()], "比特 Bits",
              "物理层把帧变成比特流（网线上是电信号，光纤上是光信号），"
              "从 PC1 发往 SW1。从现在起到对端重组为止，数据都以比特形态"
              "存在——网线不认识「帧」，只搬运 0 和 1。",
              ["物理层：帧 → 比特流（电/光信号）",
               "本跳：PC1 ⇒ SW1",
               "当前 PDU：比特（Bits）"],
              events=[{"from": "PC1", "to": "SW1"}]),
    ]


def _relay_move(to_id, from_id):
    return _step("move", 1, to_id, [bits_chip()], "比特 Bits",
                 f"帧再次变成比特流，从 {from_id} 发往 {to_id}。",
                 [f"本跳：{from_id} ⇒ {to_id}",
                  "传输形态：比特（Bits）"],
                 events=[{"from": from_id, "to": to_id}])


def _switch_process(sw_id, frame):
    return _step("process", 2, sw_id, frame, "帧 Frame",
                 f"{sw_id} 是二层设备（L1–L2）。它把比特重组回帧，只读二层"
                 "的头部信息：查目的 MAC → 查 MAC 地址表 → 从对应端口转发。"
                 "帧的内容一个比特都不改。所谓「交换机工作在二层」，就是它"
                 "只需要看到第 2 层就能完成转发。",
                 ["交换机只看 L2：目的 MAC + MAC 地址表",
                  "帧内容原样转发（不改动）",
                  f"{sw_id} 活动层级：L1–L2"])


def _router_steps(frame_before):
    """路由器：拆帧选路 + 重写 MAC 重新封装（跨网段场景专属）。"""
    ip_only = frame_before[1:-1]              # 去掉 eth 与 fcs
    new_eth = eth_chip(f"PC2 {PC2_MAC}", f"R1·G0/1 {R1_IFACES[1]['mac']}")
    frame_after = [new_eth] + frame_before[1:]
    return frame_after, [
        _step("process", 3, "R1", ip_only, "包 Packet",
              "R1 是三层设备（L1–L3）。它先校验 FCS（没出错），然后剥掉"
              "以太网头尾，露出 IP 包——「拆到第几层，就说明它工作到第"
              "几层」。接着读三层信息：查目的 IP → 查路由表 → 命中直连"
              f"网段 192.168.2.0/24，从 {R1_IFACES[1]['name']} 接口发出。",
              ["拆帧：校验 FCS → 剥掉 L2 → 露出 IP 包",
               "查路由表：192.168.2.0/24 直连，出接口 G0/1",
               "R1 活动层级：L1–L3"]),
        _step("encap", 2, "R1", frame_after, "帧 Frame",
              "R1 为新出口重新封装一个新帧：源 MAC 换成自己的 G0/1"
              f"（{R1_IFACES[1]['mac']}），目的 MAC 换成 PC2（{PC2_MAC}）。"
              "全场最核心的对照来了——IP 头：源/目的还是两台 PC，端到端"
              "不变；MAC 头：每一跳都在改写。跨网段旅程中，「谁负责找路」"
              "（IP）与「谁负责这一跳送达」（MAC）就这样分工。",
              ["新帧：源 MAC = R1·G0/1，目的 MAC = PC2",
               f"IP 头不变：{PC1_IP} → {PC2_IP_CROSS}",
               "核心结论：IP 端到端不变，MAC 每跳改写"]),
    ]


def _receiver_steps(from_id, frame):
    """PC2 自下而上解封装：L2 → L3 → L4，应用层在读到数据时闭环。"""
    return [
        _relay_move("PC2", from_id),
        _step("decap", 2, "PC2", frame[1:-1], "包 Packet",
              "PC2 开始逐层解封装。链路层先做两个检查：FCS 校验通过"
              "（传输没出错）、目的 MAC 是自己（不是就丢弃），然后剥掉"
              "以太网头尾，把里面的 IP 包交给网络层。",
              ["校验 FCS：通过",
               "核对目的 MAC = 本机 → 收下",
               "剥掉 L2 → 得到 IP 包"]),
        _step("decap", 3, "PC2", frame[2:-1], "段 Segment",
              "网络层核对目的 IP = 本机地址 → 这个包确实是给我的；"
              "剥掉 IP 头，把「段」交给传输层。",
              ["核对目的 IP = 本机 → 接收",
               "剥掉 L3 → 得到段（Segment）"]),
        _step("decap", 4, "PC2", [frame[3]], "数据 Data",
              "传输层按目的端口 80 找到正在等待请求的 HTTP 程序，剥掉"
              "TCP 头。一路剥到最后，应用层读到的正是 PC1 当初写下的那句"
              "话——对等层对话完成：PC1 的应用层「说到」了 PC2 的应用层。",
              ["按目的端口 80 交付给 HTTP 程序",
               "剥掉 L4 → 数据（Data）完整送达",
               "对等层：PC1·应用层 ⇄ PC2·应用层"]),
    ]


# ---- 主入口 ------------------------------------------------------------

@dataclass
class EncapResult:
    scenario: str
    chain: Chain
    steps: list
    mac_rewrites: int          # 帧头被改写的次数（跨网段=1，同网段=0）
    sender_pdu_names: list     # 发送方 PDU 形态演变（测试/摘要用）


def simulate(scenario="cross-net"):
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario!r} "
                         f"(choose from {', '.join(SCENARIOS)})")
    cross = scenario == "cross-net"
    chain = CHAIN_BUILDERS[scenario]()
    dst_ip = PC2_IP_CROSS if cross else PC2_IP_SAME

    if cross:
        eth = eth_chip(f"R1·G0/0 {R1_IFACES[0]['mac']}", f"PC1 {PC1_MAC}")
        l2_note = (
            "数据链路层把整个 IP 包封装成以太网帧：帧头写 MAC 地址，帧尾"
            "追加 FCS 校验字段（用于差错检测）。关键细节：目的 MAC 填的"
            f"不是 PC2，而是默认网关 R1 的 G0/0 接口（{R1_IFACES[0]['mac']}"
            "）——PC1 一算就知道目的 IP 在别的网段，跨网段的流量要先交给"
            "网关（网关的 MAC 怎么知道？ARP 协议，后续课程）。MAC 回答"
            "「我是谁、这一跳交给谁」。")
        l2_bullet = (f"目的 MAC = 网关 R1·G0/0（{R1_IFACES[0]['mac']}），"
                     "源 MAC = PC1")
        initial_desc = (
            "跨网段场景：PC1（192.168.1.10）要把一段 HTTP 数据发给 PC2"
            "（192.168.2.10）——两者不在同一个网段，中间必须经过网关路由"
            "器 R1。观察方法：跟着数据形态走——在 PC1 自上而下层层加头"
            "（封装），变成比特穿越设备，再在 PC2 自下而上层层去头（解封"
            "装）。右侧面板是 OSI 七层与 TCP/IP 模型的逐层对照，当前步会"
            "点亮对应层。口诀：物数网传会表应（1→7）。")
        initial_bullets = [
            "设备链：PC1 → SW1 → R1（网关）→ SW2 → PC2",
            "两个网段：192.168.1.0/24 与 192.168.2.0/24",
            "看什么：加头/去头的过程 + 每台设备「看到第几层」",
        ]
        final_desc = (
            "全程回顾：PC1 自上而下封装（数据→段→包→帧→比特），每层加"
            "自己的头；SW1/SW2 只看二层、原样转发；R1 拆到三层、选路后"
            "重写 MAC 重新封装；PC2 自下而上解封装还原数据。两句话带走："
            "① 头加到第几层 / 设备拆到第几层 = 它工作在第几层；② IP 端"
            "到端不变，MAC 每跳改写（跨网段时由路由器改写）。点击右上角"
            "「📖 原理」看分层意义与排错思路。")
        final_bullets = [
            "封装：数据 → 段 → 包 → 帧 → 比特（自上而下加头）",
            "转发：交换机看 L2 原样转；路由器拆到 L3 重新封装",
            "结论：IP 端到端不变；MAC 每跳改写",
        ]
    else:
        eth = eth_chip(f"PC2 {PC2_MAC}", f"PC1 {PC1_MAC}")
        l2_note = (
            "数据链路层封装以太网帧：帧头写 MAC 地址，帧尾追加 FCS 校验"
            f"字段。同网段的关键差别在这里：PC1 一算，目的 IP {PC2_IP_SAME}"
            " 和自己同属一个网段 → 不需要网关，目的 MAC 直接填 PC2 本身"
            f"（{PC2_MAC}）。它的 MAC 怎么知道？ARP 协议，后续课程展开。"
            "MAC 回答「我是谁、这一跳交给谁」。")
        l2_bullet = f"目的 MAC = PC2（{PC2_MAC}），源 MAC = PC1"
        initial_desc = (
            "同网段场景：PC1（192.168.1.10）给 PC2（192.168.1.20）发数据"
            "——两者同属 192.168.1.0/24，中间只需要一台交换机，全程不经过"
            "路由器。带着对照问题看：这个场景里 MAC 地址会不会变？"
            "（对照跨网段场景：那里每过一台路由器，MAC 就被改写一次。）"
            "口诀：物数网传会表应（1→7）。")
        initial_bullets = [
            "设备链：PC1 → SW1 → PC2（无路由器）",
            "同一网段：192.168.1.0/24",
            "对照问题：MAC 地址端到端变不变？",
        ]
        final_desc = (
            "全程回顾：同网段通信没有任何设备改写帧头——PC1 写下的目的"
            " MAC 原封不动到达 PC2。对照结论：MAC 只在跨网段、经过路由器"
            "时才被改写；IP 头则无论哪个场景都端到端不变。交换机始终只看"
            "二层。点击右上角「📖 原理」看分层意义与排错思路。")
        final_bullets = [
            "封装/解封装过程与跨网段完全相同",
            "本场景 MAC 端到端不变（无路由器改写）",
            "对照：跨网段时路由器每跳重写 MAC",
        ]

    steps = [_step("initial", 0, "PC1", [], "—",
                   initial_desc, initial_bullets)]
    steps += _sender_steps(dst_ip, eth, l2_note, l2_bullet)
    sender_pdu_names = [s["pdu_name"] for s in steps[1:]]

    sender_frame = steps[-2]["pdu"]          # L2 封装完成时的帧
    if cross:
        steps.append(_switch_process("SW1", sender_frame))
        steps.append(_relay_move("R1", "SW1"))
        router_frame, router_steps = _router_steps(sender_frame)
        steps += router_steps
        steps.append(_relay_move("SW2", "R1"))
        steps.append(_switch_process("SW2", router_frame))
        steps += _receiver_steps("SW2", router_frame)
    else:
        steps.append(_switch_process("SW1", sender_frame))
        steps += _receiver_steps("SW1", sender_frame)

    steps.append(_step("final", 0, "PC2", [data_chip()], "数据 Data",
                       final_desc, final_bullets))

    return EncapResult(
        scenario=scenario,
        chain=chain,
        steps=steps,
        mac_rewrites=1 if cross else 0,
        sender_pdu_names=sender_pdu_names,
    )
