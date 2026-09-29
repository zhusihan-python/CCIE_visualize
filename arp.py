"""ARP 地址解析故事生成器（CCNA 第 04 课：以太网基础 / MAC IP 与 ARP）。

纯逻辑、无 I/O——沿用系列约定：每个步骤都是完整快照（所在设备、OSI 层号、
当前帧字段、双方 ARP 表、接收判定）并附中文讲解；播放器只做哑渲染。

场景 resolve：三台 PC 接入同一段共享总线（无交换机，对应笔记「广播多点
接入 BMA / 共享同一介质」）。PC1 第一次 ping PC2：
四元素缺目的 MAC → 查 ARP 表未命中 → 广播请求（全村听到、只有 PC2 应答、
PC3 沉默丢弃）→ 单播应答 → 双方写表 → ICMP 单播往返；
第二次 ping 查表命中，全程零广播。
"""

from dataclasses import dataclass

SCENARIOS = ("resolve",)

# ---- 教学示意值（与笔记作业同网段；MAC 沿用仓库惯例格式） ----------------

PC1_IP, PC2_IP, PC3_IP = "192.168.1.1", "192.168.1.2", "192.168.1.3"
PC1_MAC, PC2_MAC, PC3_MAC = ("0200.0000.0001", "0200.0000.0002",
                             "0200.0000.0003")
BROADCAST_MAC = "FFFF.FFFF.FFFF"      # 即 FF-FF-FF-FF-FF-FF（48 bit 全 1）
UNKNOWN_MAC = "0000.0000.0000"        # 请求里「不知道才问」的目标 MAC


# ---- 设备链 ------------------------------------------------------------

@dataclass(frozen=True)
class Device:
    id: str
    kind: str                 # pc
    label: str
    layer_range: tuple        # (1, 7)
    ip: str
    mac: str


@dataclass
class Chain:
    devices: list
    links: list               # 总线拓扑：空。连接性由渲染层画成共享总线

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
            "links": [],
        }


def bus_chain():
    return Chain(
        devices=[
            Device("PC1", "pc", "发送方", (1, 7), PC1_IP, PC1_MAC),
            Device("PC2", "pc", "应答方", (1, 7), PC2_IP, PC2_MAC),
            Device("PC3", "pc", "旁观者", (1, 7), PC3_IP, PC3_MAC),
        ],
        links=[],
    )


# ---- 步骤构造 -----------------------------------------------------------

def _field(k, v, tone=None, hot=False):
    # tone: bcast 广播（红）/ uni 单播（绿）/ unk 未知（琥珀）/ None 常规
    return {"k": k, "v": v, "tone": tone, "hot": hot}


def _cool(fields):
    """传输/观察步沿用同一帧，但去掉「本步焦点」高亮。"""
    return [{**f, "hot": False} for f in fields]


def _entry(ip, mac, new=False):
    return {"ip": ip, "mac": mac, "type": "dynamic", "new": new}


def _step(kind, layer, device, phase, description, bullets, *,
          events=None, fields=None, tables=None, flash=None):
    return {
        "kind": kind,             # initial | process | move | final
        "layer": layer,           # 1..7；initial/final 为 0（不高亮）
        "device": device,
        "pdu_name": phase,        # 右上角阶段标签（同时是测试 ground truth）
        "description": description,
        "bullets": list(bullets),
        "events": events or [],   # 仅 move 步：总线飞行粒子（kind=frame）
        "fields": fields or [],   # 左下面板：当前帧字段快照
        "arp_tables": tables or {"PC1": [], "PC2": []},
        "flash": flash or {},     # 接收判定胶囊 {设备: {ok, text}}
    }


# ---- 报文字段面板快照 ---------------------------------------------------

def pending_fields(hot=True):
    """ARP 解析前「卡住的」ICMP 帧：四元素缺目的 MAC。"""
    return [
        _field("以太网头 · 目的 MAC", "？（还不知道）", "unk", hot),
        _field("以太网头 · 源 MAC", f"{PC1_MAC}（PC1）", "uni"),
        _field("IP 头 · 源 IP", PC1_IP),
        _field("IP 头 · 目的 IP", PC2_IP),
        _field("载荷", "ICMP Echo 请求"),
    ]


