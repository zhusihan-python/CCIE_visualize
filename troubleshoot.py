"""分层排错故事生成器（CCNA 第 02 课：网络参考模型 · 排错方法论）。

纯逻辑、无 I/O——沿用同仓约定：每步都是完整快照（检查清单、故障可见性、
OSI 层号）并附中文讲解；播放器只做哑渲染。

故事：PC1 打不开 PC2 的网页 http://192.168.2.10。方法论：自底向上
1️⃣物理 → 2️⃣链路 → 3️⃣网络 → 4️⃣应用（医院分诊）；通过=排除该层
继续向上，失败=定位→修复→验证。三个场景=同一方法论的三种断点：
- "cable"：物理层故障（PC1–SW1 网线断），首查命中。
- "ip-config"：网络层故障（PC1 被配成 192.168.3.10 错网段），
  前两层逐一排除后定位。
- "service"：应用层故障（PC2 的 HTTP 服务未启动），ping 通
  （L1–L3 全通）后指向应用层。

layer 取值规则：symptom/final=0；check=所查层号（1/2/3/7）；
fix=故障层；verify=被复查对象的层（故障层复查=故障层，应用验证=7）。
"""

from dataclasses import dataclass

from encap import Chain, Device, Link, PC1_MAC, PC2_IP_CROSS, PC2_MAC, R1_IFACES

SCENARIOS = ("cable", "ip-config", "service")

PC1_RIGHT_IP = "192.168.1.10"
PC1_WRONG_IP = "192.168.3.10"
GATEWAY = "192.168.1.1"
WEB_URL = "http://192.168.2.10"

# 检查清单四行（播放器按 layer===7 高亮第四行）
ROWS = (
    {"layer": 1, "name": "L1 物理层", "detail": "网线 / 接口指示灯"},
    {"layer": 2, "name": "L2 数据链路层", "detail": "接口 up · MAC 地址表 · VLAN 归属"},
    {"layer": 3, "name": "L3 网络层", "detail": "ipconfig · ping 网关与对端"},
    {"layer": 7, "name": "L4·L7 传输·应用", "detail": "端口监听 · 服务状态"},
)


def _checks(verdicts):
    """按 ROWS 生成检查清单快照；未提及的层为 todo。"""
    return [dict(r, verdict=verdicts.get(r["layer"], "todo")) for r in ROWS]


def _step(kind, layer, device, checks, description, bullets, events=None,
          down_links=None, alert_devices=None):
    return {
        "kind": kind,               # symptom|check|fix|verify|final
        "layer": layer,
        "device": device,
        "checks": checks,
        "description": description,
        "bullets": list(bullets),
        "events": events or [],     # ping 飞行动画（见 README 模拟边界）
        "down_links": list(down_links or []),
        "alert_devices": list(alert_devices or []),
    }


def _cross_chain(pc1_ip=PC1_RIGHT_IP, pc1_sw1_down=False):
    """排错场景的设备链：同一批角色，故障按场景注入。"""
    return Chain(
        devices=[
            Device("PC1", "pc", "PC1（客户端）", (1, 7), pc1_ip, PC1_MAC),
            Device("SW1", "switch", "接入交换机", (1, 2)),
            Device("R1", "router", "网关路由器", (1, 3),
                   interfaces=R1_IFACES),
            Device("SW2", "switch", "对端交换机", (1, 2)),
            Device("PC2", "pc", "PC2（Web 服务器）", (1, 7),
                   PC2_IP_CROSS, PC2_MAC),
        ],
        links=[
            Link("PC1", "SW1", state="down" if pc1_sw1_down else None),
            Link("SW1", "R1"), Link("R1", "SW2"), Link("SW2", "PC2"),
        ],
    )


