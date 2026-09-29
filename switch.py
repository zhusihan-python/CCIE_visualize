"""以太网交换机故事生成器（CCNA 第 05 课：以太网交换机工作原理）。

纯逻辑、无 I/O——沿用系列约定：每个步骤都是完整快照（所在设备、OSI 层号、
当前帧字段、SW1 的 MAC 地址表、接收判定）并附中文讲解；播放器只做哑渲染。
星型拓扑由渲染层专属分支绘制（SW1 居中 + 斜线链路 + 端口标注）。

场景 learn：MAC 学习 → 未知单播泛洪 → 精准转发的完整闭环，含广播 beat
（ARP 广播帧不查表直接泛洪——泛洪的两种触发同屏对照）。
场景 aging：表项 300 秒未使用 → 删除 → 再通信重现泛洪 → 重学习。
时间快进为步进快照呈现（沿用 arp 既定口径，不真实计时）。
"""

from dataclasses import dataclass

SCENARIOS = ("learn", "aging")

# ---- 教学示意值（与 arp 系列同网段同 MAC，故事可直接衔接） --------------

PC1_IP, PC2_IP, PC3_IP = "192.168.1.1", "192.168.1.2", "192.168.1.3"
PC1_MAC, PC2_MAC, PC3_MAC = ("0200.0000.0001", "0200.0000.0002",
                             "0200.0000.0003")
BROADCAST_MAC = "ffff.ffff.ffff"      # 即 FF-FF-FF-FF-FF-FF（48 bit 全 1）
PORT_PC1, PORT_PC2, PORT_PC3 = "g0/1", "g0/2", "g0/3"


# ---- 设备链 ------------------------------------------------------------

@dataclass(frozen=True)
class Device:
    id: str
    kind: str                 # pc | switch
    label: str
    layer_range: tuple        # (1,7) / (1,2)
    ip: str = None
    mac: str = None


@dataclass(frozen=True)
class Link:
    a: str                    # SW1
    b: str                    # PCx
    port: str                 # SW1 侧端口标注（星型专属渲染使用）


@dataclass
class Chain:
    devices: list
    links: list

    def ids(self):
        return [d.id for d in self.devices]

    def serialize(self):
        return {
            "devices": [
                {"id": d.id, "kind": d.kind, "label": d.label,
                 "layer_range": [d.layer_range[0], d.layer_range[1]],
                 "ip": d.ip, "mac": d.mac, "interfaces": []}
                for d in self.devices
            ],
            "links": [
                {"a": l.a, "b": l.b, "port": l.port} for l in self.links
            ],
        }


def star_chain():
    return Chain(
        devices=[
            Device("SW1", "switch", "以太网交换机", (1, 2)),
            Device("PC1", "pc", "终端", (1, 7), PC1_IP, PC1_MAC),
            Device("PC2", "pc", "终端", (1, 7), PC2_IP, PC2_MAC),
            Device("PC3", "pc", "终端", (1, 7), PC3_IP, PC3_MAC),
        ],
        links=[
            Link("SW1", "PC1", PORT_PC1),
            Link("SW1", "PC2", PORT_PC2),
            Link("SW1", "PC3", PORT_PC3),
        ],
    )


# ---- 步骤构造 -----------------------------------------------------------

def _field(k, v, tone=None, hot=False):
    # tone: bcast 广播（红）/ uni 单播（绿）/ unk 未知（琥珀）/ None 常规
    return {"k": k, "v": v, "tone": tone, "hot": hot}


def _cool(fields):
    return [{**f, "hot": False} for f in fields]


def _row(mac, port, age="300s", new=False):
    return {"mac": mac, "port": port, "type": "动态", "age": age, "new": new}


