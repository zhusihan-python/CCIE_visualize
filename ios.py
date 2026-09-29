"""Cisco IOS 基础操作故事生成器（CCNA 第 03 课）。

纯逻辑、无 I/O——沿用同仓约定：每步都是完整快照（累计终端行、IOS 模式、
场景面板状态）并附中文讲解；播放器只做哑渲染，终端为只读累计回放。

三场景（同一台教学设备的连续剧）：
- "modes"：三种模式漫游 + 帮助/缩写/Tab 补全/^ 错误定位 + no 原则。
- "save"：running(RAM) vs startup(NVRAM)——不保存 reload 丢配置、write
  拷贝、write erase 恢复出厂（结尾再现 setup 对话框与 modes 开头呼应）。
- "passwords"：Console 密码（login 必加的坑）+ enable password/secret
  （并存时 secret 胜出的实证）。

prompt↔mode 不变量：输入行 prompt 以 > 或 # 结尾 ⟺ 模式提示行，其
后缀必须匹配上一步的 mode；以 : 或 ] 结尾（Password: / [yes/no]: /
[confirm]）及其它形态一律跳过。因此约定：**跨模式的连续输入拆成多步**，
一步内的所有模式形输入共享上一步的模式。
"""

from dataclasses import dataclass

from encap import Chain

SCENARIOS = ("modes", "save", "passwords")

SETUP_QUESTION = ("Would you like to enter the initial configuration "
                  "dialog? [yes/no]:")
CONF_BANNER = "Enter configuration commands, one per line.  End with CNTL/Z."


def _in(prompt, text, silent=False):
    line = {"k": "in", "prompt": prompt, "text": text}
    if silent:
        line["silent"] = True
    return line


def _out(text=""):
    return {"k": "out", "text": text}


def _step(kind, mode, term, description, bullets, files=None, pw=None):
    step = {"kind": kind, "mode": mode, "term": list(term),
            "description": description, "bullets": list(bullets)}
    if files is not None:
        step["files"] = {"ram": list(files["ram"]),
                         "nvram": list(files["nvram"])}
    if pw is not None:
        step["pw"] = dict(pw)
    return step


def _empty_chain():
    return Chain(devices=[], links=[])


# ---- 场景一：modes（模式漫游，18 步） ------------------------------------