def request_fields(hot=True):
    return [
        _field("以太网头 · 目的 MAC", f"{BROADCAST_MAC}（广播）",
               "bcast", hot),
        _field("以太网头 · 源 MAC", f"{PC1_MAC}（PC1）", "uni"),
        _field("ARP · 操作码", "1 = ARP 请求", None, hot),
        _field("ARP · 发送方 MAC", f"{PC1_MAC}（PC1）"),
        _field("ARP · 发送方 IP", f"{PC1_IP}（PC1）", None, hot),
        _field("ARP · 目标 IP", f"{PC2_IP}（PC2）", None, hot),
        _field("ARP · 目标 MAC", f"{UNKNOWN_MAC}（未知 · 全 0）", "unk", hot),
    ]


def reply_fields(hot=True):
    return [
        _field("以太网头 · 目的 MAC", f"{PC1_MAC}（PC1 · 单播）", "uni", hot),
        _field("以太网头 · 源 MAC", f"{PC2_MAC}（PC2）", "uni"),
        _field("ARP · 操作码", "2 = ARP 应答", None, hot),
        _field("ARP · 发送方 MAC", f"{PC2_MAC}（PC2）", None, hot),
        _field("ARP · 发送方 IP", f"{PC2_IP}（PC2）", None, hot),
        _field("ARP · 目标 IP", f"{PC1_IP}（PC1）", None, hot),
        _field("ARP · 目标 MAC", f"{PC1_MAC}（PC1）", "uni", hot),
    ]


def icmp_fields(dst_mac_note, direction, payload, hot=True):
    src_ip, dst_ip = direction
    return [
        _field("以太网头 · 目的 MAC", dst_mac_note, "uni", hot),
        _field("以太网头 · 源 MAC", f"{PC1_MAC}（PC1）", "uni"),
        _field("IP 头 · 源 IP", src_ip),
        _field("IP 头 · 目的 IP", dst_ip),
        _field("载荷", payload, None, hot),
    ]


# ---- 主入口 ------------------------------------------------------------
# 阶段标签序列同时是 test_arp 的 ground truth；改动分镜须同步测试。

PHASES = (
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
)


@dataclass
class ArpResult:
    scenario: str
    chain: Chain
    steps: list
    fanout_steps: list         # 同源多目的（广播扇出）的步索引（测试/摘要用）
    table_writes: int          # 写表次数（PC2 学 PC1 + PC1 写 PC2 = 2）
    phase_names: list          # pdu_name 全序列（测试 ground truth）