def _step(kind, layer, device, phase, description, bullets, *,
          events=None, fields=None, mac_table=None, flash=None):
    return {
        "kind": kind,             # initial | process | move | final
        "layer": layer,           # 1..7；initial/final 为 0（不高亮）
        "device": device,
        "pdu_name": phase,        # 右上角阶段标签（测试 ground truth）
        "description": description,
        "bullets": list(bullets),
        "events": events or [],   # 仅 move 步：星型飞行粒子（kind=frame）
        "fields": fields or [],   # 左下面板：当前帧字段快照
        "mac_table": mac_table or [],
        "flash": flash or {},     # 接收判定胶囊 {设备: {ok, text}}
    }


# ---- 帧字段面板快照 -----------------------------------------------------

def icmp_fields(dst_note, src_note, hot=True):
    return [
        _field("以太网头 · 目的 MAC", dst_note, "uni", hot),
        _field("以太网头 · 源 MAC", src_note, "uni"),
        _field("类型", "0x0800（IPv4）", None, hot),
        _field("FCS", "校验 ✓（帧完好）"),
    ]


def arp_broadcast_fields(hot=True):
    return [
        _field("以太网头 · 目的 MAC", f"{BROADCAST_MAC}（广播）", "bcast", hot),
        _field("以太网头 · 源 MAC", f"{PC1_MAC}（PC1）", "uni"),
        _field("类型", "0x0806（ARP）", None, hot),
        _field("FCS", "校验 ✓（帧完好）"),
    ]


# ---- 主入口 ------------------------------------------------------------

LEARN_PHASES = (
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
)

AGING_PHASES = (
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
)


@dataclass
class SwitchResult:
    scenario: str
    chain: Chain
    steps: list
    flood_steps: list           # 同源多目的（泛洪）的步索引
    learn_steps: list           # MAC 表新增行的步索引
    phase_names: list


