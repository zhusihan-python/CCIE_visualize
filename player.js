/* Step-animation player for the CCNA encapsulation visualizer.
 *
 * Expects the host page to contain the shell markup (see template.html):
 * #title #subtitle #stage #stacks #stackgrid #stack-note
 * #btn-first/prev/play/next/last #speed #btn-concept #counter
 * #desc #events #concept-modal #concept-body.
 *
 * Boot with `bootPlayer(document)`; calling it again swaps the story.
 * Pages that embed a finished document just set window.PLAYER_DATA
 * before loading this file. The player is a dumb renderer: every step
 * carries the full snapshot (device / PDU chips / OSI layer number).
 */
(function () {
  'use strict';

  const W = 960, H = 640;
  const PACKET_MS = 1300, HOLD_MS = 900, STATIC_MS = 1400;
  const DEV_Y = 128, BOX_W = 118, BOX_H = 62;
  const BIT_COUNT = 8, BIT_GAP = 0.055;

  const CHIP_STYLE = {
    eth:  { fill: '#0c4a6e', border: '#38bdf8', text: '#bae6fd', w: 150 },
    ip:   { fill: '#78350f', border: '#fbbf24', text: '#fde68a', w: 150 },
    tcp:  { fill: '#134e4a', border: '#2dd4bf', text: '#99f6e4', w: 140 },
    data: { fill: '#334155', border: '#94a3b8', text: '#e2e8f0', w: 190 },
    fcs:  { fill: '#4c1d95', border: '#a78bfa', text: '#ddd6fe', w: 64 },
  };
  const KIND_BADGE = { pc: '终端', switch: '二层', router: '三层' };

  const $ = id => document.getElementById(id);

  // Mutable player state, rebuilt by bootPlayer().
  const S = { ready: false };
  let rafHandle = null;
  let keysBound = false;

  function setStep(i, keepPlaying) {
    if (!S.ready) return;
    if (!keepPlaying) { S.playing = false; }
    S.cur = Math.max(0, Math.min(S.steps.length - 1, i));
    S.enterTime = performance.now();
    const st = S.steps[S.cur];
    // 任何带 events 的步骤都生成飞行粒子（encap 的 move 比特流、
    // troubleshoot 的 ping 往返/跌落），播放器不再按 kind 特判
    S.packets = (st.events || []).map(e => ({
      from: S.pos[e.from], to: S.pos[e.to],
      delay: e.delay || 0, kind: e.kind || 'bits',
      drop: e.drop, label: e.label,
    }));
    renderPanels();
    updateButtons();
  }

  function renderPanels() {
    const st = S.steps[S.cur];
    $('counter').textContent = '第 ' + (S.cur + 1) + ' / ' + S.steps.length + ' 步';
    $('desc').textContent = st.description +
      (S.cur === 0 && S.DATA.concept ? '（💡 可先点右上角「📖 原理」了解核心思路。）' : '');
    const list = $('events');
    list.innerHTML = '';
    st.bullets.forEach(b => {
      const li = document.createElement('li');
      li.textContent = b;
      list.appendChild(li);
    });
    highlightStacks(st.layer);
  }

  function highlightStacks(layer) {
    document.querySelectorAll('#stackgrid .cell').forEach(c => {
      const parts = c.dataset.layers.split('-').map(Number);
      const lo = parts[0], hi = parts.length > 1 ? parts[1] : parts[0];
      c.classList.toggle('hot', layer >= lo && layer <= hi);
    });
  }

  function updateButtons() {
    $('btn-first').disabled = $('btn-prev').disabled = S.cur === 0;
    $('btn-next').disabled = $('btn-last').disabled =
      S.cur === S.steps.length - 1;
    $('btn-play').textContent = S.playing ? '⏸' : '▶';
  }

  function lerp(p1, p2, t) {
    return { x: p1.x + (p2.x - p1.x) * t, y: p1.y + (p2.y - p1.y) * t };
  }

  function drawX(ctx, at, color) {
    ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(at.x - 7, at.y - 7); ctx.lineTo(at.x + 7, at.y + 7);
    ctx.moveTo(at.x + 7, at.y - 7); ctx.lineTo(at.x - 7, at.y + 7);
    ctx.stroke();
  }

  // ---- 设备链绘制 ------------------------------------------------------

  function drawGlyph(ctx, kind, cx, cy) {
    ctx.save();
    ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 1.6; ctx.lineJoin = 'round';
    if (kind === 'pc') {
      ctx.strokeRect(cx - 12, cy - 11, 24, 16);
      ctx.beginPath();
      ctx.moveTo(cx - 5, cy + 5); ctx.lineTo(cx + 5, cy + 5);
      ctx.moveTo(cx, cy + 5); ctx.lineTo(cx, cy + 10);
      ctx.stroke();
    } else if (kind === 'switch') {
      ctx.strokeRect(cx - 13, cy - 8, 26, 15);
      ctx.beginPath();
      ctx.moveTo(cx - 8, cy - 3); ctx.lineTo(cx - 2, cy - 3);
      ctx.moveTo(cx - 3.5, cy - 5.5); ctx.lineTo(cx - 1.5, cy - 3);
      ctx.lineTo(cx - 3.5, cy - 0.5);
      ctx.moveTo(cx + 8, cy + 2); ctx.lineTo(cx + 2, cy + 2);
      ctx.moveTo(cx + 3.5, cy - 0.5); ctx.lineTo(cx + 1.5, cy + 2);
      ctx.lineTo(cx + 3.5, cy + 4.5);
      ctx.stroke();
    } else {  // router：圆 + 四向箭头
      ctx.beginPath(); ctx.arc(cx, cy, 11, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(cx - 6, cy); ctx.lineTo(cx + 6, cy);
      ctx.moveTo(cx, cy - 6); ctx.lineTo(cx, cy + 6);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(cx + 6, cy); ctx.lineTo(cx + 3, cy - 2.6);
      ctx.lineTo(cx + 3, cy + 2.6); ctx.closePath();
      ctx.moveTo(cx - 6, cy); ctx.lineTo(cx - 3, cy - 2.6);
      ctx.lineTo(cx - 3, cy + 2.6); ctx.closePath();
      ctx.moveTo(cx, cy + 6); ctx.lineTo(cx - 2.6, cy + 3);
      ctx.lineTo(cx + 2.6, cy + 3); ctx.closePath();
      ctx.moveTo(cx, cy - 6); ctx.lineTo(cx - 2.6, cy - 3);
      ctx.lineTo(cx + 2.6, cy - 3); ctx.closePath();
      ctx.fillStyle = '#cbd5e1'; ctx.fill();
    }
    ctx.restore();
  }

  function drawLinks(ctx, st) {
    const moving = st.kind === 'move' ? st.events[0] : null;
    const down = new Set(st.down_links || []);
    for (const l of S.links) {
      const p1 = S.pos[l.a], p2 = S.pos[l.b];
      const isDown = down.has(l.a + '-' + l.b);
      const active = !isDown && moving &&
        ((moving.from === l.a && moving.to === l.b) ||
         (moving.from === l.b && moving.to === l.a));
      ctx.strokeStyle = isDown ? '#b91c1c' : active ? '#f59e0b' : '#475569';
      ctx.lineWidth = isDown ? 2.5 : active ? 4 : 3;
      if (isDown) ctx.setLineDash([4, 6]);
      ctx.beginPath();
      ctx.moveTo(p1.x + BOX_W / 2 + 3, DEV_Y);
      ctx.lineTo(p2.x - BOX_W / 2 - 3, DEV_Y);
      ctx.stroke();
      ctx.setLineDash([]);
      if (isDown) {
        drawX(ctx, { x: (p1.x + p2.x) / 2, y: DEV_Y }, '#ef4444');
      }
    }
    // 路由器接口标注：按邻接链路的左右顺序对应 interfaces
    for (const dev of S.devices) {
      if (dev.kind !== 'router' || !dev.interfaces.length) continue;
      const neighbor = l => S.pos[l.a === dev.id ? l.b : l.a];
      // interfaces 按从左到右罗列；按邻接方位对应，不依赖链路数组顺序
      const mine = S.links.filter(l => l.a === dev.id || l.b === dev.id)
        .sort((la, lb) => neighbor(la).x - neighbor(lb).x);
      mine.forEach((l, i) => {
        const iface = dev.interfaces[i];
        if (!iface) return;
        const side = neighbor(l).x > S.pos[dev.id].x ? 1 : -1;
        const lx = S.pos[dev.id].x + side * 97;
        ctx.font = '10.5px sans-serif'; ctx.textAlign = 'center';
        ctx.fillStyle = '#7dd3fc';
        ctx.fillText(iface.name, lx, DEV_Y - 20);
        ctx.fillText(iface.ip, lx, DEV_Y - 8);
      });
    }
  }

  function drawDevices(ctx, st) {
    const alerts = new Set(st.alert_devices || []);
    for (const dev of S.devices) {
      const p = S.pos[dev.id];
      const active = st.device === dev.id;
      const x = p.x - BOX_W / 2, y = DEV_Y - BOX_H / 2;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, y, BOX_W, BOX_H, 10);
      else ctx.rect(x, y, BOX_W, BOX_H);
      ctx.fillStyle = active ? '#1d4ed8' : '#334155';
      ctx.fill();
      ctx.lineWidth = active ? 3 : 1.5;
      ctx.strokeStyle = active ? '#93c5fd' : '#475569';
      ctx.stroke();

      if (alerts.has(dev.id)) {
        ctx.font = 'bold 17px sans-serif'; ctx.textAlign = 'center';
        ctx.fillStyle = '#fbbf24';
        ctx.fillText('⚠', p.x + BOX_W / 2 - 6, y - 6);
      }

      drawGlyph(ctx, dev.kind, x + 26, DEV_Y);
      ctx.textAlign = 'left';
      ctx.fillStyle = '#fff'; ctx.font = 'bold 13px sans-serif';
      ctx.fillText(dev.id, x + 46, DEV_Y - 7);
      ctx.fillStyle = active ? '#bfdbfe' : '#94a3b8';
      ctx.font = '10.5px sans-serif';
      ctx.fillText('L' + dev.layer_range[0] + '–L' +
                   dev.layer_range[1] + ' · ' + KIND_BADGE[dev.kind],
                   x + 46, DEV_Y + 9);
      // 框下信息：PC 显示 IP/MAC，其余显示角色标签
      ctx.textAlign = 'center';
      if (dev.kind === 'pc') {
        ctx.fillStyle = '#94a3b8'; ctx.font = '10.5px sans-serif';
        ctx.fillText(dev.ip, p.x, DEV_Y + BOX_H / 2 + 16);
        ctx.fillText('MAC ' + dev.mac, p.x, DEV_Y + BOX_H / 2 + 30);
      } else {
        ctx.fillStyle = '#64748b'; ctx.font = '10.5px sans-serif';
        ctx.fillText(dev.label, p.x, DEV_Y + BOX_H / 2 + 16);
      }
    }
  }

  // ---- PDU 绘制 --------------------------------------------------------

  function drawPdu(ctx, st) {
    ctx.textAlign = 'left'; ctx.font = '12px sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.fillText('当前数据形态（PDU）', 24, 318);
    ctx.textAlign = 'right'; ctx.font = 'bold 22px sans-serif';
    ctx.fillStyle = '#fde68a';
    ctx.fillText(st.pdu_name, W - 24, 324);
    ctx.font = '12px sans-serif'; ctx.fillStyle = '#64748b';
    const hint = { encap: '↓ 封装：自上而下加头',
                   decap: '↑ 解封装：自下而上去头',
                   move: '→ 物理传输：比特流',
                   process: '◎ 中间设备：按自己的层级查看' }[st.kind];
    if (hint) ctx.fillText(hint, W - 24, 344);

    if (!st.pdu.length) {
      ctx.textAlign = 'center'; ctx.font = '13px sans-serif';
      ctx.fillStyle = '#475569';
      ctx.fillText('（数据尚未产生——点 ▶ 或 → 开始封装）', W / 2, 420);
      return;
    }
    if (st.pdu[0].t === 'bits') { drawBits(ctx); return; }

    const prev = S.cur > 0 ? S.steps[S.cur - 1] : null;
    const prevTokens = new Set(prev ? prev.pdu.map(c => c.t) : []);
    const GAP = 8;
    const total = st.pdu.reduce((sum, c) => sum + CHIP_STYLE[c.t].w, 0) +
                  GAP * (st.pdu.length - 1);
    let x = (W - total) / 2;
    const y = 372, h = 92;
    for (const chip of st.pdu) {
      const style = CHIP_STYLE[chip.t];
      const isNew = !prevTokens.has(chip.t);
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, y, style.w, h, 8);
      else ctx.rect(x, y, style.w, h);
      ctx.fillStyle = style.fill; ctx.fill();
      ctx.lineWidth = isNew ? 3 : 1.5;
      ctx.strokeStyle = isNew ? '#facc15' : style.border;
      ctx.stroke();
      ctx.textAlign = 'center';
      ctx.fillStyle = style.border; ctx.font = 'bold 12.5px sans-serif';
      ctx.fillText(chip.title, x + style.w / 2, y + 20);
      ctx.fillStyle = style.text; ctx.font = '11px sans-serif';
      chip.lines.forEach((line, i) => {
        ctx.fillText(line, x + style.w / 2, y + 40 + i * 16);
      });
      if (isNew) {
        ctx.fillStyle = '#facc15'; ctx.font = 'bold 11px sans-serif';
        ctx.fillText('＋ 新增', x + style.w / 2, y - 8);
      }
      x += style.w + GAP;
    }
  }

  function drawBits(ctx) {
    const bw = 560, bx = (W - bw) / 2, by = 380, bh = 56;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(bx, by, bw, bh, 8);
    else ctx.rect(bx, by, bw, bh);
    ctx.fillStyle = '#78350f'; ctx.fill();
    ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.fillStyle = '#fde68a'; ctx.font = 'bold 16px "SF Mono", Menlo, monospace';
    ctx.textAlign = 'center';
    ctx.fillText('10110010  11000101  01110000  01011100 …', W / 2, by + 34);
    ctx.fillStyle = '#94a3b8'; ctx.font = '11.5px sans-serif';
    ctx.fillText('物理层视角：帧已变成比特流（电/光信号）', W / 2, by + bh + 22);
  }

  // ---- 排错检查清单（troubleshoot 主题的下半画布） ----------------------

  function drawChecklist(ctx, st) {
    ctx.textAlign = 'left'; ctx.font = '12px sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.fillText('排错检查清单（自底向上）', 24, 318);
    ctx.textAlign = 'right'; ctx.font = 'bold 20px sans-serif';
    ctx.fillStyle = '#fde68a';
    ctx.fillText(st.layer ? '排错 · 第 ' + st.layer + ' 层' : '排错 · 待分诊',
                 W - 24, 322);

    const rows = st.checks || [];
    const x0 = 48, w = W - 96, rh = 54, gap = 10, y0 = 348;
    rows.forEach((c, i) => {
      const y = y0 + i * (rh + gap);
      const active = st.layer === c.layer &&
                     st.kind !== 'symptom' && st.kind !== 'final';
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x0, y, w, rh, 9);
      else ctx.rect(x0, y, w, rh);
      ctx.fillStyle = c.verdict === 'fail' ? '#450a0a'
                    : active ? '#1e3a8a' : '#263449';
      ctx.fill();
      ctx.lineWidth = active ? 3 : 1.5;
      ctx.strokeStyle = c.verdict === 'fail' ? '#ef4444'
                      : active ? '#93c5fd' : '#334155';
      ctx.stroke();
      ctx.textAlign = 'left';
      ctx.fillStyle = c.verdict === 'fail' ? '#fca5a5' : '#e2e8f0';
      ctx.font = 'bold 14px sans-serif';
      ctx.fillText(c.name, x0 + 16, y + 22);
      ctx.fillStyle = '#94a3b8'; ctx.font = '11.5px sans-serif';
      ctx.fillText(c.detail, x0 + 16, y + 41);
      ctx.textAlign = 'right';
      if (c.verdict === 'pass') {
        ctx.fillStyle = '#4ade80'; ctx.font = 'bold 14px sans-serif';
        ctx.fillText('✓ 通过', x0 + w - 16, y + 33);
      } else if (c.verdict === 'fail') {
        ctx.fillStyle = '#f87171'; ctx.font = 'bold 14px sans-serif';
        ctx.fillText('✗ 失败', x0 + w - 16, y + 33);
      } else {
        ctx.fillStyle = '#64748b'; ctx.font = '13px sans-serif';
        ctx.fillText('· 未查', x0 + w - 16, y + 33);
      }
    });
  }

  // ---- 飞行动画（encap 比特流 / troubleshoot ping 两态） -----------------

  function drawPingDot(ctx, q, label) {
    ctx.beginPath(); ctx.arc(q.x, DEV_Y, 9, 0, Math.PI * 2);
    ctx.fillStyle = '#f59e0b'; ctx.fill();
    ctx.strokeStyle = '#78350f'; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.fillStyle = '#fde68a'; ctx.font = 'bold 10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(label || 'ping', q.x, DEV_Y - 14);
  }

  function drawFlight(ctx, now) {
    let spread = 0;
    for (const pk of S.packets) {
      const base = Math.min(1.35, Math.max(0,
        (now - S.enterTime) / (PACKET_MS / S.speed) - pk.delay));
      if (pk.kind === 'ping') {
        spread = Math.max(spread, pk.delay + (pk.drop !== undefined ? pk.drop : 1));
        if (base <= 0) continue;
        if (pk.drop !== undefined) {
          // 失败版：行至 drop 比例处停住，红 ✕ 持续显示（可截图验证）
          if (base < pk.drop) {
            drawPingDot(ctx, lerp(pk.from, pk.to, base), pk.label);
          } else {
            drawX(ctx, lerp(pk.from, pk.to, pk.drop), '#ef4444');
          }
        } else if (base <= 1) {
          drawPingDot(ctx, lerp(pk.from, pk.to, base), pk.label);
        }
        continue;
      }
      // 比特流（encap move）：一串 1/0 尾迹
      spread = Math.max(spread, pk.delay + (BIT_COUNT - 1) * BIT_GAP);
      for (let k = 0; k < BIT_COUNT; k++) {
        const t = base - k * BIT_GAP;
        if (t <= 0 || t >= 1) continue;
        const q = lerp(pk.from, pk.to, t);
        const label = k % 2 ? '0' : '1';
        ctx.beginPath();
        ctx.arc(q.x, DEV_Y, 8, 0, Math.PI * 2);
        ctx.fillStyle = '#f59e0b'; ctx.fill();
        ctx.strokeStyle = '#78350f'; ctx.lineWidth = 1.5; ctx.stroke();
        ctx.fillStyle = '#1c1917'; ctx.font = 'bold 9.5px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(label, q.x, DEV_Y + 3.5);
      }
    }
    return spread;
  }

  function draw(now) {
    if (!S.ready) return;
    const ctx = S.ctx;
    ctx.clearRect(0, 0, W, H);
    const st = S.steps[S.cur];
    drawLinks(ctx, st);
    drawDevices(ctx, st);
    if (S.DATA.topic === 'troubleshoot') {
      drawChecklist(ctx, st);
    } else {
      drawPdu(ctx, st);
    }
    if (S.packets.length) {
      const spread = drawFlight(ctx, now);
      if (S.playing &&
          now > S.enterTime + ((1 + spread) * PACKET_MS + HOLD_MS) / S.speed) {
        advance();
      }
    } else if (S.playing && now > S.enterTime + STATIC_MS / S.speed) {
      advance();
    }
    rafHandle = requestAnimationFrame(draw);
  }

  function advance() {
    if (S.cur < S.steps.length - 1) setStep(S.cur + 1, true);
    else { S.playing = false; updateButtons(); }
  }

  // ---- 原理卡 / 控件 ---------------------------------------------------

  function buildConceptModal() {
    const modal = $('concept-modal');
    if (!S.DATA.concept) { $('btn-concept').style.display = 'none'; return; }
    $('btn-concept').style.display = '';
    const c = S.DATA.concept;
    let html = '<h2>' + c.title + '</h2>';
    if (c.scenario) html += '<p class="scenario">' + c.scenario + '</p>';
    html += '<h3>要解决的问题</h3><p>' + c.problem + '</p>';
    html += '<h3>核心思路</h3><p>' + c.idea + '</p>';
    if (c.rules) {
      html += '<h3>关键规则</h3><ul>' +
              c.rules.map(r => '<li>' + r + '</li>').join('') + '</ul>';
    }
    if (c.glossary) {
      html += '<h3>术语速查</h3><dl>' +
              c.glossary.map(g => '<dt>' + g[0] + '</dt><dd>' + g[1] + '</dd>')
                        .join('') + '</dl>';
    }
    $('concept-body').innerHTML = html;
    modal.classList.remove('open');
  }

  function bindStacks() {
    if (S.stacksBound) return;
    S.stacksBound = true;
    document.querySelectorAll('#stackgrid .cell').forEach(c => {
      c.onclick = () => { $('stack-note').textContent = c.dataset.note; };
    });
  }

  function bindControls() {
    if (keysBound) return;
    keysBound = true;
    $('btn-first').onclick = () => setStep(0);
    $('btn-prev').onclick = () => setStep(S.cur - 1);
    $('btn-next').onclick = () => setStep(S.cur + 1);
    $('btn-last').onclick = () => setStep(S.steps.length - 1);
    $('btn-play').onclick = () => {
      if (!S.playing && S.cur === S.steps.length - 1) setStep(0);
      S.playing = !S.playing; S.enterTime = performance.now(); updateButtons();
    };
    $('speed').onchange = e => { S.speed = parseFloat(e.target.value); };
    $('btn-concept').onclick = () => $('concept-modal').classList.add('open');
    $('concept-modal').onclick = e => {
      if (e.target === $('concept-modal')) $('concept-modal').classList.remove('open');
    };
    $('concept-close').onclick = () => $('concept-modal').classList.remove('open');
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') $('concept-modal').classList.remove('open');
      if (!S.ready) return;
      if (e.key === 'ArrowLeft') { setStep(S.cur - 1); e.preventDefault(); }
      else if (e.key === 'ArrowRight') { setStep(S.cur + 1); e.preventDefault(); }
      else if (e.key === ' ') { $('btn-play').click(); e.preventDefault(); }
      else if (e.key === 'Home') { setStep(0); e.preventDefault(); }
      else if (e.key === 'End') { setStep(S.steps.length - 1); e.preventDefault(); }
    });
  }

  function bootPlayer(data) {
    if (rafHandle !== null) cancelAnimationFrame(rafHandle);
    const canvas = $('stage');
    const dpr = window.devicePixelRatio || 1;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.aspectRatio = W + ' / ' + H;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    S.DATA = data;
    S.devices = data.chain.devices;
    S.links = data.chain.links;
    S.steps = data.steps;
    S.cur = 0;
    S.playing = false;
    S.speed = parseFloat(($('speed') && $('speed').value) || '1');
    S.enterTime = performance.now();
    S.packets = [];
    S.ctx = ctx;

    S.pos = {};
    const N = S.devices.length;
    S.devices.forEach((d, i) => {
      S.pos[d.id] = { x: 90 + i * (W - 180) / (N - 1), y: DEV_Y };
    });

    // PDU 色块图例只对 encap 主题有意义
    const legend = document.querySelector('div.legend.pdu-legend');
    if (legend) legend.style.display =
      data.topic === 'troubleshoot' ? 'none' : '';

    bindControls();
    bindStacks();
    $('title').textContent = data.title;
    $('subtitle').textContent = data.subtitle;
    buildConceptModal();
    S.ready = true;
    setStep(0);
    rafHandle = requestAnimationFrame(draw);
  }

  window.bootPlayer = bootPlayer;
  // Headless test/debug hook (same convention as the STP visualizer).
  window.PLAYER = { setStep: i => setStep(i) };
  if (window.PLAYER_DATA) bootPlayer(window.PLAYER_DATA);
})();
