"""ARP 地址解析故事生成器（CCNA 第 04 课：以太网基础 / MAC IP 与 ARP）。

纯逻辑、无 I/O——沿用系列约定：每个步骤都是完整快照（所在设备、OSI 层号、
当前帧字段、双方 ARP 表、接收判定）并附中文讲解；播放器只做哑渲染。

场景 resolve：三台 PC 接入同一段共享总线（无交换机，对应笔记「广播多点
接入 BMA / 共享同一介质」）。PC1 第一次 ping PC2：
四元素缺目的 MAC → 查 ARP 表未命中 → 广播请求（全村听到、只有 PC2 应答、
PC3 沉默丢弃）→ 单播应答 → 双方写表 → ICMP 单播往返；
第二次 ping 查表命中，全程零广播。

场景 conflict：承接 resolve 结尾的表状态。PC3 误配与 PC2 相同的 IP →
接口 up 自动广播免费 ARP（源 IP=目标 IP=自己）→ PC1 表被合并规则悄悄
污染 → PC2 单播冲突应答、PC3 告警 → 修复①PC3 改回正确 IP + 修复②PC2
防守广播重申映射、纠正邻居表。免费 ARP 两个作用（检测冲突 / 更新邻居
表）一网打尽。学习行为按 RFC 826 经典算法。
"""

from dataclasses import dataclass

SCENARIOS = ("resolve", "conflict")

# ---- 教学示意值（与笔记作业同网段；MAC 沿用仓库惯例格式） ----------------

PC1_IP, PC2_IP, PC3_IP = "192.168.1.1", "192.168.1.2", "192.168.1.3"
PC1_MAC, PC2_MAC, PC3_MAC = ("0200.0000.0001", "0200.0000.0002",
                             "0200.0000.0003")