def _simulate_learn():
    chain = star_chain()
    empty = []
    mac1_new = [_row(PC1_MAC, PORT_PC1, new=True)]
    mac1 = [_row(PC1_MAC, PORT_PC1)]
    two_new = [_row(PC1_MAC, PORT_PC1), _row(PC2_MAC, PORT_PC2, new=True)]
    two = [_row(PC1_MAC, PORT_PC1), _row(PC2_MAC, PORT_PC2)]
    two_refresh = [_row(PC1_MAC, PORT_PC1, age="↻ 300s 刷新"),
                   _row(PC2_MAC, PORT_PC2)]

    steps = [
        _step("initial", 0, "SW1", LEARN_PHASES[0],
              "承接前两篇：ARP 已经把「谁是谁」解决了，总线也把「人人可听」"
              "演到了极致。现在把中间的总线换成一台真正的以太网交换机 SW1"
              "——三块网卡各接一个口（g0/1–g0/3），右下的 MAC 地址表开局"
              "全空。交换机的工作就从这张表开始：每收到一个帧，先学源 MAC，"
              "再查目的 MAC。看什么：表什么时候长出第一行、帧什么时候还在"
              "「打扰全村」、什么时候变成点对点专送。",
              ["拓扑：SW1 居中，PC1/PC2/PC3 分别接 g0/1 / g0/2 / g0/3",
               "交换机工作在二层：只看 MAC，与 IP 无关",
               "看什么：MAC 表何时 +1、泛洪何时变成精准转发"],
              mac_table=empty),
        _step("process", 3, "PC1", LEARN_PHASES[1],
              "PC1 要 ping 192.168.1.2。ARP 上一课已经完成——目的 MAC 直接"
              f"填 PC2（{PC2_MAC}），帧头三件套齐了：目的 MAC、源 MAC、类型"
              " 0x0800（里面是 IPv4 包），帧尾 FCS 保证没坏。这个帧从网线"
              "发往 SW1 的 g0/1 口。",
              ["帧：目的=PC2 单播 / 源=PC1 / 类型 0x0800（IPv4）/ FCS",
               "ARP 已完成（上篇）——目的 MAC 直接可用",
               "入端口：g0/1"],
              fields=[
                  _field("以太网头 · 目的 MAC",
                         f"{PC2_MAC}（PC2 · 单播）", "uni", True),
                  _field("以太网头 · 源 MAC", f"{PC1_MAC}（PC1）", "uni"),
                  _field("类型", "0x0800（IPv4）", None, True),
                  _field("FCS", "校验 ✓（帧完好）"),
              ],
              mac_table=empty),
        _step("process", 2, "SW1", LEARN_PHASES[2],
              "SW1 在 g0/1 收到这个帧。第一个动作不是转发，而是学习：读帧"
              f"的源 MAC——{PC1_MAC}，查表没有 → 记录「这个 MAC 从 g0/1 来」"
              "（右下表 +1）。笔记原话：交换机靠源 MAC 生成表——哪个口进来"
              "的，源 MAC 就记在哪个口。",
              [f"学习：源 MAC {PC1_MAC} → 端口 g0/1（表 +1）",
               "一个端口可以学到多个 MAC；已存在则刷新老化",
               "交换机最核心的功能之一：MAC Learning"],
              fields=[
                  _field("以太网头 · 源 MAC",
                         f"{PC1_MAC} → 记为 g0/1", None, True),
                  _field("学习依据", "源 MAC + 入端口", None, True),
                  _field("FCS", "校验 ✓（帧完好）"),
              ],
              mac_table=mac1_new),
        _step("process", 2, "SW1", LEARN_PHASES[3],
              "第二个动作才是查表转发：读目的 MAC——"
              f"{PC2_MAC}，查 MAC 地址表：没有！这个帧是「未知单播帧」。"
              "交换机不知道 PC2 在哪个口，只能把帧泛洪：从除入口 g0/1 之外"
              "的所有端口发出去。",
              [f"查表：目的 {PC2_MAC} → 未命中（未知单播帧）",
               "泛洪规则：除入口端口外，全部转发",
               "现在表里只有 PC1——PC2 还没「报过到」"],
              fields=[
                  _field("以太网头 · 目的 MAC",
                         f"{PC2_MAC}（PC2）→ 查表 ✗", None, True),
                  _field("判定", "未知单播 → 泛洪（g0/2 + g0/3）", None,
                         True),
                  _field("FCS", "校验 ✓（帧完好）"),
              ],
              mac_table=mac1),
        _step("move", 1, "SW1", LEARN_PHASES[4],
              "泛洪出发：两份复制帧同时沿 g0/2、g0/3 下行——注意 g0/1 安安"
              "静静，帧绝不从入口原路返回。对照上一篇的总线：此刻的交换机"
              "还没比总线聪明多少（PC3 也得听），但它已经在攒表了。",
              ["泛洪：SW1 → PC2（g0/2）与 SW1 → PC3（g0/3）同时起飞",
               "不回入口 g0/1——泛洪的第一条铁律",
               "未知单播泛洪 =「不知道 → 都问一遍」"],
              events=[
                  {"from": "SW1", "to": "PC2", "kind": "frame",
                   "label": "未知单播 · 泛洪", "hue": "icmp"},
                  {"from": "SW1", "to": "PC3", "kind": "frame",
                   "label": "未知单播 · 泛洪", "hue": "icmp"},
              ],
              fields=_cool(icmp_fields(f"{PC2_MAC}（PC2）", f"{PC1_MAC}（PC1）")),
              mac_table=mac1),
        _step("process", 2, "PC3", LEARN_PHASES[5],
              "PC3 的网卡收到这帧：目的 MAC 是 PC2 的单播地址，不是我——"
              "直接丢弃（和总线时代一模一样）。PC3 的沉默不是失礼，是以太"
              "网的规矩：单播帧，只有目的网卡点头。",
              ["PC3：目的 MAC ≠ 本机 → 网卡丢弃",
               "与总线篇的 PC3 行为一致——MAC 过滤在网卡",
               "泛洪是交换机的无奈，过滤是网卡的日常"],
              fields=_cool(icmp_fields(f"{PC2_MAC}（PC2）", f"{PC1_MAC}（PC1）")),
              mac_table=mac1,
              flash={"PC3": {"ok": False, "text": "丢弃 · 目的 MAC 不是我"}}),
        _step("process", 2, "PC2", LEARN_PHASES[6],
              "PC2 收到：目的 MAC 是我——收下，交付给上层（ICMP 应答任务）。"
              "PC2 立刻构造回程帧：源 MAC 换成自己、目的 MAC 填 PC1（这个"
              "地址从请求帧里一眼可见），从网线发往 SW1 的 g0/2。",
              ["PC2：目的 MAC = 本机 → 收下（ICMP 回应）",
               "回程帧：源=PC2 / 目的=PC1 / 类型 0x0800",
               "入端口：g0/2"],
              fields=icmp_fields(f"{PC1_MAC}（PC1 · 单播）", f"{PC2_MAC}（PC2）"),
              mac_table=mac1,
              flash={"PC2": {"ok": True, "text": "收下 · 是我的"}}),
        _step("process", 2, "SW1", LEARN_PHASES[7],
              "回程帧从 g0/2 进入 SW1——学习时间：源 MAC "
              f"{PC2_MAC} → g0/2，表再 +1，两行了。此刻 SW1 已经知道两位"
              "住户的门牌。",
              [f"学习：{PC2_MAC} → g0/2（表 +1，共 2 行）",
               "学习永远发生在「收帧的入口」",
               "两行表在手，下一次查表就有得查了"],
              fields=[
                  _field("以太网头 · 源 MAC",
                         f"{PC2_MAC} → 记为 g0/2", None, True),
                  _field("学习依据", "源 MAC + 入端口", None, True),
                  _field("FCS", "校验 ✓（帧完好）"),
              ],
              mac_table=two_new),
        _step("process", 2, "SW1", LEARN_PHASES[8],
              f"再查表：目的 MAC {PC1_MAC}——命中 g0/1！这是「已知单播"
              "帧」。交换机知道 PC1 就住在 g0/1，于是只从 g0/1 精准发出，"
              "g0/3 一点动静都没有。",
              [f"查表：{PC1_MAC} → 命中 g0/1（已知单播帧）",
               "精准转发：只发 g0/1，1 对 1",
               "「能送到 → 转发」"],
              fields=[
                  _field("以太网头 · 目的 MAC",
                         f"{PC1_MAC} → 命中 g0/1 ✓", None, True),
                  _field("判定", "已知单播 → 精准转发 g0/1", None, True),
                  _field("FCS", "校验 ✓（帧完好）"),
              ],
              mac_table=two),
        _step("move", 1, "SW1", LEARN_PHASES[9],
              "应答帧精准降落在 PC1——与第 5 步的泛洪同屏对照：同样的交换"
              "机，查表命中后只打扰一个人。ping 通了。",
              ["精准转发：SW1 → PC1，单航线",
               "对照第 5 步：未知时泛洪 2 份，已知时专送 1 份"],
              events=[{"from": "SW1", "to": "PC1", "kind": "frame",
                       "label": "已知单播 · 精准转发", "hue": "icmp"}],
              fields=_cool(icmp_fields(f"{PC1_MAC}（PC1）", f"{PC2_MAC}（PC2）")),
              mac_table=two),
        _step("process", 3, "PC1", LEARN_PHASES[10],
              "PC1 的 ping 圆满闭环。此刻右下 MAC 表恰好两行（PC1→g0/1、"
              "PC2→g0/2），PC1 与 PC2 之后的每次通信都是帧帧 1 对 1——"
              "PC3 再也听不到它们的私聊。这就是交换机对总线的全部改进："
              "学得越多，打扰越少。",
              ["ping 通；MAC 表 2 行：PC1→g0/1、PC2→g0/2",
               "此后 PC1⇄PC2 全部精准转发，PC3 全程安静",
               "交换机的价值：学得越多，泛洪越少"],
              fields=_cool(icmp_fields(f"{PC2_MAC}（PC2）", f"{PC1_MAC}（PC1）")),
              mac_table=two),
        _step("process", 2, "PC1", LEARN_PHASES[11],
              "新剧情：PC1 的 ARP 缓存过期了（或要找一台新设备），需要重新"
              "广播 ARP 请求。看字段面板的变化：目的 MAC 填 "
              f"{BROADCAST_MAC}（广播），类型换成 0x0806（ARP）。广播帧天生"
              "就是「发给所有人」的帧。",
              [f"ARP 请求帧：目的 = {BROADCAST_MAC}（广播）/ 类型 0x0806",
               "广播帧 = 发给本广播域所有设备（ARP 请求是典型）",
               "帧照常从 g0/1 进入 SW1"],
              fields=arp_broadcast_fields(),
              mac_table=two),
        _step("process", 2, "SW1", LEARN_PHASES[12],
              "g0/1 又收到 PC1 的帧：学习动作照做——源 MAC 已在表中，那就"
              "刷新它的老化计时（重新计 300 秒），不新增行。查表转发：目的"
              " MAC 是广播地址——广播帧不查表，直接泛洪。泛洪的两种触发在"
              "这一步凑齐了：未知单播（不知道才问）与广播（天生给所有人）。",
              ["学习：源 MAC 已存在 → 刷新老化（不新增行）",
               "广播帧不查表 → 无条件泛洪（除入口外）",
               "泛洪两触发对照：未知单播 / 广播帧"],
              fields=[
                  _field("学习", "源 MAC 已在 g0/1 → 刷新老化 ↻", None, True),
                  _field("查表", "目的 = 广播 → 不查表，直接泛洪", None,
                         True),
                  _field("类型", "0x0806（ARP）"),
              ],
              mac_table=two_refresh),
        _step("move", 1, "SW1", LEARN_PHASES[13],
              "第二次泛洪：即使 MAC 表已经有两行，广播帧照样发给 g0/2 和 "
              "g0/3——这不是交换机没记住，是广播帧的语义本就如此。",
              ["泛洪：g0/2 + g0/3（表再满也拦不住广播）",
               "对照：上一泛洪因「未知」，这一泛洪因「广播」"],
              events=[
                  {"from": "SW1", "to": "PC2", "kind": "frame",
                   "label": "广播帧 · 泛洪", "hue": "arp"},
                  {"from": "SW1", "to": "PC3", "kind": "frame",
                   "label": "广播帧 · 泛洪", "hue": "arp"},
              ],
              fields=_cool(arp_broadcast_fields()),
              mac_table=two_refresh),
        _step("process", 2, "PC2", LEARN_PHASES[14],
              "同一帧广播，两种结局：PC2 一看 ARP 问的目标 IP 是自己——认领，"
              "准备单播应答；PC3 看目的 MAC 是广播、但问的目标 IP 不是自己"
              "——沉默丢弃。与 ARP 篇的剧本分毫不差：广播问、单播答。",
              ["PC2：目标 IP = 本机 → 认领（ARP 应答待发）",
               "PC3：非目标 → 沉默丢弃",
               "广播问、单播答——第 4 课的规律原样适用"],
              fields=_cool(arp_broadcast_fields()),
              mac_table=two_refresh,
              flash={"PC2": {"ok": True, "text": "收下 · 问的是我"},
                     "PC3": {"ok": False, "text": "丢弃 · 目标 IP 不是我"}}),
        _step("move", 1, "SW1", LEARN_PHASES[15],
              "ARP 应答以单播发出：先入 SW1 的 g0/2，SW1 一查表——目的 PC1 "
              "命中 g0/1，精准转出。两段航线一气呵成：问的时候全村听，答的"
              "时候专线达。",
              ["应答回程：PC2 → SW1（g0/2 入）→ 精准转发 PC1",
               "表已两行：应答全程 1 对 1"],
              events=[
                  {"from": "PC2", "to": "SW1", "kind": "frame",
                   "label": "ARP 应答（单播）", "hue": "arp"},
                  {"from": "SW1", "to": "PC1", "kind": "frame",
                   "label": "ARP 应答（单播）", "hue": "arp", "delay": 1},
              ],
              fields=[
                  _field("以太网头 · 目的 MAC", f"{PC1_MAC}（PC1 · 单播）",
                         "uni", False),
                  _field("以太网头 · 源 MAC", f"{PC2_MAC}（PC2）", "uni"),
                  _field("类型", "0x0806（ARP）"),
                  _field("FCS", "校验 ✓（帧完好）"),
              ],
              mac_table=two_refresh),
        _step("final", 0, "SW1", LEARN_PHASES[16],
              "全程回顾：交换机收帧两步走——先学源（源 MAC + 入端口，已有"
              "则刷新老化），再查目。三种行为：能送到 → 转发（已知单播，"
              "1 对 1）；不知道 → 泛洪（未知单播，除入口外全部；广播帧不查"
              "表直接泛洪）；有问题 → 丢弃（本篇未演，见「📖 原理」）。与总"
              "线篇对照：交换机用一张 MAC 表换来了「学得越多、打扰越少」。"
              "下一个问题：这张表会一直记着吗？——下一篇：老化。",
              ["两步走：先学源（源 MAC + 入端口）→ 再查目",
               "口诀：能送到→转发 / 不知道→泛洪 / 有问题→丢弃",
               "下一篇：MAC 表会忘——老化与重学习"],
              mac_table=two),
    ]

    flood = [i for i, s in enumerate(steps)
             if len(s["events"]) > 1 and
             len({e["from"] for e in s["events"]}) == 1]
    learn = [i for i, s in enumerate(steps)
             if any(r.get("new") for r in s["mac_table"])]
    return SwitchResult("learn", chain, steps, flood, learn,
                        [s["pdu_name"] for s in steps])