def _modes_story():
    term = [
        _out("--- System Configuration Dialog ---"),
        _out(SETUP_QUESTION),
    ]
    steps = [
        _step("initial", "setup", term,
              "一台空配（完全没有配置）的 Cisco 设备首次开机。系统认为你是"
              "第一次使用，于是弹出 System Configuration Dialog——「新手"
              "向导」：要不要帮你自动填一份最基本的配置（主机名、接口 IP、"
              "密码……）？向导适合快速上手，但一般选 no，由管理员自行配置。"
              "右上模式图当前显示「开机向导」——回答完这个问题才进入第一种"
              " IOS 模式。",
              ["空配开机：系统弹出初始配置向导", "向导会引导填主机名/接口 IP/密码等",
               "一般选 no，保持空配由管理员手工配置"]),
    ]

    term = term + [
        _in(SETUP_QUESTION, "no"),
        _out(),
        _out("Press RETURN to get started!"),
        _out(),
    ]
    steps.append(_step("cli", "user", term,
                       "回答 no 跳过向导，回车后出现第一个提示符：Router>。"
                       "「>」就是用户模式的标志——最低权限：只能查看少量"
                       "信息，不能做任何配置。提示符是判断当前模式的唯一"
                       "可靠依据，这个场景请始终盯着它。",
                       ["回答 no → 进入用户模式 Router>",
                        "> = 用户模式：最低权限、只读少量信息",
                        "本场景方法论：盯提示符，它随权限变化"]))

    term = term + [
        _in("Router>", "?"),
        _out("Exec commands:"),
        _out("  enable      Turn on privileged commands"),
        _out("  exit        Exit from the EXEC"),
        _out("  show        Show running system information"),
        _out("  ..."),
        _out(),
    ]
    steps.append(_step("cli", "user", term,
                       "第一个基本功：问号帮助。在任何提示符下输入 ? 就列出"
                       "当前模式可用的全部命令（此处为节选）。注意列表里的"
                       " enable——它就是通往特权模式的那扇门。",
                       ["? = 全部帮助：列出当前模式所有命令",
                        "hostname、conf t 不在列表里——用户模式没有配置命令",
                        "看到 enable：通往特权的入口"]))

    term = term + [
        _in("Router>", "en?"),
        _out("enable"),
        _out(),
    ]
    steps.append(_step("cli", "user", term,
                       "部分帮助：只记得开头几个字母？输入 en? ——列出所有以 "
                       "en 开头的命令。结果只有 enable 一个，不用背全拼。",
                       ["en? = 部分帮助：列出 en 开头的命令",
                        "缩写规则同源：能唯一识别即可（conf t = configure terminal）",
                        "帮助不需要背：? 随时可问"]))

    term = term + [
        _in("Router>", "enable"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "输入 enable（或缩写 en）：从用户模式升级到特权模式。"
                       "注意提示符的变化：Router> 变成了 Router#——「>」换"
                       "「#」，权限升级的可见信号。特权模式可以查看所有信息、"
                       "执行保存、重启等操作，但仍不能改配置。",
                       ["enable：用户模式 → 特权模式",
                        "> 变 #：权限升级的可见信号",
                        "特权模式：查看所有信息 + 保存/重启，尚不能配置"]))

    term = term + [
        _in("Router#", "?"),
        _out("   ...（比特权以下多得多的命令：copy / reload / write /",
             ),
        _out("        delete / erase / configure terminal ...）"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "在 Router# 再问一次 ?：可用命令比用户模式多得多——"
                       "copy、reload、write 这些「有破坏力」的命令都出现在"
                       "特权模式。这也解释了为什么后面要给 enable 单独设"
                       "一道密码（那是 passwords 场景的故事）。",
                       ["特权模式命令集远大于用户模式",
                        "reload / write / erase 都在这一层",
                        "权限越大，越需要密码保护（后续场景）"]))

    term = term + [
        _in("Router#", "conf"),
        _out("[Tab] 补全 → configure"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "Tab 补全：输入 conf 后按 Tab——因为以 conf 开头的"
                       "命令唯一（configure），IOS 自动补全。它与缩写是同一"
                       "条规则的两面：能唯一识别即可。conf t 为什么成立？"
                       "configure 的唯一前缀 conf + terminal 的唯一前缀 t。",
                       ["Tab：能唯一识别即补全（conf → configure）",
                        "缩写同规则：conf t = configure terminal",
                        "int + Tab → interface，同理"]))

    term = term + [
        _in("Router#", "conf t"),
        _out(CONF_BANNER),
        _out(),
    ]
    steps.append(_step("cli", "config", term,
                       "conf t 进入全局配置模式，提示符变为 Router(config)#。"
                       "注意回显的提示：End with CNTL/Z——预告了稍后的 "
                       "Ctrl+Z 快捷退出。从这一层开始才能修改设备配置。",
                       ["configure terminal：特权 → 全局配置",
                        "提示符 Router(config)#：第三种模式",
                        "回显预告 CNTL/Z：记住这个伏笔"]))

    term = term + [
        _in("Router(config)#", "hostname R1"),
        _out(),
    ]
    steps.append(_step("cli", "config", term,
                       "第一条真正的配置：hostname R1。配置立即生效——下一"
                       "条命令的提示符就直接变成 R1(config)# 了。主机名是"
                       "最直观的「配置改变了设备」的例子。",
                       ["hostname R1：立即生效",
                        "下一行提示符变 R1(config)# ——配置的即时反馈",
                        "多设备运维时主机名就是身份牌"]))

    term = term + [
        _in("R1(config)#", "no hostname"),
        _out(),
    ]
    steps.append(_step("cli", "config", term,
                       "删除配置的万能公式：怎么配的就怎么删——在原命令前面"
                       "加 no 空格。no hostname 把主机名恢复默认，提示符跟"
                       "着退回 Router(config)#。提示符永远反映当前主机名。",
                       ["no + 原命令 = 删除该配置",
                        "R1(config)# 退回 Router(config)#",
                        "提示符始终跟着 hostname 走"]))

    prompt_len = len("Router(config)#")
    term = term + [
        _in("Router(config)#", "hnostame R1"),
        _out(),
        _out("% Invalid input detected at '^' marker."),
        _out(" " * prompt_len + "^"),
        _out(),
    ]
    steps.append(_step("cli", "config", term,
                       "故意打错：hnostame（字母顺序错了）。IOS 不会说「你"
                       "错了」，而是精确报位置：% Invalid input detected，"
                       "并在下一行用 ^ 标记出错的字符——^ 指着 h，一看就知"
                       "道这个单词从第一个字母就不对。定位错误靠 marker，"
                       "不靠猜。",
                       ["错误提示 + ^ marker：精确定位错在哪",
                        "^ 指到 h：单词从第一字母就拼错",
                        "配合 ? 使用：拼不全就问，别硬猜"]))

    term = term + [
        _in("Router(config)#", "hostname R1"),
        _out(),
    ]
    steps.append(_step("cli", "config", term,
                       "改正重输：hostname R1。这次没有任何报错——命令正确"
                       "时 IOS 通常保持安静。提示符再次变为 R1(config)#。",
                       ["改正重输：无输出 = 成功",
                        "IOS 的哲学：出错才说话",
                        "提示符又变 R1(config)# 了"]))

    term = term + [
        _in("R1(config)#", "exit"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "exit 是「返回上一层」：全局配置 → 特权模式。提示符"
                       " R1(config)# 变 R1#。",
                       ["exit：退一层（config → priv）",
                        "R1# ：回到特权模式",
                        "退出不会丢配置——配置在 running-config 里"]))

    term = term + [
        _in("R1#", "exit"),
        _out(),
    ]
    steps.append(_step("cli", "user", term,
                       "再 exit：特权 → 用户模式，回到 R1>。逐层退出，一步"
                       "一层。",
                       ["再 exit：priv → user，回到 R1>",
                        "模式层级：user ⊂ priv ⊂ config",
                        "逐层退 = 一层一步"]))

    term = term + [
        _in("R1>", "enable"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "再次快速升到特权模式（配合缩写 en 更快）。下一拍演示"
                       "进配置模式的捷径。",
                       ["en（缩写）再次升特权",
                        "三种进出命令都在手上：enable / conf t / exit",
                        "下一拍：Ctrl+Z 捷径"]))

    term = term + [
        _in("R1#", "conf t"),
        _out(CONF_BANNER),
        _out(),
    ]
    steps.append(_step("cli", "config", term,
                       "再次进入全局配置模式，这次是为了演示快捷键。",
                       ["conf t：再次进入全局配置",
                        "提示符 R1(config)#",
                        "接下来不敲命令，敲快捷键"]))

    term = term + [
        _in("R1(config)#", "[Ctrl+Z]"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "Ctrl+Z（即回显里的 CNTL/Z）：从任意配置层一步直跳"
                       "特权模式——不用 exit 一层层退。exit 是「退一层」，"
                       "Ctrl+Z 是「配置结束，直接回特权」。两条路都合法，"
                       "看你要不要顺路经过中间层。",
                       ["Ctrl+Z：任意配置层 → 特权模式，一步直达",
                        "exit 退一层；Ctrl+Z 直跳到底",
                        "配置随之生效（End with CNTL/Z 的兑现）"]))

    steps.append(_step("final", "priv", term,
                       "全程回顾：三种模式 = 三种权限，提示符就是身份证——"
                       "Router>（用户，最低权限，只读少量信息）→ Router#"
                       "（特权，查看一切 + 保存/重启）→ Router(config)#"
                       "（全局配置，能改设备）。进出命令：enable 升、"
                       "conf t 再进、exit 退一层、Ctrl+Z 直跳特权。基本功："
                       "? 帮助、Tab 补全、缩写、^ 定位错误、no 删除。"
                       "点击「📖 原理」看三模式对照表。",
                       ["三模式：> 用户 / # 特权 / (config)# 配置",
                        "进出：enable ↑ · conf t ↑ · exit ↓一层 · Ctrl+Z ↓到底",
                        "基本功：? / Tab / 缩写 / ^ marker / no"]))
    return steps