def simulate(scenario="resolve"):
    if scenario != "resolve":
        raise ValueError(f"unknown scenario: {scenario!r} "
                         f"(choose from {', '.join(SCENARIOS)})")
    chain = bus_chain()
    empty_tables = {"PC1": [], "PC2": []}
    pc2_learned = {"PC1": [], "PC2": [_entry(PC1_IP, PC1_MAC, new=True)]}
    pc2_only = {"PC1": [], "PC2": [_entry(PC1_IP, PC1_MAC)]}
    both = {"PC1": [_entry(PC2_IP, PC2_MAC, new=True)],
            "PC2": [_entry(PC1_IP, PC1_MAC)]}
    both_settled = {"PC1": [_entry(PC2_IP, PC2_MAC)],
                    "PC2": [_entry(PC1_IP, PC1_MAC)]}

    steps = [
        _step("initial", 0, "PC1", PHASES[0],
              "三台 PC 接入同一段共享总线（无交换机）——这是笔记里「广播"
              "多点接入（BMA）」的最小形态：介质人人共享，一台发声、全村"
              "都能听到。PC1（192.168.1.1）接下来要第一次 ping PC2"
              "（192.168.1.2）；右下两块 ARP 缓存表现在都是空的。带着问题"
              "看：PC1 只有 PC2 的 IP，目的 MAC 从哪来？",
              ["拓扑：PC1 / PC2 / PC3 共享同一段总线（同一广播域）",
               "每台 PC：IP 按规划配置 + 出厂烧录的全球唯一 MAC",
               "看什么：广播怎么「全村扩散」、ARP 表何时写入、"
               "第二次 ping 有何不同"],
              tables=empty_tables),
        _step("process", 2, "PC1", PHASES[1],
              "在 PC1 敲下 ping 192.168.1.2。封装帧需要四个元素，此刻已经"
              "有三个：源 IP、目的 IP、源 MAC——唯独目的 MAC 不知道：IP "
              "可以按规划推算，但「192.168.1.2 对应哪块网卡」没人告诉过"
              "PC1。二层帧头写不出来，包就发不出去——这个缺口正是 ARP "
              "要补的。",
              ["命令：PC1> ping 192.168.1.2",
               "四元素已备其三：源 IP / 目的 IP / 源 MAC，缺「目的 MAC」",
               "笔记结论：ARP 是 IPv4 通信的前置条件，没有它帧封不出去"],
              fields=pending_fields(),
              tables=empty_tables),
        _step("process", 2, "PC1", PHASES[2],
              "操作系统不会上来就广播——发包前的第一步永远是先查自己的 "
              "ARP 缓存表（arp -a 看到的那张表）：如果 192.168.1.2 已有"
              "映射，直接拿来封帧，零广播。此刻 PC1 的表是空的，未命中"
              "——这才轮到 ARP 请求出场。",
              ["先查表：PC1 的 ARP 缓存 → 无 192.168.1.2 的表项",
               "命中即可免广播；未命中 → 发送 ARP 请求",
               "好习惯：广播是兜底手段，不是第一反应"],
              fields=_cool(pending_fields()),
              tables=empty_tables),
        _step("process", 2, "PC1", PHASES[3],
              "PC1 构造 ARP 请求报文，每个字段都在左下面板展开：操作码=1"
              "（请求）；发送方填自己（IP+MAC，白送对方学习）；目标 IP 填 "
              f"192.168.1.2；目标 MAC 填全 0——不知道才问嘛。最外层以太网"
              f"头的目的 MAC 填广播地址 {BROADCAST_MAC}（即 "
              "FF-FF-FF-FF-FF-FF，48 bit 全 1）：既然不知道谁持有这个 IP，"
              "就向全村喊话。",
              [f"ARP 报文：OP=1 请求；发送方=PC1（IP+MAC）；目标 IP={PC2_IP}；"
               "目标 MAC=未知（全 0）",
               f"以太网头：目的 = {BROADCAST_MAC}（广播），源 = PC1",
               "为什么广播？不知道谁持有 192.168.1.2，只能问所有人"],
              fields=request_fields(),
              tables=empty_tables),
        _step("move", 1, "PC1", PHASES[4],
              "广播帧登上总线，向左右两侧同时扩散——三台 PC 都会收到（这就"
              "是「拿着大喇叭、全村都听到」）。物理层视角：总线上跑的是比"
              "特流，所有网卡都能听到这段信号。",
              ["广播发送：同一帧同时发往 PC2 与 PC3（两侧扩散）",
               "目的 MAC 全 F = 本广播域内人人有份",
               "当前 PDU：帧（Frame）→ 总线比特流"],
              events=[
                  {"from": "PC1", "to": "PC2", "kind": "frame",
                   "label": "ARP 请求（广播）", "hue": "arp"},
                  {"from": "PC1", "to": "PC3", "kind": "frame",
                   "label": "ARP 请求（广播）", "hue": "arp"},
              ],
              fields=_cool(request_fields()),
              tables=empty_tables),
        _step("process", 2, "PC3", PHASES[5],
              "PC3 的网卡收到这帧：目的 MAC 是广播地址——收下，往上交。拆开"
              "一看，ARP 询问的目标 IP 是 192.168.1.2，不是自己"
              "（192.168.1.3）——不是问我的，就不应答，也不需要做什么。"
              "沉默，正是非目标设备对广播的正确态度。",
              ["PC3：广播帧 → 收下；目标 IP ≠ 本机 → 不应答",
               "非目标设备：安静丢弃，不产生任何流量",
               "反过来说：应答的只会是真正持有该 IP 的设备"],
              fields=_cool(request_fields()),
              tables=empty_tables,
              flash={"PC3": {"ok": False, "text": "丢弃 · 目标 IP 不是我"}}),
        _step("process", 2, "PC2", PHASES[6],
              "PC2 收到同一帧：目标 IP = 192.168.1.2 = 本机——问的就是我！"
              "PC2 立刻准备应答。还有个顺手的收获：请求报文的「发送方 "
              "IP/MAC」字段里明明白白写着 PC1 的映射，PC2 顺手把它学进自己"
              "的 ARP 表（右下角 PC2 表新增一行）——等会儿回程封帧直接就能"
              "用，不用再广播问一次。",
              ["PC2：目标 IP = 本机 → 认领并准备应答",
               f"顺手学习：从请求的「发送方」字段学到 {PC1_IP} → {PC1_MAC}"
               "（dynamic）",
               "一次广播，两边受益——「免费 ARP 更新邻居表」同款机制"],
              fields=[
                  _field("以太网头 · 目的 MAC", f"{BROADCAST_MAC}（广播）",
                         "bcast"),
                  _field("ARP · 目标 IP", f"{PC2_IP}（= 本机 → 认领）",
                         "uni", True),
                  _field("ARP · 发送方 IP", f"{PC1_IP}（PC1）", None, True),
                  _field("ARP · 发送方 MAC", f"{PC1_MAC}（PC1）→ 学走",
                         None, True),
              ],
              tables=pc2_learned,
              flash={"PC2": {"ok": True, "text": "收下 · 问的是我"}}),
        _step("process", 2, "PC2", PHASES[7],
              "PC2 构造 ARP 应答：操作码=2；发送方=自己；目标 IP/MAC 直接填 "
              "PC1——刚从请求里学来的，不用再问。注意以太网头：目的 MAC 填 "
              "PC1 的单播地址，不再广播——应答只需要给请求者一个人，没必要"
              "让全村再听一遍。",
              ["ARP 报文：OP=2 应答；发送方=PC2；目标=PC1（从请求学来）",
               "以太网头：目的 = PC1 单播（广播问、单播答）",
               "对照：请求的目的 MAC 是全 F，应答的目的 MAC 是具体某台"],
              fields=reply_fields(),
              tables=pc2_only),
        _step("move", 1, "PC2", PHASES[8],
              "应答帧以单播方式沿总线送到 PC1——只有 PC1 的网卡会对它「点"
              "头」。广播问、单播答，ARP 的不对称就在这两步之间。",
              ["单播应答：PC2 → PC1，一条航线",
               "广播（请求）vs 单播（应答）：问的人多，答的人只有一个",
               "当前 PDU：帧（Frame）→ 总线比特流"],
              events=[{"from": "PC2", "to": "PC1", "kind": "frame",
                       "label": "ARP 应答（单播）", "hue": "arp"}],
              fields=_cool(reply_fields()),
              tables=pc2_only),
        _step("process", 2, "PC1", PHASES[9],
              f"PC1 收到应答，把 {PC2_IP} → {PC2_MAC} 写入 ARP 缓存表（右下"
              "角 PC1 表新增一行，类型 dynamic）。四个元素终于凑齐——刚才 "
              "ping 还卡在「目的 MAC 未知」，现在可以继续封装了。",
              [f"写表：{PC2_IP} → {PC2_MAC}（dynamic）",
               "表项来自应答，动态学习、有老化时间",
               "四元素齐：源/目的 IP + 源/目的 MAC——封帧走起"],
              fields=[
                  _field("ARP · 发送方 IP", f"{PC2_IP}（PC2）", None, True),
                  _field("ARP · 发送方 MAC", f"{PC2_MAC}（PC2）→ 写入表",
                         None, True),
                  _field("ARP · 操作码", "2 = ARP 应答"),
              ],
              tables=both),
        _step("process", 3, "PC1", PHASES[10],
              "现在封装 ICMP Echo 请求：以太网头目的 MAC 填刚查到的 PC2"
              "（对照第 2 步的空缺——这就是 ARP 补上的那一格），IP 头 "
              "192.168.1.1 → 192.168.1.2。完整的逐层封装（数据→段→包→帧）"
              "就是上一篇「封装与解封装」的主线，这里不再重复展开。",
              [f"以太网头：目的 MAC = {PC2_MAC}（ARP 刚解析到的）",
               f"IP 头：{PC1_IP} → {PC2_IP}；载荷 = ICMP Echo 请求",
               "逐层加头的完整过程：见「封装与解封装 · 同网段场景」"],
              fields=icmp_fields(f"{PC2_MAC}（PC2 · 刚查到）",
                                 (PC1_IP, PC2_IP), "ICMP Echo 请求"),
              tables=both_settled),
        _step("move", 1, "PC1", PHASES[11],
              "ICMP 请求单播发送。共享总线的物理特性：PC3 的网卡同样「听得"
              "到」这段比特——但网卡一看目的 MAC 是 PC2 的单播地址、不是自"
              "己，直接丢弃不上交。MAC 过滤正是以太网寻址的本质：真正让帧"
              "找到目标设备的是 MAC，不是 IP。",
              ["单播发送：PC1 → PC2",
               "PC3 也听得到（共享介质），但目的 MAC ≠ 我 → 网卡丢弃",
               "以太网真正用来寻址的是 MAC 地址"],
              events=[{"from": "PC1", "to": "PC2", "kind": "frame",
                       "label": "ICMP Echo 请求", "hue": "icmp"}],
              fields=_cool(icmp_fields(f"{PC2_MAC}（PC2）",
                                       (PC1_IP, PC2_IP), "ICMP Echo 请求")),
              tables=both_settled,
              flash={"PC3": {"ok": False, "text": "丢弃 · 目的 MAC 不是我"}}),
        _step("process", 3, "PC2", PHASES[12],
              "PC2 收到：目的 MAC=我、目的 IP=我——确实是发给我的。网络层把 "
              "ICMP Echo 请求交给协议处理，生成 Echo 应答：目的 MAC 填 PC1"
              "（查自己的 ARP 表——第 7 步顺手学的这行现在派上用场），IP 头"
              "反向 192.168.1.2 → 192.168.1.1。",
              ["PC2 收下：目的 MAC=我、目的 IP=我，双重核对",
               "应答封装：目的 MAC=PC1（查 PC2 的 ARP 表命中——第 7 步学的）",
               f"IP 头反向：{PC2_IP} → {PC1_IP}"],
              fields=icmp_fields(f"{PC1_MAC}（PC1 · 查表命中）",
                                 (PC2_IP, PC1_IP), "ICMP Echo 应答"),
              tables=both_settled),
        _step("move", 1, "PC2", PHASES[13],
              "应答帧单播回程，PC2 → PC1。一次 ping 的往返即将闭环。",
              ["单播回程：PC2 → PC1",
               "载荷：ICMP Echo 应答",
               "当前 PDU：帧（Frame）→ 总线比特流"],
              events=[{"from": "PC2", "to": "PC1", "kind": "frame",
                       "label": "ICMP Echo 应答", "hue": "icmp"}],
              fields=_cool(icmp_fields(f"{PC1_MAC}（PC1）",
                                       (PC2_IP, PC1_IP), "ICMP Echo 应答")),
              tables=both_settled),
        _step("process", 3, "PC1", PHASES[14],
              "PC1 的 ping 收到应答——通了！此刻右下角 PC1 的 ARP 表恰好"
              "一行：整个通信链路（先 ARP、后 ICMP）完整跑通。",
              ["ping 通 = ICMP 请求/应答成功往返（L1–L3 全通）",
               "输出样例：84 bytes from 192.168.1.2 icmp_seq=1 "
               "ttl=64 time≈0.5ms",
               f"PC1 ARP 表此刻：{PC2_IP} → {PC2_MAC}（dynamic）"],
              fields=_cool(icmp_fields(f"{PC2_MAC}（PC2）",
                                       (PC1_IP, PC2_IP), "ICMP Echo 请求")),
              tables=both_settled),
        _step("process", 2, "PC1", PHASES[15],
              "用 arp -a 看一眼 PC1 的 ARP 缓存表——右下角那张表就是这条命令"
              "的输出：IP 地址、MAC 地址、类型 dynamic 一行齐活（对应课后"
              "作业的截图 4：必须能看到 PC2 的 MAC）。表在内存里，由系统"
              "自动维护。",
              ["命令：PC1> arp -a（Windows / Linux / VPC 同名命令）",
               "表项三要素：IP 地址 ↔ MAC 地址 ↔ 类型",
               "这张表是缓存：为「下次免广播」而生"],
              fields=_cool(reply_fields()),
              tables=both_settled),
        _step("process", 2, "PC1", PHASES[16],
              "再 ping 一次 192.168.1.2。这次发包前的查表命中——192.168.1.2 "
              "的映射就在表里，直接拿来封帧。对照第 5 步：第一次 ping 前有"
              "一场全村广播，这一次零广播——ARP 缓存的价值正在于此。",
              ["第二次 ping：查表命中 → 直接封装，不再 ARP",
               "对照第一次：广播 1 次 → 0 次",
               "真实世界：首次 ping 常见首包超时，正是因为 ARP 在抢跑"],
              fields=icmp_fields(f"{PC2_MAC}（PC2 · 表里就有）",
                                 (PC1_IP, PC2_IP), "ICMP Echo 请求"),
              tables=both_settled),
        _step("move", 1, "PC1", PHASES[17],
              "请求与应答一去一回（两个粒子先后飞行）——没有广播、没有 ARP，"
              "纯粹的点到点往返。两次 ping 看下来，ARP 的全貌就一句话：用一"
              "次广播，换之后每次通信的直接送达。",
              ["第二次 ping 往返：请求（PC1→PC2）+ 应答（PC2→PC1）",
               "全程零广播——查表命中，帧帧单播",
               "动态表项会老化（几分钟到 4 小时）：过期删除后，又要广播一次"],
              events=[
                  {"from": "PC1", "to": "PC2", "kind": "frame",
                   "label": "ICMP Echo 请求", "hue": "icmp"},
                  {"from": "PC2", "to": "PC1", "kind": "frame",
                   "label": "ICMP Echo 应答", "hue": "icmp", "delay": 1},
              ],
              fields=_cool(icmp_fields(f"{PC2_MAC}（PC2）",
                                       (PC1_IP, PC2_IP), "ICMP Echo 请求")),
              tables=both_settled),
        _step("final", 0, "PC1", PHASES[18],
              "全程回顾：① 封帧四元素缺目的 MAC → 先查 ARP 表，未命中才广"
              "播；② 请求广播（目的 MAC 全 F、全村听到、只有目标应答），应"
              "答单播；③ 双方都学到映射，写入 dynamic 表项；④ 之后通信先查"
              "表，命中免广播——直到表项老化。arp -d 清空表再 ping，会完整"
              "重演一遍（课后作业任务 4）。下一篇：免费 ARP——设备主动广播"
              "「谁和我同 IP？」，冲突检测就靠它。",
              ["ARP：已知 IP → 广播问 → 单播答 → 写表缓存",
               "表项 dynamic 会老化；arp -d 清空后重 ping = 重演全过程",
               "预告：免费 ARP（源 IP=目标 IP=自己）——IP 冲突检测，"
               "下一篇展开"],
              tables=both_settled),
    ]

    # 广播扇出 = 同一步内 >1 个事件且同源（第二次 ping 是异源往返，不算）
    fanout = [i for i, s in enumerate(steps)
              if len(s["events"]) > 1 and
              len({e["from"] for e in s["events"]}) == 1]
    return ArpResult(
        scenario=scenario,
        chain=chain,
        steps=steps,
        fanout_steps=fanout,
        table_writes=2,
        phase_names=[s["pdu_name"] for s in steps],
    )