def _simulate_aging():
    chain = star_chain()
    two_300 = [_row(PC1_MAC, PORT_PC1), _row(PC2_MAC, PORT_PC2)]
    two_180 = [_row(PC1_MAC, PORT_PC1, age="180s"),
               _row(PC2_MAC, PORT_PC2, age="180s")]
    two_0 = [_row(PC1_MAC, PORT_PC1, age="0s"),
             _row(PC2_MAC, PORT_PC2, age="0s")]
    empty = []
    mac1_new = [_row(PC1_MAC, PORT_PC1, new=True)]
    mac1 = [_row(PC1_MAC, PORT_PC1)]
    two_new = [_row(PC1_MAC, PORT_PC1), _row(PC2_MAC, PORT_PC2, new=True)]
    two = [_row(PC1_MAC, PORT_PC1), _row(PC2_MAC, PORT_PC2)]

    steps = [
        _step("initial", 0, "SW1", AGING_PHASES[0],
              "承接上篇结尾：MAC 表两行（PC1→g0/1、PC2→g0/2），一切精准。"
              "但每行表项都带着一个倒计时——老化时间（默认 300 秒）：表项"
              "只有在「持续被使用」时才活着。本篇就看它怎么被忘掉、又怎么"
              "被想起。",
              ["表 2 行：PC1→g0/1、PC2→g0/2（老化 300s 起跳）",
               "老化规则：表项被再次使用 → 刷新计时；300 秒无人问津 → 删除",
               "看什么：表什么时候清空、清空后再通信会发生什么"],
              mac_table=two_300),
        _step("process", 2, "SW1", AGING_PHASES[1],
              "⏩ 时间快进——PC1 和 PC2 之间整整 120 秒没有任何帧往来。两行"
              "表项的倒计时安静走着：300 → 180。",
              ["⏩ 快进 120 秒：PC1/PC2 无通信",
               "老化计时：300s → 180s（右下表可见）",
               "计时未到——表项仍在"],
              fields=[_field("老化计时", "300s → 180s", None, True),
                      _field("表项", "2 行仍在（未被使用）"),
                      _field("通信状态", "PC1 ⇄ PC2 静默")],
              mac_table=two_180),
        _step("process", 2, "SW1", AGING_PHASES[2],
              "⏩ 继续快进——又是 180 秒无通信，倒计时归零。",
              ["⏩ 再快进 180 秒：依旧无通信",
               "老化计时：180s → 0s",
               "归零即删——下一步见"],
              fields=[_field("老化计时", "180s → 0s", None, True),
                      _field("表项", "2 行仍在（摇摇欲坠）"),
                      _field("通信状态", "PC1 ⇄ PC2 静默")],
              mac_table=two_0),
        _step("process", 2, "SW1", AGING_PHASES[3],
              "计时归零，SW1 把两行表项删除——MAC 表回到开局的白纸。这不是"
              "故障，是交换机的自我维护：留着没人用的表项，万一设备换了端口，"
              "表就成了错误地图。作业 2 第二问的答案就在这：老化时间到了，"
              "表项会被删除。",
              ["300s 无使用 → 两行表项删除（表清空）",
               "删除不是故障：防止「设备换端口后表指错」",
               "作业 2：老化到 → 删除 ✓"],
              fields=[_field("老化计时", "0s → 删除", None, True),
                      _field("MAC 表", "（空）", "unk", True),
                      _field("通信状态", "PC1 ⇄ PC2 静默")],
              mac_table=empty),
        _step("process", 3, "PC1", AGING_PHASES[4],
              "PC1 浑然不觉，又 ping 了一次 192.168.1.2。注意两张表的错位："
              "PC1 自己的 ARP 表还留着 PC2 的映射（ARP 老化通常更久），所以"
              "帧照常构造、目的 MAC 直接填 PC2——但交换机的 MAC 表已经空了。"
              "两张表、两套老化、两个主人：ARP 表归 PC 的系统管，MAC 表归"
              "交换机管。",
              ["PC1 的 ARP 表还在 → 目的 MAC 直接可用（帧照常发）",
               "交换机的 MAC 表已空——两张表是不同的表！",
               "ARP 表在 PC（系统管）/ MAC 表在交换机（SW1 管）"],
              fields=[
                  _field("以太网头 · 目的 MAC",
                         f"{PC2_MAC}（PC2 · ARP 表查得）", "uni", True),
                  _field("类型", "0x0800（IPv4）"),
                  _field("FCS", "校验 ✓（帧完好）"),
              ],
              mac_table=empty),
        _step("process", 2, "SW1", AGING_PHASES[5],
              "帧从 g0/1 进入空表的 SW1。先学源："
              f"{PC1_MAC} → g0/1，表 +1。再查目：{PC2_MAC}——又没了！未知"
              "单播，泛洪。整个剧本回到上篇开头：老化删掉的记忆，用一次泛洪"
              "换回来。",
              [f"学习：{PC1_MAC} → g0/1（表 +1）",
               "查表：未命中 → 未知单播 → 泛洪",
               "老化删除的代价：重现一次泛洪"],
              fields=[
                  _field("以太网头 · 源 MAC",
                         f"{PC1_MAC} → 记为 g0/1", None, True),
                  _field("判定", "未知单播 → 泛洪（g0/2 + g0/3）", None,
                         True),
                  _field("FCS", "校验 ✓（帧完好）"),
              ],
              mac_table=mac1_new),
        _step("move", 1, "SW1", AGING_PHASES[6],
              "泛洪照旧：g0/2、g0/3 同时出发，g0/1 保持安静。PC3 又被无奈地"
              "打扰了一次——这就是 MAC 表空着的代价。",
              ["泛洪：g0/2 + g0/3（PC3 又被牵连）",
               "与上篇第一次泛洪完全同款"],
              events=[
                  {"from": "SW1", "to": "PC2", "kind": "frame",
                   "label": "未知单播 · 泛洪", "hue": "icmp"},
                  {"from": "SW1", "to": "PC3", "kind": "frame",
                   "label": "未知单播 · 泛洪", "hue": "icmp"},
              ],
              fields=_cool(icmp_fields(f"{PC2_MAC}（PC2）", f"{PC1_MAC}（PC1）")),
              mac_table=mac1),
        _step("process", 2, "PC2", AGING_PHASES[7],
              "PC2 收下（目的 MAC 是我），构造 ICMP 应答从 g0/2 发回。命运的"
              "齿轮开始重转：这个应答将替 SW1 把第二行表项学回来。",
              ["PC2：目的 MAC=本机 → 收下，回应答帧",
               "应答：源=PC2 / 目的=PC1 / 从 g0/2 入 SW1"],
              fields=icmp_fields(f"{PC1_MAC}（PC1 · 单播）", f"{PC2_MAC}（PC2）"),
              mac_table=mac1,
              flash={"PC2": {"ok": True, "text": "收下 · 是我的"}}),
        _step("process", 2, "SW1", AGING_PHASES[8],
              "应答帧入 g0/2：学习——"
              f"{PC2_MAC} → g0/2，表第二行回来了（重学习）。查目："
              f"{PC1_MAC} 命中 g0/1 → 已知单播。作业 2 第三问的答案：删除后"
              "再通信，重新学习，过程重现一次泛洪。",
              [f"重学习：{PC2_MAC} → g0/2（表 2 行复原）",
               "查表：命中 g0/1 → 已知单播",
               "作业 2：删除后再通信 → 重新学习 ✓"],
              fields=[
                  _field("以太网头 · 源 MAC",
                         f"{PC2_MAC} → 记为 g0/2", None, True),
                  _field("判定", "已知单播 → 精准转发 g0/1", None, True),
                  _field("FCS", "校验 ✓（帧完好）"),
              ],
              mac_table=two_new),
        _step("move", 1, "SW1", AGING_PHASES[9],
              "应答精准送达 PC1——ping 通。表满两行，精准时代回归。",
              ["精准转发：SW1 → PC1，ping 通",
               "表复原：此后又是 1 对 1 时代"],
              events=[{"from": "SW1", "to": "PC1", "kind": "frame",
                       "label": "已知单播 · 精准转发", "hue": "icmp"}],
              fields=_cool(icmp_fields(f"{PC1_MAC}（PC1）", f"{PC2_MAC}（PC2）")),
              mac_table=two),
        _step("final", 0, "SW1", AGING_PHASES[10],
              "老化的完整闭环：表项 300 秒没被使用 → 删除 → 再通信时泛洪一次 "
              "→ 重新学习。为什么不建议改老化时间？五条理由：表是转发核心、"
              "默认 300 秒是最佳折中、改短则频繁重学（性能下降）、改长则换"
              "端口后表指错（错误转发）、企业网络基本保持默认。一句话：老化"
              "不是可调的优化项，是交换机自我维护的一部分——正常情况下别动它。",
              ["闭环：300s 未用 → 删 → 泛洪一次 → 重学习",
               "不建议改老化的五条理由（核心 / 折中 / 过短频繁重学 / 过长指错 / 保持默认）",
               "与 ARP 老化互为镜像：两张表都是「缓存」"],
              mac_table=two),
    ]

    flood = [i for i, s in enumerate(steps)
             if len(s["events"]) > 1 and
             len({e["from"] for e in s["events"]}) == 1]
    learn = [i for i, s in enumerate(steps)
             if any(r.get("new") for r in s["mac_table"])]
    return SwitchResult("aging", chain, steps, flood, learn,
                        [s["pdu_name"] for s in steps])


def simulate(scenario="learn"):
    builders = {"learn": _simulate_learn, "aging": _simulate_aging}
    if scenario not in builders:
        raise ValueError(f"unknown scenario: {scenario!r} "
                         f"(choose from {', '.join(SCENARIOS)})")
    return builders[scenario]()