# ---- 场景二：save（配置保存，21 步） --------------------------------------

def _save_story():
    files = {"ram": [], "nvram": []}

    def snapshot():
        return {"ram": list(files["ram"]), "nvram": list(files["nvram"])}

    term = [
        _out("Router con0 is now available"),
        _out(),
        _out("Press RETURN to get started."),
        _out(),
    ]
    steps = [
        _step("initial", "user", term,
              "还是那台空配设备（开机向导已在上个场景见过，这里选过 no "
              "直接跳过）。本场景的主角是两份配置文件：running-config——"
              "正在运行、存在 RAM（内存）里，断电即失；startup-config——"
              "开机加载、存在 NVRAM 里，断电不丢。盯住右侧面板的两个盒子："
              "现在都是空的。",
              ["running-config：RAM 中，正在跑，断电即失",
               "startup-config：NVRAM 中，开机加载，持久",
               "右侧双盒实时显示两份文件的内容"], files=snapshot()),
    ]

    term = term + [_in("Router>", "enable"), _out()]
    steps.append(_step("cli", "priv", term,
                       "enable 升到特权模式——配置操作都要从这里出发。",
                       ["enable → 特权模式", "配置的起点：特权模式",
                        "提示符 Router#"], files=snapshot()))

    term = term + [_in("Router#", "conf t"), _out(CONF_BANNER), _out()]
    steps.append(_step("cli", "config", term,
                       "进入全局配置模式，开始配置。",
                       ["conf t → 全局配置", "提示符 Router(config)#",
                        "敲第一条配置"], files=snapshot()))

    term = term + [_in("Router(config)#", "hostname R2"), _out()]
    files["ram"] = ["hostname R2"]
    steps.append(_step("cli", "config", term,
                       "hostname R2。看右侧面板：RAM 盒子里长出了这一行——"
                       "每敲一条配置，它立刻进入 running-config。而 NVRAM "
                       "盒还是空的：你还没保存过。",
                       ["hostname R2 → 立即写入 running-config（RAM）",
                        "面板：RAM=1 行，NVRAM=0 行",
                        "「配置了」≠「保存了」"], files=snapshot()))

    term = term + [_in("R2(config)#", "exit"), _out()]
    steps.append(_step("cli", "priv", term,
                       "退回特权模式——show 命令在特权模式执行。",
                       ["exit → 特权模式", "show 命令的执行位置：特权模式",
                        "R2(config)# → R2#"], files=snapshot()))

    term = term + [
        _in("R2#", "show running-config"),
        _out("Building configuration..."),
        _out(),
        _out("Current configuration : 55 bytes"),
        _out("!"),
        _out("hostname R2"),
        _out("!"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "show running-config：查看当前正在运行的配置——刚才"
                       "敲的 hostname R2 就在这里。它读的就是 RAM（面板左"
                       "盒）。",
                       ["show running-config：看当前生效配置",
                        "hostname R2 在列——读的是 RAM",
                        "刚敲的配置都会出现在这里"], files=snapshot()))

    term = term + [
        _in("R2#", "show startup-config"),
        _out("startup-config is not present"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "show startup-config：查看开机加载的配置——结果是 "
                       "not present（不存在）。空配机从未保存过，NVRAM 盒"
                       "空空如也。两份配置此刻完全不同步。",
                       ["show startup-config：看开机配置",
                        "not present：NVRAM 里什么都没有",
                        "RAM 有一行 / NVRAM 空——不同步"], files=snapshot()))

    steps.append(_step("cli", "priv", term,
                       "对照面板梳理一遍：running-config（RAM）里有 "
                       "hostname R2，startup-config（NVRAM）为空。关键推论"
                       "——设备重启时只会从 NVRAM 加载。也就是说：现在重启，"
                       "hostname R2 就没了。要验证这个推论吗？",
                       ["重启只从 NVRAM 加载",
                        "RAM 里的东西不会自己进 NVRAM",
                        "推论：现在 reload = 配置丢失"], files=snapshot()))

    term = term + [
        _in("R2#", "reload"),
        _out(),
        _out("Proceed with reload? [confirm]"),
        _out(),
        _out("……（设备重启：未保存的 running-config 随内存清空）……"),
        _out(),
    ]
    files["ram"] = []
    steps.append(_step("cli", "user", term,
                       "没保存，直接 reload（确认提示处回车）。设备重启：RAM "
                       "断电即清——面板左盒瞬间清空，hostname R2 没了！重"
                       "启后回到空配的 Router>。这就是「配了但没保存」的"
                       "代价，每个初学者都栽过的一次。",
                       ["不保存 reload：RAM 清空，配置全丢",
                        "面板：RAM 归零（NVRAM 本来就空）",
                        "重启回到空配 Router>"], files=snapshot()))

    term = term + [_in("Router>", "enable"), _out()]
    steps.append(_step("cli", "priv", term,
                       "验证丢失：升到特权模式看看配置还在不在。",
                       ["重启后再进特权模式", "提示符回到 Router——主机名没了",
                        "下一步 show run 验证"], files=snapshot()))

    term = term + [
        _in("Router#", "show running-config"),
        _out("Building configuration..."),
        _out(),
        _out("Current configuration : 0 bytes"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "show running-config 确认：配置真的没了（0 bytes 的"
                       "空配）。重来一遍，这次记住保存。",
                       ["show run：0 bytes——hostname R2 消失",
                        "RAM 清空即历史清零",
                        "重配 + 这次记得 write"], files=snapshot()))

    term = term + [_in("Router#", "conf t"), _out(CONF_BANNER), _out()]
    steps.append(_step("cli", "config", term,
                       "重新进入配置模式。",
                       ["重来：conf t", "同样的操作再来一遍",
                        "区别只在最后一步：保存"], files=snapshot()))

    term = term + [_in("Router(config)#", "hostname R2"), _out()]
    files["ram"] = ["hostname R2"]
    steps.append(_step("cli", "config", term,
                       "hostname R2——RAM 盒再次长出这一行。",
                       ["hostname R2 重新写入 RAM", "面板：RAM=1，NVRAM 仍=0",
                        "这次用 write 同步"], files=snapshot()))

    term = term + [_in("R2(config)#", "exit"), _out()]
    steps.append(_step("cli", "priv", term,
                       "退回特权模式（write 在特权模式执行）。",
                       ["exit → 特权模式", "write 的执行位置：特权模式",
                        "下一拍：保存"], files=snapshot()))

    term = term + [
        _in("R2#", "write"),
        _out("Building configuration..."),
        _out("[OK]"),
        _out(),
    ]
    files["nvram"] = ["hostname R2"]
    steps.append(_step("cli", "priv", term,
                       "write（等价 write memory / copy run start）：把 "
                       "running-config 拷贝进 NVRAM 的 startup-config。"
                       "回显 [OK]，面板右盒长出同一行——两份配置同步了。",
                       ["write：running → startup 的拷贝",
                        "面板：RAM 与 NVRAM 各 1 行，同步",
                        "从此重启不丢"], files=snapshot()))

    term = term + [
        _in("R2#", "reload"),
        _out(),
        _out("Proceed with reload? [confirm]"),
        _out(),
        _out("……（设备重启：开机从 NVRAM 加载 startup-config）……"),
        _out(),
    ]
    steps.append(_step("cli", "user", term,
                       "再 reload 一次（同样确认）。这次重启的行为不同：开机"
                       "时设备从 NVRAM 加载 startup-config 到 RAM——面板左"
                       "盒从右盒恢复出 hostname R2。保存的意义在此刻兑现。",
                       ["保存后 reload：开机从 NVRAM 加载",
                        "面板：RAM 从 NVRAM 恢复 = 1 行",
                        "对照上一轮：一步 write 的差别"], files=snapshot()))

    term = term + [_in("R2>", "enable"), _out()]
    steps.append(_step("cli", "priv", term,
                       "重启后提示符是 R2>——主机名活着！配置随开机加载回来"
                       "了。这就是「重启不丢」的实证。",
                       ["提示符 R2>：hostname 随开机恢复",
                        "RAM 从 NVRAM 重新装载",
                        "重启不丢 = 已保存"], files=snapshot()))

    term = term + [
        _in("R2#", "write erase"),
        _out("Erasing the nvram filesystem will remove all configuration files! Continue? [confirm]"),
        _out(),
        _out("[OK]"),
        _out(),
    ]
    files["nvram"] = []
    steps.append(_step("cli", "priv", term,
                       "恢复出厂的最后一步：write erase 清空 NVRAM（确认后 "
                       "[OK]）。面板右盒清空——开机配置没了。RAM 里的还在，"
                       "但重启后两边都不会剩。",
                       ["write erase：清空 NVRAM 的 startup-config",
                        "面板：NVRAM=0（RAM 暂仍=1）",
                        "重启后即恢复出厂"], files=snapshot()))

    term = term + [
        _in("R2#", "reload"),
        _out(),
        _out("Proceed with reload? [confirm]"),
        _out(),
        _out("--- System Configuration Dialog ---"),
        _out(SETUP_QUESTION),
        _out(),
    ]
    files["ram"] = []
    steps.append(_step("cli", "setup", term,
                       "reload 重启：RAM 清空、NVRAM 也是空的——设备回到"
                       "出厂状态。看，开机向导（System Configuration "
                       "Dialog）又回来了！这正是 modes 场景开机的样子："
                       "恢复出厂 = 回到空配开机的原点。",
                       ["重启后空配：开机向导再次出现",
                        "面板：RAM 与 NVRAM 双清零",
                        "与 modes 场景开头呼应——这就是恢复出厂"], files=snapshot()))

    term = term + [
        _in(SETUP_QUESTION, "no"),
        _out(),
        _out("Press RETURN to get started!"),
        _out(),
    ]
    steps.append(_step("cli", "user", term,
                       "照旧回答 no，回到用户模式。设备完成了一次完整的"
                       "「配置 → 丢失 → 重配 → 保存 → 恢复出厂」循环。",
                       ["回答 no → Router>，循环闭环",
                        "出厂状态：无主机名、无配置",
                        "两句话总结见下一步"], files=snapshot()))

    steps.append(_step("final", "user", term,
                       "带走两句话：① running-config 在 RAM 里跑、易失，"
                       "startup-config 在 NVRAM 里躺、持久，重启只加载后者；"
                       "② write 是把 RAM 拷进 NVRAM 的动作——不 write 的"
                       "配置只活到断电为止。恢复出厂 = write erase + reload。"
                       "点击「📖 原理」看两份配置的对照表。",
                       ["running=RAM 易失；startup=NVRAM 持久",
                        "write：RAM → NVRAM；reload 只加载 NVRAM",
                        "恢复出厂：write erase + reload"], files=snapshot()))
    return steps


