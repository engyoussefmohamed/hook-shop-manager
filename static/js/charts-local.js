function setupCanvas(canvas) {
  if (!canvas) return null;
  const parent = canvas.parentElement;
  const width = Math.max(parent ? parent.clientWidth : 600, 280);
  const height = Math.max(parseInt(canvas.getAttribute('height') || '180', 10), 160);
  const ratio = window.devicePixelRatio || 1;
  canvas.style.width = '100%';
  canvas.style.height = `${height}px`;
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { ctx, width, height };
}

function moneyLabel(value) {
  const num = Number(value || 0);
  if (num >= 1000) return `${Math.round(num / 1000)}k`;
  return num.toFixed(0);
}

function drawAxes(ctx, width, height, maxValue) {
  const pad = { top: 16, right: 16, bottom: 34, left: 44 };
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = '#e2e8f0';
  ctx.fillStyle = '#64748b';
  ctx.lineWidth = 1;
  ctx.font = '12px system-ui, sans-serif';

  for (let i = 0; i <= 4; i++) {
    const y = pad.top + ((height - pad.top - pad.bottom) * i / 4);
    const value = maxValue - (maxValue * i / 4);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    ctx.fillText(moneyLabel(value), 4, y + 4);
  }
  return pad;
}

function drawEmpty(ctx, width, height) {
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#94a3b8';
  ctx.font = '14px system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('لا توجد بيانات كافية للرسم', width / 2, height / 2);
  ctx.textAlign = 'start';
}

function drawBarChart(canvas, options) {
  const box = setupCanvas(canvas);
  if (!box) return;
  const { ctx, width, height } = box;
  const labels = options.labels || [];
  const values = (options.values || []).map(Number);
  const maxValue = Math.max(...values, 0);
  if (!values.length || maxValue <= 0) return drawEmpty(ctx, width, height);

  const pad = drawAxes(ctx, width, height, maxValue);
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const gap = 10;
  const barW = Math.max(12, (plotW - gap * (values.length - 1)) / values.length);

  values.forEach((value, i) => {
    const x = pad.left + i * (barW + gap);
    const h = (value / maxValue) * plotH;
    const y = pad.top + plotH - h;
    ctx.fillStyle = options.color || '#22c55e';
    ctx.globalAlpha = 0.25;
    ctx.fillRect(x, y, barW, h);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = options.color || '#22c55e';
    ctx.strokeRect(x, y, barW, h);
    ctx.fillStyle = '#64748b';
    ctx.font = '11px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(String(labels[i] || ''), x + barW / 2, height - 10);
  });
  ctx.textAlign = 'start';
}

function drawLineChart(canvas, options) {
  const box = setupCanvas(canvas);
  if (!box) return;
  const { ctx, width, height } = box;
  const labels = options.labels || [];
  const values = (options.values || []).map(Number);
  const maxValue = Math.max(...values, 0);
  if (!values.length || maxValue <= 0) return drawEmpty(ctx, width, height);

  const pad = drawAxes(ctx, width, height, maxValue);
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const step = values.length > 1 ? plotW / (values.length - 1) : plotW;
  const points = values.map((value, i) => ({
    x: pad.left + step * i,
    y: pad.top + plotH - ((value / maxValue) * plotH)
  }));

  ctx.beginPath();
  points.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y));
  ctx.strokeStyle = options.color || '#22c55e';
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.lineTo(pad.left + plotW, pad.top + plotH);
  ctx.lineTo(pad.left, pad.top + plotH);
  ctx.closePath();
  ctx.fillStyle = options.color || '#22c55e';
  ctx.globalAlpha = 0.12;
  ctx.fill();
  ctx.globalAlpha = 1;

  points.forEach((p, i) => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
    ctx.fillStyle = options.color || '#22c55e';
    ctx.fill();
    if (i % Math.ceil(values.length / 6 || 1) === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '11px system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(String(labels[i] || '').slice(5), p.x, height - 10);
    }
  });
  ctx.textAlign = 'start';
}