def _symptom(extra, bullets, down_links=None):
    return _step("symptom", 0, "PC1", _checks({}),
                 "用户报告：PC1 上打不开 " + WEB_URL + " 的网页（PC2 是 Web "
                 "服务器）。排错方法论：像医生分诊，自底向上逐层检查——"
                 "1️⃣物理（网线/接口）→ 2️⃣链路（MAC/VLAN）→ 3️⃣网络"
                 "（IP/路由）→ 4️⃣应用（服务/端口）。每层检查要么「通过」"
                 "（排除该层，继续向上），要么「失败」（定位→修复→验证）。"
                  "下方清单实时记录排查进度，右侧面板高亮当前检查的层。" + extra,
                 ["症状：PC1 打不开 " + WEB_URL,
                  "方法论：自底向上，先排除再定位（医院分诊）",
                  bullets],
                 down_links=down_links)


def _l1_pass():
    return _step("check", 1, "PC1", _checks({1: "pass"}),
                 "第一站·物理层：看 PC1 与 SW1 的网口指示灯——都亮，接口 up。"
                 "链路物理上没问题，物理层「排除」。「排除」本身就是收获："
                 "网线和接口不用再查了，继续向上。",
                 ["检查项：网口指示灯 / 接口状态",
                  "结果：✓ 灯亮——物理层排除",
                  "向上：继续查数据链路层"])


def _l2_pass():
    return _step("check", 2, "SW1", _checks({1: "pass", 2: "pass"}),
                 "第二站·数据链路层：SW1 的接口 up；查 SW1 的 MAC 地址表，"
                 "能看到 PC1 所在端口的条目——帧的收发正常（VLAN 归属也属于"
                 "二层检查项，本场景端口划分正常）。链路层「排除」。",
                 ["检查项：接口状态 / SW1 的 MAC 地址表条目",
                  "结果：✓ 帧收发正常——链路层排除",
                  "向上：继续查网络层"])


def _app_verify(prev_verdicts):
    verdicts = dict(prev_verdicts)
    verdicts[7] = "pass"
    return _step("verify", 7, "PC1", _checks(verdicts),
                 "应用层验证：PC1 重新打开 " + WEB_URL + "——网页正常返回。"
                 "症状消失，排错闭环。",
                 ["应用验证：网页正常打开 ✓",
                  "闭环：症状消失，排错结束"])


# ---- 场景一：cable（物理层，6 步） ---------------------------------------

def _cable_story():
    steps = [
        _symptom("提示：这次画布上就能看见一处异常——PC1 与 SW1 之间的链路。",
                 "观察：画布上 PC1–SW1 链路有红 ✕",
                 down_links=["PC1-SW1"]),
        _step("check", 1, "PC1", _checks({1: "fail"}),
              "第一站·物理层：看 PC1 的网口指示灯——不亮；换一根确认好的"
              "网线仍然不亮，SW1 侧接口也一样。比特流根本发不出去：故障"
              "定位在物理层（链路中断）。对照画布：红 ✕ 正是这条链路。",
              ["检查项：网口指示灯 / 更换网线",
               "结果：✗ 灯不亮——PC1–SW1 链路中断",
               "定位：物理层故障——一次检查即命中"],
              down_links=["PC1-SW1"]),
        _step("fix", 1, "PC1", _checks({1: "fail"}),
              "修复动作：更换 PC1 到 SW1 的网线，两端重新协商成功（画布上"
              "红 ✕ 消失）。原则：修复永远修在故障层，验证从故障层开始"
              "向上——先复查物理层，再确认应用恢复。",
              ["修复：更换 PC1–SW1 网线",
               "原则：修在故障层，验从故障层起",
               "链路已恢复 up（红 ✕ 消失）"]),
        _step("verify", 1, "PC1", _checks({1: "pass"}),
              "复查物理层：PC1 网口灯亮起、接口 up——物理层恢复 ✓。"
              "继续向上做最终验证：应用是否真的回来了。",
              ["复查 L1：网口灯亮、接口 up ✓",
               "向上：确认应用恢复"]),
        _app_verify({1: "pass"}),
        _step("final", 0, "PC1", _checks({1: "pass", 7: "pass"}),
              "总结：故障在物理层（网线损坏）。自底向上的价值：低层故障在"
              "第一站就被拦下——先查网线，避免一上来就怀疑应用或路由白白"
              "绕路。对照另外两个场景：故障位置越高，需要排除的层数越多，"
              "但方法不变——通过=排除，失败=定位。本场景连 ping 都还没轮"
              "到：物理层就命中了。点击「📖 原理」看分层排错要点。",
              ["故障层：L1 物理（网线损坏）",
               "检查次数：1 次命中——自底向上对低层故障最快",
               "方法论：通过=排除，失败=定位→修复→验证"]),
    ]
    return _cross_chain(pc1_sw1_down=True), steps, 1, 1