# ---- 场景三：passwords（双密码关卡，27 步） --------------------------------

def _passwords_story():
    pw = {"console_pw": "", "console_login": False,
          "enable_password": "", "enable_secret": ""}

    def snapshot():
        return dict(pw)

    term = [
        _out("R1 con0 is now available"),
        _out(),
        _out("Press RETURN to get started."),
        _out(),
    ]
    steps = [
        _step("initial", "user", term,
              "设备 R1（主机名已配好）。本场景给设备上两道锁：第一道 "
              "Console 门——防止任何人插根 Console 线就进设备；第二道 "
              "enable 门——守住特权模式这个「能 reload、能 write 的层」。"
              "当前两道门都没有。右侧面板实时显示密码配置。",
              ["两道关卡：Console 门（进设备）+ enable 门（进特权）",
               "Console 门由 line console 0 + password + login 构成",
               "enable 门由 enable password / secret 构成"], pw=snapshot()),
    ]

    term = term + [_in("R1>", "enable"), _out()]
    steps.append(_step("cli", "priv", term,
                       "先体验没有锁的 enable：直接就进特权模式了——谁能到"
                       "用户模式，谁就能一路升到特权。",
                       ["无锁的 enable：直接升特权",
                        "特权层「裸奔」：reload/write 敞开",
                        "先配 Console 门"], pw=snapshot()))

    term = term + [_in("R1#", "conf t"), _out(CONF_BANNER), _out()]
    steps.append(_step("cli", "config", term,
                       "进入全局配置模式。",
                       ["conf t → 全局配置", "R1(config)#",
                        "Console 密码在线路子模式配置"], pw=snapshot()))

    term = term + [_in("R1(config)#", "line console 0"), _out()]
    steps.append(_step("cli", "config-line", term,
                       "line console 0：进入 Console 线路（本地管理口）的"
                       "配置子模式。提示符变成 R1(config-line)#——注意它是"
                       "config 的子模式，模式图上显示为全局配置盒内的芯片。",
                       ["line console 0：Console 线路子模式",
                        "提示符 (config-line)#：config 的子层",
                        "密码就配在这条线路上"], pw=snapshot()))

    term = term + [_in("R1(config-line)#", "password CCNA"), _out()]
    pw["console_pw"] = "CCNA"
    steps.append(_step("cli", "config-line", term,
                       "password CCNA：给 Console 线路设密码。但注意右侧面"
                       "板——console_login 还是 ✗：光有密码还不生效，差一句"
                       "开关命令。这是本场景第一个坑，先记住，等下验证。",
                       ["password CCNA：密码已设置",
                        "但 login 还没配——密码尚未启用",
                        "面板：console_pw=CCNA，login=✗"], pw=snapshot()))

    term = term + [_in("R1(config-line)#", "exit"), _out()]
    steps.append(_step("cli", "config", term,
                       "先退出线路子模式（回上一层 config）。",
                       ["exit 退回 config", "(config-line)# → (config)#",
                        "准备验证坑一"], pw=snapshot()))

    term = term + [_in("R1(config)#", "exit"), _out()]
    steps.append(_step("cli", "priv", term,
                       "退回特权模式。",
                       ["exit → 特权", "R1#", "再退一层就登出"], pw=snapshot()))

    term = term + [
        _in("R1#", "exit"),
        _out(),
        _out("R1 con0 is now available"),
        _out("Press RETURN to get started."),
        _out(),
        _out("R1>"),
        _out(),
    ]
    steps.append(_step("cli", "user", term,
                       "坑一实锤：exit 登出后重新连接 Console——没有问密码，"
                       "直接就出现 R1>！password CCNA 配了却形同虚设，因为"
                       "少了那句开关：login。",
                       ["重连验证：没有密码提示，直接 R1>",
                        "坑一：配了 password 没配 login = 白配",
                        "login 才是启用密码检查的开关"], pw=snapshot()))

    term = term + [_in("R1>", "enable"), _out()]
    steps.append(_step("cli", "priv", term,
                       "回去补配置：先进特权。",
                       ["回去补 login", "enable → 特权", "差一句就能锁上门"],
                       pw=snapshot()))

    term = term + [_in("R1#", "conf t"), _out(CONF_BANNER), _out()]
    steps.append(_step("cli", "config", term,
                       "再次进入配置模式。",
                       ["conf t", "R1(config)#", "直奔 line console 0"],
                       pw=snapshot()))

    term = term + [_in("R1(config)#", "line console 0"), _out()]
    steps.append(_step("cli", "config-line", term,
                       "进入 Console 线路子模式。",
                       ["line console 0", "(config-line)#", "补上开关"],
                       pw=snapshot()))

    term = term + [_in("R1(config-line)#", "login"), _out()]
    pw["console_login"] = True
    steps.append(_step("cli", "config-line", term,
                       "login：启用 Console 密码检查。面板上 console_login "
                       "翻成 ✓——密码这才真正上岗。记住这组三件套："
                       "line console 0 + password xxx + login，缺一不可。",
                       ["login：启用密码检查（必须加）",
                        "面板：console_login=✓，Console 门上锁",
                        "三件套：line console 0 / password / login"],
                       pw=snapshot()))

    term = term + [_in("R1(config-line)#", "exit"), _out()]
    steps.append(_step("cli", "config", term,
                       "退出线路子模式，准备再验证。",
                       ["exit → config", "验证第一道门",
                        "这次应该要密码了"], pw=snapshot()))

    term = term + [_in("R1(config)#", "exit"), _out()]
    steps.append(_step("cli", "priv", term,
                       "退回特权模式。",
                       ["exit → 特权", "R1#", "登出重连"],
                       pw=snapshot()))

    term = term + [
        _in("R1#", "exit"),
        _out(),
        _out("User Access Verification"),
        _in("Password:", "CCNA", silent=True),
        _out(),
        _out("R1>"),
        _out(),
    ]
    steps.append(_step("cli", "user", term,
                       "重连验证：这次出现 User Access Verification 和 "
                       "Password: 提示。输入 CCNA（真实设备上密码输入完全"
                       "不回显——终端上看不到任何字符，这是 IOS 的正常行为）。"
                       "密码正确 → 进入 R1>。第一道门 ✓。",
                       ["重连：这次要密码了",
                        "输入 CCNA（终端不回显，正常）",
                        "密码对 → R1>：第一道门过"], pw=snapshot()))

    term = term + [_in("R1>", "enable"), _out()]
    steps.append(_step("cli", "priv", term,
                       "来到第二道门的位置：enable。此刻 enable 还没有密码——"
                       "直接进了 R1#。特权层仍在大门敞开，接下来补第二把锁。",
                       ["enable：无密码直接进 # ——第二道门缺席",
                        "特权裸奔：能 reload、能 erase",
                        "配 enable 密码（两种）"], pw=snapshot()))

    term = term + [_in("R1#", "conf t"), _out(CONF_BANNER), _out()]
    steps.append(_step("cli", "config", term,
                       "进入配置模式，配 enable 密码。IOS 提供两种：enable "
                       "password（明文）与 enable secret（加密），先配明文版"
                       "看它的毛病。",
                       ["conf t", "enable 密码有两种：password / secret",
                        "先配明文版"], pw=snapshot()))

    term = term + [_in("R1(config)#", "enable password 123456"), _out()]
    pw["enable_password"] = "123456"
    steps.append(_step("cli", "config", term,
                       "enable password 123456：特权密码设好了。但它有个天"
                       "生缺陷——show running-config 里它是明文裸奔的，马"
                       "上验证。",
                       ["enable password 123456",
                        "面板：enable_password=123456（明文）",
                        "缺陷：配置文件里可读——下一步验证"], pw=snapshot()))

    term = term + [_in("R1(config)#", "exit"), _out()]
    steps.append(_step("cli", "priv", term,
                       "退回特权模式查看配置。",
                       ["exit → 特权", "show run 验证明文",
                        "R1#"], pw=snapshot()))

    term = term + [
        _in("R1#", "show running-config"),
        _out("Building configuration..."),
        _out("......"),
        _out("enable password 123456"),
        _out("......"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "show running-config（节选）：enable password 123456 "
                       "赫然在列——明文！任何能看到配置的人都能把特权密码"
                       "读走。这就是它不安全的原因。（Console 段与本话题"
                       "无关，用省略号略过。）",
                       ["show run：enable password 明文裸奔",
                        "能看配置 = 能拿走密码",
                        "对策：enable secret"], pw=snapshot()))

    term = term + [_in("R1#", "conf t"), _out(CONF_BANNER), _out()]
    steps.append(_step("cli", "config", term,
                       "回去配加密版。",
                       ["conf t", "配 enable secret", "加密版登场"],
                       pw=snapshot()))

    term = term + [_in("R1(config)#", "enable secret Cisco@123"), _out()]
    pw["enable_secret"] = "Cisco@123"
    steps.append(_step("cli", "config", term,
                       "enable secret Cisco@123：加密的特权密码。规则：两种"
                       "密码同时存在时，以 secret 为准，password 自动失效。"
                       "面板上两把 enable 锁并列——马上实证谁说了算。",
                       ["enable secret Cisco@123（加密存储）",
                        "并存规则：secret 为准，password 失效",
                        "面板：两把 enable 锁并列——验证在即"], pw=snapshot()))

    term = term + [_in("R1(config)#", "exit"), _out()]
    steps.append(_step("cli", "priv", term,
                       "退回特权，再看一眼配置里两者的差别。",
                       ["exit → 特权", "对比明文与密文的存储形态",
                        "R1#"], pw=snapshot()))

    term = term + [
        _in("R1#", "show running-config"),
        _out("Building configuration..."),
        _out("......"),
        _out("enable secret 5 $1$9Q8O$mVCMssrcoibWUb9CioLol."),
        _out("enable password 123456"),
        _out("......"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "show running-config（节选）：secret 那行存的是密文"
                       "（$1$ 开头的一串乱码），password 那行仍是明文——"
                       "同一台设备上两种形态并存。但真正管门的只有 secret。",
                       ["secret 行：密文（$1$…）", "password 行：仍明文",
                        "两行并存，生效的是 secret——下一步实证"], pw=snapshot()))

    term = term + [
        _in("R1#", "exit"),
        _out(),
        _out("User Access Verification"),
        _in("Password:", "CCNA", silent=True),
        _out(),
        _out("R1>"),
        _out(),
    ]
    steps.append(_step("cli", "user", term,
                       "登出重连，完整走一遍两道门：第一道 Console 门输 "
                       "CCNA（不回显）→ R1> ✓。",
                       ["重连：第一道门（Console）输 CCNA → 过",
                        "不回显依旧",
                        "重点在第二道门"], pw=snapshot()))

    term = term + [
        _in("R1>", "enable"),
        _out(),
        _out("Password:"),
        _in("Password:", "123456", silent=True),
        _out(),
        _out("% Bad secrets"),
        _out(),
        _out("Password:"),
        _in("Password:", "Cisco@123", silent=True),
        _out(),
        _out("R1#"),
        _out(),
    ]
    steps.append(_step("cli", "priv", term,
                       "坑二实锤：第二道门输 123456（enable password 的明"
                       "文值）——% Bad secrets，被拒！再输 Cisco@123"
                       "（secret 的值）——R1#，进去了。两把锁同时在，但门"
                       "只认 secret：并存时 password 失效的规则眼见为实。",
                       ["输 123456 → % Bad secrets：password 不认",
                        "输 Cisco@123 → R1#：secret 才是门锁",
                        "规则实证：并存时以 secret 为准"], pw=snapshot()))

    steps.append(_step("final", "priv", term,
                       "收束成三句话：① Console 门三件套缺一不可——line "
                       "console 0 + password xxx + login（login 是开关，"
                       "不配等于没锁）；② enable 门用 secret 不用 password"
                       "——明文密码会在 show run 里裸奔；③ 两种 enable 密"
                       "码并存时，secret 为准。两道门锁好，设备才算有了基"
                       "本的安全底线。点击「📖 原理」看双关卡对照。",
                       ["Console 门：三件套，login 必加",
                        "enable 门：用 secret（密文），弃 password（明文）",
                        "并存时 secret 为准——已实证"], pw=snapshot()))
    return steps


_STORIES = {"modes": _modes_story, "save": _save_story,
            "passwords": _passwords_story}


@dataclass
class IosResult:
    scenario: str
    chain: Chain
    steps: list
    mode_changes: int         # 模式发生变化的步数（摘要/测试用）


MODE_ORDER = ("setup", "user", "priv", "config", "config-line")


def simulate(scenario="modes"):
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario!r} "
                         f"(choose from {', '.join(SCENARIOS)})")
    steps = _STORIES[scenario]()
    changes = sum(1 for i in range(1, len(steps))
                  if steps[i]["mode"] != steps[i - 1]["mode"])
    return IosResult(scenario, _empty_chain(), steps, changes)