BROADCAST_MAC = "ffff.ffff.ffff"      # 即 FF-FF-FF-FF-FF-FF（48 bit 全 1）
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
          events=None, fields=None, tables=None, flash=None,
          alert=None, dev_ip=None):
    step = {
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
    # 仅 conflict 使用：⚠ 告警徽章（resolve 契约不用 alert_devices）与
    # 设备框 IP 的每步覆盖（误配期间 PC3 显示 192.168.1.2）
    if alert:
        step["alert_devices"] = list(alert)
    if dev_ip:
        step["dev_ip"] = dict(dev_ip)
    return step


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


def _simulate_resolve():
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
              "广播帧登上总线，两个复制帧同时起飞、一近一远奔向 PC2 与 "
              "PC3——三台 PC 都会收到（这就是「拿着大喇叭、全村都听到」）。"
              "物理层视角：总线上跑的是比特流，所有网卡都能听到这段信号。",
              ["广播发送：同一帧同时发往 PC2 与 PC3（同时起飞、一近一远）",
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
        scenario="resolve",
        chain=chain,
        steps=steps,
        fanout_steps=fanout,
        table_writes=2,
        phase_names=[s["pdu_name"] for s in steps],
    )


# ---- 场景 conflict：免费 ARP 与 IP 冲突 ---------------------------------

# 阶段标签序列同时是 test_arp 的 ground truth；改动分镜须同步测试。
CONFLICT_PHASES = (
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
)


def _gratuitous_fields(hot=True):
    """PC3 的免费 ARP 请求：源 IP = 目标 IP = 自己（误配的 192.168.1.2）。"""
    return [
        _field("以太网头 · 目的 MAC", f"{BROADCAST_MAC}（广播）", "bcast", hot),
        _field("以太网头 · 源 MAC", f"{PC3_MAC}（PC3）", "uni"),
        _field("ARP · 操作码", "1 = ARP 请求", None, hot),
        _field("ARP · 发送方 IP", f"{PC2_IP}（自己 · 误配的新 IP）", None, hot),
        _field("ARP · 发送方 MAC", f"{PC3_MAC}（PC3）"),
        _field("ARP · 目标 IP", f"{PC2_IP}（也是自己！）", None, hot),
        _field("ARP · 目标 MAC", f"{UNKNOWN_MAC}（未知 · 全 0）", "unk", hot),
    ]


def _conflict_reply_fields(hot=True):
    """PC2 的冲突应答（单播）：持有人声明「这个 IP 我在用」。"""
    return [
        _field("以太网头 · 目的 MAC", f"{PC3_MAC}（PC3 · 单播）", "uni", hot),
        _field("以太网头 · 源 MAC", f"{PC2_MAC}（PC2）", "uni"),
        _field("ARP · 操作码", "2 = ARP 应答", None, hot),
        _field("ARP · 发送方 IP", f"{PC2_IP}（PC2 · 真正持有人）", None, hot),
        _field("ARP · 发送方 MAC", f"{PC2_MAC}（PC2）", None, hot),
        _field("ARP · 目标 IP", f"{PC2_IP}（PC3 抢配的）"),
        _field("ARP · 目标 MAC", f"{PC3_MAC}（PC3）"),
    ]


def _defensive_fields(hot=True):
    """PC2 的防守性免费 ARP：重申正确映射（源 IP = 目标 IP = 自己）。"""
    return [
        _field("以太网头 · 目的 MAC", f"{BROADCAST_MAC}（广播）", "bcast", hot),
        _field("以太网头 · 源 MAC", f"{PC2_MAC}（PC2）", "uni"),
        _field("ARP · 操作码", "1 = ARP 请求", None, hot),
        _field("ARP · 发送方 IP", f"{PC2_IP}（PC2 · 重申持有人）", None, hot),
        _field("ARP · 发送方 MAC", f"{PC2_MAC}（PC2）", None, hot),
        _field("ARP · 目标 IP", f"{PC2_IP}（自己）", None, hot),
        _field("ARP · 目标 MAC", f"{UNKNOWN_MAC}（未知 · 全 0）", "unk", hot),
    ]


def _simulate_conflict():
    chain = bus_chain()
    pc2_only = {"PC1": [_entry(PC2_IP, PC2_MAC)],
                "PC2": [_entry(PC1_IP, PC1_MAC)]}
    pc1_poisoned_new = {"PC1": [_entry(PC2_IP, PC3_MAC, new=True)],
                        "PC2": [_entry(PC1_IP, PC1_MAC)]}
    pc1_poisoned = {"PC1": [_entry(PC2_IP, PC3_MAC)],
                    "PC2": [_entry(PC1_IP, PC1_MAC)]}
    pc1_fixed_new = {"PC1": [_entry(PC2_IP, PC2_MAC, new=True)],
                     "PC2": [_entry(PC1_IP, PC1_MAC)]}
    pc1_fixed = {"PC1": [_entry(PC2_IP, PC2_MAC)],
                 "PC2": [_entry(PC1_IP, PC1_MAC)]}
    misconf = {"PC3": PC2_IP}          # 误配期间设备框 IP 覆盖

    steps = [
        _step("initial", 0, "PC3", CONFLICT_PHASES[0],
              "承接上一篇结尾：PC1 和 PC2 刚通信完——PC1 的 ARP 表里有 "
              f"{PC2_IP} → PC2，PC2 的表里有 {PC1_IP} → PC1；PC3 的表还是"
              "空的。这一篇的主角是 PC3：它将被误配成与 PC2 相同的 IP，一场 "
              "IP 冲突全程上演。免费 ARP 的两个作用——检测冲突、更新邻居"
              "表——都会演到。",
              [f"承接上篇：PC1 表 {PC2_IP}→PC2 / PC2 表 {PC1_IP}→PC1",
               f"PC3 即将误配 {PC2_IP}（与 PC2 重复）",
               "看什么：免费 ARP 怎么暴露冲突、邻居表被谁污染又怎么纠正"],
              tables=pc2_only),
        _step("process", 3, "PC3", CONFLICT_PHASES[1],
              "管理员在 PC3 上配 IP，手一滑把 192.168.1.3 敲成了 "
              f"{PC2_IP}——和 PC2 一模一样。注意设备框下方的 IP 显示已经"
              "变成误配值。IP 地址不像 MAC 出厂烧录，它可以随手改——这正是"
              "冲突的根源：没有任何机制阻止两台设备配同一个 IP。",
              [f"PC3 被误配为 {PC2_IP}（与 PC2 冲突）",
               "IP 可随意配置（对比 MAC 出厂烧录、全球唯一）",
               "系统不会立刻报错——冲突要靠免费 ARP 才能暴露"],
              fields=[
                  _field("PC3 · 接口 IP", f"{PC2_IP}（误配）", None, True),
                  _field("ARP · 发送方 IP（下一帧）", f"{PC2_IP}（自己）",
                         None, True),
                  _field("ARP · 发送方 MAC（下一帧）", f"{PC3_MAC}（PC3）"),
              ],
              tables=pc2_only, dev_ip=misconf),
        _step("process", 2, "PC3", CONFLICT_PHASES[2],
              "接口配置生效（up）时，系统的标准动作是发一帧免费 ARP 探测"
              "冲突。看左下面板的字段——这就是免费 ARP 的身份证：操作码仍是"
              "「请求」；发送方 IP 填自己新配的地址；最妙的是目标 IP 也填同"
              "一个——问的正是「除了我，还有谁在用这个 IP？」；目标 MAC 全 "
              "0（不知道才问）。外层以太网头目的 = 广播，全村都要听。",
              [f"免费 ARP = 请求（OP=1）+ 源 IP = 目标 IP = {PC2_IP}（自己）",
               f"「我是 {PC2_IP}，谁也是 {PC2_IP}？」",
               f"以太网目的 = 广播 {BROADCAST_MAC}——人人都得听"],
              fields=_gratuitous_fields(),
              tables=pc2_only, dev_ip=misconf),
        _step("move", 1, "PC3", CONFLICT_PHASES[3],
              "免费 ARP 以广播登上总线，两份复制帧同时起飞、一近一远奔向 "
              "PC1 与 PC2。对 PC2 来说，这帧是冲着它的 IP 来的；对 PC1 来"
              "说，只是又一帧「与我无关」的广播——但别走开，下一步有它的"
              "戏。",
              ["广播扇出：PC3 → PC1 与 PC3 → PC2 同时起飞",
               "无人应答 = 没人用这个 IP；有人应答 = 冲突",
               "PC1/PC2 都会按 RFC 826 顺手处理发送方字段"],
              events=[
                  {"from": "PC3", "to": "PC1", "kind": "frame",
                   "label": "免费 ARP 请求（广播）", "hue": "arp"},
                  {"from": "PC3", "to": "PC2", "kind": "frame",
                   "label": "免费 ARP 请求（广播）", "hue": "arp"},
              ],
              fields=_cool(_gratuitous_fields()),
              tables=pc2_only, dev_ip=misconf),
        _step("process", 2, "PC1", CONFLICT_PHASES[4],
              "PC1 收到广播：目标 IP 不是我——不应答。但按 RFC 826 的合并"
              "规则，请求「发送方 IP/MAC」是要顺手记的：PC1 表里已有 "
              f"{PC2_IP} 的条目（上一篇 ping 学的，指向 PC2）——于是被改写"
              "成 PC3 的 MAC！IP 冲突最阴险的伤害在这一步悄悄完成：PC1 之"
              f"后再发 {PC2_IP}，帧会飞向 PC3。",
              ["PC1：非目标 → 不应答；发送方字段 → 合并进表",
               f"表项 {PC2_IP}：PC2 的 MAC 被改写为 PC3 的 MAC",
               "暗伤形成：发往 .2 的流量将跑偏（稍后第 10 步显形）"],
              fields=[
                  _field("ARP · 发送方 IP", f"{PC2_IP}（PC3 声称）", None, True),
                  _field("ARP · 发送方 MAC", f"{PC3_MAC}（PC3）→ 改写表",
                         None, True),
                  _field("以太网头 · 目的 MAC", f"{BROADCAST_MAC}（广播）",
                         "bcast"),
              ],
              tables=pc1_poisoned_new, dev_ip=misconf,
              flash={"PC1": {"ok": True, "text": "收下 · 顺手改写表"}}),
        _step("process", 2, "PC2", CONFLICT_PHASES[5],
              "PC2 收到同一帧，逐字段一看：发送方 IP = "
              f"{PC2_IP}——这是我自己的 IP！有人配了和我一样的地址还在全村"
              "广播。PC2 不需要等谁通知，冲突实锤了；它立刻准备一帧应答，"
              "把真正的持有人信息回给 PC3。",
              [f"PC2：发送方 IP = 我持有的 {PC2_IP} → 发现冲突",
               "免费 ARP 冲突检测：冲突方（而非被抢方）先发声",
               "PC2 将以单播应答回敬——只回给 PC3"],
              fields=[
                  _field("ARP · 发送方 IP", f"{PC2_IP}（= 我持有的 IP！）",
                         None, True),
                  _field("ARP · 发送方 MAC", f"{PC3_MAC}（PC3）", None, True),
                  _field("ARP · 目标 IP", f"{PC2_IP}（也是自己）", None, True),
              ],
              tables=pc1_poisoned, dev_ip=misconf,
              flash={"PC2": {"ok": True, "text": "收下 · 在抢我的 IP"}}),
        _step("process", 2, "PC2", CONFLICT_PHASES[6],
              "PC2 构造冲突应答：操作码=2（应答）；发送方填自己——"
              f"{PC2_IP} → PC2 的 MAC，这就是「这个 IP 我在用」的正式声明；"
              "目标 IP/MAC 直接抄请求里的发送方（PC3 的 MAC 是从那帧里学来"
              "的）。以太网头目的 = PC3 单播：应答只需要回给冲突方，不必再"
              "吵全村。",
              [f"OP=2 应答：发送方 = {PC2_IP} / {PC2_MAC}（持有人声明）",
               "目标 = PC3（IP/MAC 均从请求的发送方字段学来）",
               "单播回敬——「你不需要用这个 IP」"],
              fields=_conflict_reply_fields(),
              tables=pc1_poisoned, dev_ip=misconf),
        _step("move", 1, "PC2", CONFLICT_PHASES[7],
              "冲突应答以单播送达 PC3——与第 4 步的广播形成对照：探测用广播"
              "喊话，应答用单播点名。",
              ["单播应答：PC2 → PC3",
               "对照：免费 ARP 广播问，冲突应答单播答",
               "当前 PDU：帧（Frame）→ 总线比特流"],
              events=[{"from": "PC2", "to": "PC3", "kind": "frame",
                       "label": "冲突应答（单播）", "hue": "arp"}],
              fields=_cool(_conflict_reply_fields()),
              tables=pc1_poisoned, dev_ip=misconf),
        _step("process", 2, "PC3", CONFLICT_PHASES[8],
              f"PC3 收到应答——「有人已经在用 {PC2_IP} 了」。系统弹出 IP "
              "冲突告警（设备上方 ⚠ 亮起并持续）。至此免费 ARP 的第一个作用"
              "完成闭环：广播探测 → 有人应答 → 冲突实锤。真实世界里 PC2 "
              "一侧往往也会弹冲突提示——两头都知道出事了。",
              ["PC3 收到应答 → IP 冲突告警（⚠ 持续显示）",
               "作用①闭环：探测（广播）→ 应答（单播）→ 告警",
               "真实系统：冲突双方通常都会收到提示"],
              fields=_cool(_conflict_reply_fields()),
              tables=pc1_poisoned, dev_ip=misconf,
              alert=["PC3"],
              flash={"PC3": {"ok": False, "text": "⚠ IP 冲突！"}}),
        _step("process", 2, "PC1", CONFLICT_PHASES[9],
              "冲突不只是弹个告警。回看 PC1 的 ARP 表（右下）："
              f"{PC2_IP} 仍指向 PC3 的 MAC——第 5 步被改写后一直没纠正。如果"
              f"此刻 PC1 ping {PC2_IP}，封装时会查表命中 PC3 的 MAC，帧直接"
              "飞向 PC3——数据就跑偏了。表项存在就不会重新 ARP，污染会一直"
              "持续到老化或被主动更正。",
              [f"PC1 表仍指向 PC3：发往 {PC2_IP} 的帧将跑偏",
               "表项未 miss 就不会重新 ARP——污染持续",
               "IP 冲突的暗伤：不只是报错，流量会错向"],
              fields=[
                  _field("以太网头 · 目的 MAC",
                         f"{PC3_MAC}（查表所得 · 指向 PC3！）", "uni", True),
                  _field("以太网头 · 源 MAC", f"{PC1_MAC}（PC1）", "uni"),
                  _field("IP 头 · 目的 IP", PC2_IP),
                  _field("载荷", "ICMP Echo 请求（发出即跑偏）", None, True),
              ],
              tables=pc1_poisoned, dev_ip=misconf,
              alert=["PC3"],
              flash={"PC1": {"ok": False, "text": "发往 .2 将跑偏 PC3"}}),
        _step("process", 3, "PC3", CONFLICT_PHASES[10],
              "修复分两步。第一步改源头：管理员把 PC3 的 IP 改回规划值 "
              f"{PC3_IP}——设备框下方的显示恢复，⚠ 告警摘除。但注意：PC1 "
              "表里的污染还残留着，误配的后果不会随配置改对而自动消失。",
              [f"修复①：PC3 改回 {PC3_IP}，告警摘除",
               "但 PC1 的表仍指向 PC3——污染残留",
               "需要有人把正确映射重新广播出去"],
              fields=[
                  _field("PC3 · 接口 IP", f"{PC3_IP}（改回规划值）", None,
                         True),
                  _field("ARP · 发送方 IP（下一帧）", f"{PC3_IP}（自己）",
                         None, True),
                  _field("ARP · 发送方 MAC（下一帧）", f"{PC3_MAC}（PC3）"),
              ],
              tables=pc1_poisoned),
        _step("process", 2, "PC2", CONFLICT_PHASES[11],
              "第二步由真正的持有人出手：PC2 发一帧防守性免费 ARP——报文与"
              " PC3 当初那帧长得几乎一样（源 IP = 目标 IP = "
              f"{PC2_IP}、广播、请求），唯一区别是发送方 MAC 换成 PC2 的。"
              "这就是免费 ARP 的第二个作用：主动把自己的 IP→MAC 声明出去，"
              "刷新所有邻居的缓存。网卡更换、VRRP 主备切换（IP 漂移）后都靠"
              "它通知全网。",
              [f"修复②：PC2 广播重申 {PC2_IP} → {PC2_MAC}",
               "免费 ARP 作用②：更新邻居 ARP 表（换网卡/IP 漂移同理）",
               "表项存在不会重新 ARP——必须有人主动更正"],
              fields=_defensive_fields(),
              tables=pc1_poisoned),
        _step("move", 1, "PC2", CONFLICT_PHASES[12],
              "防守广播登上总线，第二次扇出：PC1 与 PC3 又一次同时收到"
              f"「{PC2_IP} 的声明」——但这一次，声明人是真正的持有人 PC2。",
              ["第二次广播扇出：PC2 → PC1 与 PC2 → PC3",
               "同样的广播格式，发送方换成了正确的人",
               "邻居们的表即将被这帧纠正"],
              events=[
                  {"from": "PC2", "to": "PC1", "kind": "frame",
                   "label": "免费 ARP（防守广播）", "hue": "arp"},
                  {"from": "PC2", "to": "PC3", "kind": "frame",
                   "label": "免费 ARP（防守广播）", "hue": "arp"},
              ],
              fields=_cool(_defensive_fields()),
              tables=pc1_poisoned),
        _step("process", 2, "PC1", CONFLICT_PHASES[13],
              "PC1 收到广播，合并发送方字段：表里的 "
              f"{PC2_IP} 从 PC3 的 MAC 纠正回 PC2 的 MAC（右下角行高亮）。"
              "暗伤愈合——之后发往 .2 的帧将回到正轨。「免费 ARP 更新邻居 "
              "ARP 表」这句话，此刻有了画面。",
              [f"PC1 合并：{PC2_IP} → {PC2_MAC}（纠正完成）",
               "暗伤愈合：流量回正轨",
               "免费 ARP 作用②在此闭环"],
              fields=[
                  _field("ARP · 发送方 IP", f"{PC2_IP}（PC2）", None, True),
                  _field("ARP · 发送方 MAC", f"{PC2_MAC}（PC2）→ 纠正表",
                         None, True),
                  _field("以太网头 · 目的 MAC", f"{BROADCAST_MAC}（广播）",
                         "bcast"),
              ],
              tables=pc1_fixed_new,
              flash={"PC1": {"ok": True, "text": "表已纠正"}}),
        _step("process", 2, "PC3", CONFLICT_PHASES[14],
              "PC3 也收到了这帧广播：目标 IP 不是我（我已经改回 "
              f"{PC3_IP} 了）——不应答；自己表里也没有 .2 的旧条目，按 "
              "RFC 826 经典算法无条目不新增。沉默，和上一篇 PC3 的表现一模"
              "一样：非目标设备的本分。",
              ["PC3：非目标 → 不应答；无旧条目 → 不新增",
               "与场景 A 的 PC3 行为完全一致（RFC 826 经典算法）",
               "沉默即正常——若有人应答才说明又有冲突"],
              fields=[
                  _field("ARP · 目标 IP", f"{PC2_IP}（≠ 本机 {PC3_IP}）",
                         None, True),
                  _field("ARP · 发送方 IP", f"{PC2_IP}（PC2）"),
                  _field("ARP · 发送方 MAC", f"{PC2_MAC}（PC2）"),
              ],
              tables=pc1_fixed,
              flash={"PC3": {"ok": False, "text": "丢弃 · 目标 IP 不是我"}}),
        _step("final", 0, "PC3", CONFLICT_PHASES[15],
              "全程回顾：免费 ARP = 源 IP 与目标 IP 都填自己的广播请求。"
              "① 冲突检测：配上 IP 就广播自问，无人应答 = 地址可用，有人"
              "应答 = 冲突告警；② 更新邻居表：真正的持有人广播重申映射，把"
              "被污染的邻居表纠正回来。两句话带走：IP 冲突的伤害不止告警"
              "——邻居 ARP 表会被悄悄污染、流量跑偏；修复 = 改对配置 + "
              "防守广播。",
              ["免费 ARP：源 IP = 目标 IP = 自己（广播请求）",
               "无人应答 = 没冲突；有人应答 = 冲突",
               "修复套路：源头改对 + 持有人防守广播刷新邻居表"],
              tables=pc1_fixed),
    ]

    fanout = [i for i, s in enumerate(steps)
              if len(s["events"]) > 1 and
              len({e["from"] for e in s["events"]}) == 1]
    return ArpResult(
        scenario="conflict",
        chain=chain,
        steps=steps,
        fanout_steps=fanout,
        table_writes=2,             # PC1 表两次改写（污染 + 纠正）
        phase_names=[s["pdu_name"] for s in steps],
    )


def simulate(scenario="resolve"):
    builders = {"resolve": _simulate_resolve, "conflict": _simulate_conflict}
    if scenario not in builders:
        raise ValueError(f"unknown scenario: {scenario!r} "
                         f"(choose from {', '.join(SCENARIOS)})")
    return builders[scenario]()