# ---- 场景二：ip-config（网络层，8 步） -----------------------------------

def _ip_config_story():
    steps = [
        _symptom("这次画布上看不出任何异常——配置类故障是「隐形」的，"
                 "必须逐层确认。",
                 "观察：画布无异常——隐形故障靠逐层排查"),
        _l1_pass(),
        _l2_pass(),
        _step("check", 3, "PC1", _checks({1: "pass", 2: "pass", 3: "fail"}),
              "第三站·网络层：先 ipconfig 看 PC1 本机配置——IP 竟是 "
              f"{PC1_WRONG_IP}！正确应为 {PC1_RIGHT_IP}（网关 {GATEWAY}）："
              "配错网段，ARP 与 ping 网关都出不去。故障定位：网络层"
              "（地址配置错误）。画布上 ping 在半路跌落（教学示意：真实"
              "环境中表现为 ARP 解析失败或请求超时）。",
              ["检查项：ipconfig / ping 网关 " + GATEWAY,
               f"结果：✗ 本机 IP 是 {PC1_WRONG_IP}（应为 {PC1_RIGHT_IP}）",
               "定位：网络层配置错误——前两层的排除没有白做"],
              events=[{"from": "PC1", "to": "R1", "kind": "ping",
                       "drop": 0.55, "label": "ping"}],
              alert_devices=["PC1"]),
        _step("fix", 3, "PC1", _checks({1: "pass", 2: "pass", 3: "fail"}),
              "修复动作：把 PC1 的 IP 改回 " + PC1_RIGHT_IP + "/24、网关 "
              + GATEWAY + "。修复在故障层完成，从故障层开始验证。",
              [f"修复：IP 已改回 {PC1_RIGHT_IP}（网关 {GATEWAY}）",
               "原则：修在故障层，验从故障层起",
               "注：设备框显示的是故障时的配置快照"],
              alert_devices=["PC1"]),
        _step("verify", 3, "PC1", _checks({1: "pass", 2: "pass", 3: "pass"}),
              "复查网络层：ipconfig 确认配置已正确；ping " + GATEWAY +
              "——请求与应答往返成功（画布上 ping 飞了个来回），再 ping "
              "192.168.2.10 也通。网络层恢复 ✓。",
              ["复查 L3：配置正确，ping 网关往返成功 ✓",
               "ping 通意味着 L1–L3 路径全通",
               "向上：确认应用恢复"],
              events=[{"from": "PC1", "to": "R1", "kind": "ping",
                       "label": "ping"},
                      {"from": "R1", "to": "PC1", "kind": "ping",
                       "delay": 1.0, "label": "应答"}]),
        _app_verify({1: "pass", 2: "pass", 3: "pass"}),
        _step("final", 0, "PC1",
              _checks({1: "pass", 2: "pass", 3: "pass", 7: "pass"}),
              "总结：故障在网络层——PC1 的 IP 配错网段。方法论复盘：物理"
              "层、链路层逐一「通过」被排除，第三站才命中——排除法是分层"
              "排错的日常：每一层的通过都在收窄范围，让你有资格怀疑下一"
              "层。ping 的分层含义：ping 通=L1–L3 全通；ping 不通=故障在"
              " L1–L3 之内（或对端不响应）。点击「📖 原理」看要点。",
              [f"故障层：L3 网络（IP 配错网段 {PC1_WRONG_IP}）",
               "检查次数：3 次定位——排除法逐层收窄",
               "方法论：通过=排除，失败=定位→修复→验证"]),
    ]
    return _cross_chain(pc1_ip=PC1_WRONG_IP), steps, 3, 3


# ---- 场景三：service（应用层，9 步） --------------------------------------

