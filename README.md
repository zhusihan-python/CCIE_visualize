# CCNA 可视化系列（visualizer）

配套《CCNA 学习资料》课程笔记的教学可视化工具。架构完全沿用
[stpAlgorithmVisualizer](../../stpAlgorithmVisualizer) 的成熟模式：
**算法/故事逻辑只在 Python，每步附中文讲解；渲染端是零依赖的原生
JS + canvas 单文件 HTML，双击即用**。

## 快速开始

```bash
python3 generate.py                    # 跨网段场景 -> encap.html
python3 generate.py -t same-net        # 同网段对照场景 -> encap-same.html
open encap.html                        # 双击打开也行，无需服务器
python3 generate.py --json doc.json    # 同时导出原始步骤数据
```

播放器：⏮ ◀ ▶ ▶| ⏭ / 空格 / ←→ / Home / End，0.5–2× 速度；
「📖 原理」弹窗讲解分层思路；右侧「分层对照」面板实时高亮当前步骤
所在层（OSI 七层 / TCP/IP 对等五层 / TCP/IP 四层三列对齐，点击任意层
查看它的作用）。

## 当前内容：封装与解封装（第 02 课 · 网络参考模型）

一条 HTTP 请求的完整旅程，每步同时展示：所在设备、PDU 形态
（数据 → 段 → 包 → 帧 → 比特的嵌套头图）、OSI 层号。

- **跨网段场景（默认，17 步）**：PC1 → SW1 → R1（网关）→ SW2 → PC2。
  核心 teaching 点：交换机只看二层、帧内容不变；路由器拆到三层、
  查路由表后**重写 MAC 重新封装**——IP 头端到端不变，MAC 头每跳改写。
- **同网段场景（12 步）**：PC1 → SW1 → PC2。无路由器，MAC 端到端不变，
  与跨网段场景互为对照。

## 代码结构

| 文件 | 职责 |
|---|---|
| `encap.py` | 故事生成器（纯逻辑）：设备链、两场景、步骤 + 中文讲解 |
| `concepts.py` | 「📖 原理」卡内容与分场景看点 |
| `generate.py` | CLI 与 `build_document()` 统一入口；模板占位符替换出单文件 HTML |
| `template.html` | 页面外壳 + 三列分层对照面板（`__DATA__` / `/*__PLAYER__*/` 双占位符） |
| `player.js` | 播放器：设备链/PDU 头图画布渲染、比特飞行、层高亮；暴露 `window.PLAYER.setStep` 钩子 |
| `test_*.py` | 故事不变量（PDU 状态机 ground truth）、原理卡 schema、渲染/CLI 契约 |

## 模拟边界（教学简化）

- 同步串行模型：一次只讲一条请求的方向，不建模 TCP 握手/重传/排序细节。
- 地址与端口为教学示意值（192.168.1.10 等），非真实抓包。
- ARP 仅一句话提及（“网关/对端 MAC 怎么获得”），后续课程展开。
- 防火墙（L3–L7）、AC/AP 等设备只在原理卡中以「设备看层」词条出现，
  不进入故事拓扑。

## 测试

```bash
python3 -m unittest test_encap test_concepts test_render   # 34 tests
```
