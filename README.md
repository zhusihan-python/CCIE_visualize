# CCNA 可视化系列（visualizer）

配套《CCNA 学习资料》课程笔记的教学可视化工具。架构完全沿用
[stpAlgorithmVisualizer](../../stpAlgorithmVisualizer) 的成熟模式：
**算法/故事逻辑只在 Python，每步附中文讲解；渲染端是零依赖的原生
JS + canvas 单文件 HTML，双击即用**。

## 快速开始

```bash
python3 generate.py                                # 跨网段场景 -> encap.html
python3 generate.py -t same-net                    # 同网段对照场景 -> encap-same.html
python3 generate.py -p troubleshoot                # 排错·网线中断 -> troubleshoot.html
python3 generate.py -p troubleshoot -t service     # 排错·服务未启动
python3 generate.py --json doc.json                # 同时导出原始步骤数据
open encap.html                                    # 双击打开也行，无需服务器
```

播放器：⏮ ◀ ▶ ▶| ⏭ / 空格 / ←→ / Home / End，0.5–2× 速度；
「📖 原理」弹窗讲解核心思路；右侧「分层对照」面板实时高亮当前步骤
所在层（OSI 七层 / TCP/IP 对等五层 / TCP/IP 四层三列对齐，点击任意层
查看它的作用）。

## 内容一：封装与解封装（第 02 课 · `-p encap`）

一条 HTTP 请求的完整旅程，每步同时展示：所在设备、PDU 形态
（数据 → 段 → 包 → 帧 → 比特的嵌套头图）、OSI 层号。

- **跨网段场景（默认，17 步）**：PC1 → SW1 → R1（网关）→ SW2 → PC2。
  核心 teaching 点：交换机只看二层、帧内容不变；路由器拆到三层、
  查路由表后**重写 MAC 重新封装**——IP 头端到端不变，MAC 头每跳改写。
- **同网段场景（12 步）**：PC1 → SW1 → PC2。无路由器，MAC 端到端不变，
  与跨网段场景互为对照。

## 内容二：分层排错故事线（第 02 课 §七 · `-p troubleshoot`）

症状统一：PC1 打不开 PC2 的网页 `http://192.168.2.10`。按课程
「自底向上、医院分诊」方法论逐层检查：1️⃣物理 → 2️⃣链路 → 3️⃣网络
→ 4️⃣应用；**通过=排除继续向上，失败=定位→修复→验证**。三个场景=
同一方法论的三种断点：

| 场景 | 故障层 | 教学看点 |
|---|---|---|
| `-t cable`（默认，6 步） | L1 网线中断 | 首查即命中——自底向上对低层故障最快 |
| `-t ip-config`（8 步） | L3 IP 配错网段 | 前两层逐一排除后定位——排除法收窄范围 |
| `-t service`（9 步） | L4·L7 服务未启动 | ping 通一次性排除 L1–L3；ping 通 ≠ 应用好 |

画布语义：红色 ✕ 虚线链路 = 断线（换线后消失）；设备上方 ⚠ = 定位到
的故障设备（复查通过后摘除）；下半画布是自底向上的检查清单
（✓ 通过 / ✗ 失败 / · 未查，当前检查行高亮）；ping 以琥珀点直线往返
表示成功，中途跌落 + 红 ✕ 表示失败。

## 代码结构

| 文件 | 职责 |
|---|---|
| `encap.py` | 封装/解封装故事生成器（纯逻辑）：设备链、两场景、步骤 + 中文讲解 |
| `troubleshoot.py` | 分层排错故事生成器（纯逻辑）：三故障场景、检查清单快照、ping 事件 |
| `concepts.py` | 「📖 原理」卡内容与分场景看点（按 topic 注册） |
| `generate.py` | CLI 与 `build_document()` 统一入口；`TOPICS` 映射收口场景/标题/输出名；模板占位符替换出单文件 HTML |
| `template.html` | 页面外壳 + 三列分层对照面板（`__DATA__` / `/*__PLAYER__*/` 双占位符） |
| `player.js` | 播放器：设备链/PDU 头图/检查清单画布渲染、比特与 ping 飞行动画、断线 ✕ 与 ⚠ 徽章、层高亮；暴露 `window.PLAYER.setStep` 钩子 |
| `test_*.py` | 故事不变量（PDU/检查序列 ground truth）、原理卡 schema、渲染/CLI 契约 |

## 模拟边界（教学简化）

- 同步串行模型：一次只讲一条请求的方向，不建模 TCP 握手/重传/排序细节。
- 地址与端口为教学示意值（192.168.1.10 等），非真实抓包。
- ARP 仅一句话提及（“网关/对端 MAC 怎么获得”），后续课程展开。
- 防火墙（L3–L7）、AC/AP 等设备只在原理卡中以「设备看层」词条出现，
  不进入故事拓扑。
- 排错场景的 ping 动画与检查项为教学示意：真实环境中「错网段」的表现是
  ARP 解析失败 / 请求超时（画为中途跌落）；不做真实 CLI 命令模拟，
  每层只选一个代表性检查动作。

## 测试

```bash
python3 -m unittest test_encap test_concepts test_render test_troubleshoot
```