def _service_story():
    steps = [
        _symptom("画布上同样看不出异常——这次要一路查到顶层。",
                 "悬念：底层全通的话，问题在哪儿？"),
        _l1_pass(),
        _l2_pass(),
        _step("check", 3, "PC1", _checks({1: "pass", 2: "pass", 3: "pass"}),
              "第三站·网络层：ipconfig 看 PC1 配置正常（" + PC1_RIGHT_IP +
              "/24，网关 " + GATEWAY + "）；ping 192.168.2.10——请求与"
              "应答往返成功。这是重要信息：ICMP 能走一个来回，说明 L1–L3 "
              "的整条路径都在工作。网络层「排除」——故障只能藏在更上层"
              "的服务里。",
              ["检查项：ipconfig / ping 192.168.2.10",
               "结果：✓ ping 往返成功——L1–L3 全通",
               "收窄：只剩传输·应用层，目标指向服务本身"],
              events=[{"from": "PC1", "to": "PC2", "kind": "ping",
                       "label": "ping"},
                      {"from": "PC2", "to": "PC1", "kind": "ping",
                       "delay": 1.0, "label": "应答"}]),
        _step("check", 7, "PC2",
              _checks({1: "pass", 2: "pass", 3: "pass", 7: "fail"}),
              "第四站·传输·应用层：ping 通但网页打不开，矛头指向服务本身。"
              "检查 PC2：telnet 192.168.2.10 80——连接被拒；查服务状态"
              "——HTTP 服务根本没有运行，80 端口无人监听。故障定位：应用层"
              "（服务未启动）。「端口无监听」是它在传输层的表象。",
              ["检查项：telnet 192.168.2.10 80 / 服务状态",
               "结果：✗ 连接被拒——80 端口无人监听",
               "定位：应用层故障（HTTP 服务未启动）"],
              alert_devices=["PC2"]),
        _step("fix", 7, "PC2",
              _checks({1: "pass", 2: "pass", 3: "pass", 7: "fail"}),
              "修复动作：在 PC2 上启动 HTTP 服务，确认 80 端口进入监听"
              "状态。修复在故障层完成。",
              ["修复：启动 HTTP 服务（80 端口监听）",
               "原则：修在故障层，验从故障层起"],
              alert_devices=["PC2"]),
        _step("verify", 7, "PC2",
              _checks({1: "pass", 2: "pass", 3: "pass", 7: "pass"}),
              "复查传输·应用层：telnet 192.168.2.10 80——端口能连上了，"
              "服务在监听 ✓。最后做应用级终验。",
              ["复查：80 端口可连接 ✓",
               "终验：确认应用真正恢复"]),
        _app_verify({1: "pass", 2: "pass", 3: "pass", 7: "pass"}),
        _step("final", 0, "PC1",
              _checks({1: "pass", 2: "pass", 3: "pass", 7: "pass"}),
              "总结：故障在应用层——HTTP 服务未启动。本场景最值钱的一步"
              "是 ping 通：它一次性排除了 L1–L3 三层，把范围收窄到服务"
              "本身。记住两句话：ping 通≠应用正常（路通不等于服务活）；"
              "越往高层查，越要理解「这一层通过到底证明了什么」。点击"
              "「📖 原理」看分层排错要点。",
              ["故障层：L4·L7 应用（服务未启动）",
               "关键一步：ping 通一次性排除 L1–L3",
               "结论：ping 通 ≠ 应用好"]),
    ]
    return _cross_chain(), steps, 7, 4


_STORIES = {"cable": _cable_story, "ip-config": _ip_config_story,
            "service": _service_story}


@dataclass
class TroubleshootResult:
    scenario: str
    chain: Chain
    steps: list
    fault_layer: int          # 1 / 3 / 7
    checks_until_hit: int     # 命中前的检查次数（1 / 3 / 4）


def simulate(scenario="cable"):
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario!r} "
                         f"(choose from {', '.join(SCENARIOS)})")
    chain, steps, fault_layer, checks_until_hit = _STORIES[scenario]()
    return TroubleshootResult(scenario, chain, steps, fault_layer,
                              checks_until_hit)
