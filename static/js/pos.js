/* ── State ──────────────────────────────────────────────────────────────────── */
let cart = [];
let currentCat = 'الكل';
let currentProducts = [];
let lastAddedId = null;
let scannerBuffer = '';
let scannerTimer = null;
let suggestIndex = -1;

const CART_KEY = 'hookshop_cart';
const HELD_KEY = 'hookshop_held_carts';

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[ch]));
}

function money(value) {
  return Number(value || 0).toFixed(2) + ' ج';
}

function stripScannerPrefix(code) {
  // Remove standard AIM scanner ID prefixes (e.g. ]C0, ]E0, ]Q3)
  return code.replace(/^\][A-Za-z0-9]{1,3}/, '');
}

let _beepCtx = null;
function beep(type = 'success') {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    if (!_beepCtx) _beepCtx = new AudioCtx();
    if (_beepCtx.state === 'suspended') _beepCtx.resume();
    const osc = _beepCtx.createOscillator();
    const gain = _beepCtx.createGain();
    osc.frequency.value = type === 'error' ? 180 : 720;
    gain.gain.value = 0.035;
    osc.connect(gain);
    gain.connect(_beepCtx.destination);
    osc.start();
    setTimeout(() => {
      try { osc.stop(); } catch {}
    }, type === 'error' ? 160 : 90);
  } catch {}
}

function saveCart() {
  localStorage.setItem(CART_KEY, JSON.stringify({
    cart,
    discount: document.getElementById('discount')?.value || 0,
    discount_type: document.getElementById('discount-type')?.value || 'amount',
    payment: document.getElementById('payment-method')?.value || 'كاش'
  }));
}

function restoreCart() {
  try {
    const saved = JSON.parse(localStorage.getItem(CART_KEY) || '{}');
    if (Array.isArray(saved.cart)) cart = saved.cart;
    if (saved.discount != null) document.getElementById('discount').value = saved.discount;
    if (saved.discount_type) document.getElementById('discount-type').value = saved.discount_type;
    if (saved.payment) setPayment(saved.payment);
  } catch {
    cart = [];
  }
}

function clearSavedCart() {
  localStorage.removeItem(CART_KEY);
}

/* ── Silent print ───────────────────────────────────────────────────────────── */
function printReceipt(saleId) {
  const popup = window.open(
    `/receipt/${saleId}?print=1`,
    'receipt_print',
    'width=420,height=620,top=-3000,left=-3000,menubar=no,toolbar=no,location=no,status=no'
  );
  if (!popup) window.open(`/receipt/${saleId}`, '_blank');
}

/* ── Keyboard / scanner ─────────────────────────────────────────────────────── */
document.addEventListener('keydown', function (e) {
  const tag = e.target.tagName.toLowerCase();
  const scanInput = document.getElementById('scan-input');

  if (e.key === 'F2') {
    e.preventDefault();
    scanInput?.focus();
    return;
  }
  if (e.key === 'F4') {
    e.preventDefault();
    scanInput?.focus();
    scanInput?.select();
    return;
  }
  if (e.key === 'F8') {
    e.preventDefault();
    openLastReceipt();
    return;
  }
  if (e.key === 'F9') {
    e.preventDefault();
    checkout();
    return;
  }
  if (e.key === 'Escape' && tag !== 'input' && tag !== 'select') {
    clearCart();
    return;
  }
  if ((e.key === '+' || e.key === '=') && tag !== 'input' && lastAddedId) {
    e.preventDefault();
    changeQty(lastAddedId, 1);
    return;
  }
  if (e.key === '-' && tag !== 'input' && lastAddedId) {
    e.preventDefault();
    changeQty(lastAddedId, -1);
    return;
  }

  if (tag === 'select') return;
  if (tag === 'input' && e.target.id !== 'scan-input') return;

  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    if (moveSuggestion(e.key === 'ArrowDown' ? 1 : -1)) e.preventDefault();
    return;
  }

  if (e.key === 'Enter') {
    const picked = pickSuggestion();
    if (picked) {
      e.preventDefault();
      return;
    }
    const inputVal = scanInput?.value?.trim() || '';
    const raw = scannerBuffer.trim().length >= inputVal.length
      ? scannerBuffer.trim() : inputVal;
    const code = stripScannerPrefix(raw);
    if (code) {
      if (/^\*\d+$/.test(code)) {
        multiplyLast(Number(code.slice(1)));
      } else {
        scanProduct(code);
      }
      if (scanInput) scanInput.value = '';
      hideSuggestions();
    }
    scannerBuffer = '';
    clearTimeout(scannerTimer);
    e.preventDefault();
    return;
  }

  if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
    if (document.activeElement !== scanInput) scanInput?.focus();
    scannerBuffer += e.key;
    clearTimeout(scannerTimer);
    const stripped = stripScannerPrefix(scannerBuffer);
    if (/^[A-Za-z0-9\-\.\+\*\/\_]{4,}$/.test(stripped)) {
      scannerTimer = setTimeout(() => {
        const code = stripScannerPrefix(scannerBuffer.trim());
        if (code && /^[A-Za-z0-9\-\.\+\*\/\_]{4,}$/.test(code)) {
          scanInput.value = '';
          scanProduct(code);
          scannerBuffer = '';
        }
      }, 300);
    } else {
      scannerTimer = setTimeout(() => { scannerBuffer = ''; }, 600);
    }
  }
});

document.addEventListener('click', function (e) {
  const tag = e.target.tagName.toLowerCase();
  if (!e.target.closest('#suggestions')) hideSuggestions();
  if (e.target.closest('.prod-card')) return;
  if (tag !== 'button' && tag !== 'input' && tag !== 'select' && tag !== 'a') {
    document.getElementById('scan-input')?.focus();
  }
});

document.getElementById('scan-input')?.addEventListener('input', debounce(function (e) {
  const q = e.target.value.trim();
  if (q.length < 2) {
    hideSuggestions();
    return;
  }
  loadSuggestions(q);
}, 160));

function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/* ── Product grid / suggestions ─────────────────────────────────────────────── */
async function loadProducts(cat) {
  const url = (cat && cat !== 'الكل')
    ? `/api/products/search?category=${encodeURIComponent(cat)}`
    : '/api/products/search';
  const res = await fetch(url);
  currentProducts = await res.json();
  renderGrid(currentProducts);
}

async function loadSuggestions(q) {
  const res = await fetch(`/api/products/search?q=${encodeURIComponent(q)}`);
  const list = (await res.json()).slice(0, 8);
  const box = document.getElementById('suggestions');
  suggestIndex = -1;
  if (!box || !list.length) {
    hideSuggestions();
    return;
  }
  box.innerHTML = list.map((p, idx) => `
    <div class="suggestion-item" data-idx="${idx}" onclick="addSuggestion(${p.id})">
      <span>${escapeHtml(p.name)}</span>
      <span class="suggestion-meta">${money(p.price)} | ${p.quantity > 0 ? 'متاح: ' + p.quantity : 'نفذ'}</span>
    </div>
  `).join('');
  box.dataset.products = JSON.stringify(list);
  box.style.display = 'block';
}

function hideSuggestions() {
  const box = document.getElementById('suggestions');
  if (box) box.style.display = 'none';
  suggestIndex = -1;
}

function moveSuggestion(delta) {
  const box = document.getElementById('suggestions');
  if (!box || box.style.display !== 'block') return false;
  const items = [...box.querySelectorAll('.suggestion-item')];
  if (!items.length) return false;
  suggestIndex = (suggestIndex + delta + items.length) % items.length;
  items.forEach((item, idx) => item.classList.toggle('active', idx === suggestIndex));
  return true;
}

function pickSuggestion() {
  const box = document.getElementById('suggestions');
  if (!box || box.style.display !== 'block' || suggestIndex < 0) return false;
  const products = JSON.parse(box.dataset.products || '[]');
  const product = products[suggestIndex];
  if (!product) return false;
  addToCart(product);
  document.getElementById('scan-input').value = '';
  hideSuggestions();
  return true;
}

function addSuggestion(id) {
  addById(id);
  document.getElementById('scan-input').value = '';
  hideSuggestions();
}

function renderGrid(products) {
  const grid = document.getElementById('product-grid');
  if (!grid) return;
  if (!products.length) {
    grid.innerHTML = '<div class="text-center text-muted py-4 w-100" style="font-size:1.1rem">لا توجد منتجات</div>';
    return;
  }
  const wrap = document.querySelector('.pos-wrap');
  grid.innerHTML = products.map(p => {
    const stockClass = p.quantity <= 0 ? 'out-stock' : (p.quantity <= Number(wrap?.dataset.lowStock || 5) ? 'low-stock' : '');
    const qty = p.quantity > 0 ? 'متبقي: ' + p.quantity : '<span style="color:#ef4444">نفذ</span>';
    return `
      <div class="prod-card ${stockClass}" onclick="addById(${p.id})" data-pid="${p.id}"
           title="${escapeHtml(`${p.size ? 'مقاس: ' + p.size : ''} ${p.color ? '| لون: ' + p.color : ''}`)}">
        <div class="p-name">${escapeHtml(p.name)}</div>
        <div class="p-price">${money(p.price)}</div>
        <div class="p-qty">${qty}</div>
      </div>
    `;
  }).join('');
}

function filterCat(el, cat) {
  currentCat = cat;
  document.querySelectorAll('.cat-pill').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  loadProducts(cat);
}

async function scanProduct(code) {
  const res = await fetch(`/api/product/${encodeURIComponent(code)}`);
  const data = await res.json();

  if (data.success) {
    addToCart(data.product);
    toast(`تمت الإضافة: ${data.product.name}`, 'success');
    beep('success');
  } else {
    const res2 = await fetch(`/api/products/search?q=${encodeURIComponent(code)}`);
    const list = await res2.json();
    if (list.length === 1) {
      addToCart(list[0]);
      toast(`تمت الإضافة: ${list[0].name}`, 'success');
      beep('success');
    } else if (list.length > 1) {
      renderGrid(list);
      toast('اختر المنتج من القائمة', 'info');
    } else {
      toast(data.error || 'المنتج غير موجود', 'error');
      beep('error');
      openQuickAdd(code);
    }
  }
  document.getElementById('scan-input')?.focus();
}

async function addById(id) {
  const res = await fetch(`/api/product/${id}`);
  const data = await res.json();
  if (data.success) {
    addToCart(data.product);
    toast(`تمت الإضافة: ${data.product.name}`, 'success');
    beep('success');
  } else {
    toast(data.error, 'error');
    beep('error');
    offerStockUpdate(id, data.error);
  }
}

/* ── Flash animation on product card ──────────────────────────────────────── */
function flashProductCard(productId) {
  const card = document.querySelector(`.prod-card[data-pid="${productId}"]`);
  if (!card) return;
  card.classList.remove('flash');
  void card.offsetWidth; // force reflow
  card.classList.add('flash');
  setTimeout(() => card.classList.remove('flash'), 400);
}

/* ── Cart ───────────────────────────────────────────────────────────────────── */
function availableQty(product) {
  const fromGrid = currentProducts.find(p => p.id === product.id);
  return Number((fromGrid || product).quantity || 0);
}

function addToCart(product) {
  const maxQty = availableQty(product);
  if (maxQty <= 0) {
    toast(`المنتج "${product.name}" نفذ من المخزون`, 'error');
    offerStockUpdate(product.id);
    return;
  }

  const existing = cart.find(i => i.id === product.id);
  if (existing) {
    if (existing.quantity >= existing.available) {
      toast(`المتاح من "${existing.name}" هو ${existing.available} فقط`, 'error');
      beep('error');
      return;
    }
    existing.quantity++;
  } else {
    cart.push({
      id: product.id,
      name: product.name,
      price: Number(product.price || 0),
      cost_price: Number(product.cost_price || 0),
      quantity: 1,
      available: maxQty
    });
  }
  lastAddedId = product.id;
  flashProductCard(product.id);
  renderCart();
  saveCart();
}

function removeFromCart(id) {
  cart = cart.filter(i => i.id !== id);
  renderCart();
  saveCart();
}

function changeQty(id, delta) {
  const item = cart.find(i => i.id === id);
  if (!item) return;
  const next = item.quantity + delta;
  if (next <= 0) {
    removeFromCart(id);
    return;
  }
  if (next > item.available) {
    toast(`المتاح من "${item.name}" هو ${item.available} فقط`, 'error');
    beep('error');
    return;
  }
  item.quantity = next;
  lastAddedId = id;
  renderCart();
  saveCart();
}

function multiplyLast(qty) {
  if (!lastAddedId || qty <= 0) return;
  const item = cart.find(i => i.id === lastAddedId);
  if (!item) return;
  if (qty > item.available) {
    toast(`المتاح من "${item.name}" هو ${item.available} فقط`, 'error');
    return;
  }
  item.quantity = qty;
  renderCart();
  saveCart();
}

function renderCart() {
  const body = document.getElementById('cart-body');
  const countEl = document.getElementById('cart-count');
  const totalEl = document.getElementById('total');
  const finalEl = document.getElementById('final-total');
  if (!body) return;

  const total = cart.reduce((s, i) => s + i.price * i.quantity, 0);
  const discountType = document.getElementById('discount-type')?.value || 'amount';
  const discountValue = Math.max(0, parseFloat(document.getElementById('discount')?.value || 0));
  const discount = discountType === 'percent' ? total * Math.min(discountValue, 100) / 100 : discountValue;
  const wrap = document.querySelector('.pos-wrap');
  const servicePercent = Number(wrap?.dataset.service || 0);
  const taxPercent = Number(wrap?.dataset.tax || 0);
  const afterDiscount = Math.max(0, total - discount);
  const service = afterDiscount * servicePercent / 100;
  const tax = afterDiscount * taxPercent / 100;
  const finalTotal = Math.max(0, afterDiscount + service + tax);

  if (countEl) countEl.textContent = cart.reduce((s, i) => s + i.quantity, 0);
  if (totalEl) totalEl.textContent = money(total);
  const serviceEl = document.getElementById('service-total');
  if (serviceEl) serviceEl.textContent = money(service);
  const serviceRow = document.getElementById('service-row');
  if (serviceRow) serviceRow.classList.toggle('d-none', service === 0);
  const taxEl = document.getElementById('tax-total');
  if (taxEl) taxEl.textContent = money(tax);
  const taxRow = document.getElementById('tax-row');
  if (taxRow) taxRow.classList.toggle('d-none', tax === 0);
  if (finalEl) finalEl.textContent = money(finalTotal);
  saveCart();

  if (cart.length === 0) {
    body.innerHTML = `
      <div class="text-center text-muted py-5">
        <i class="bi bi-cart3 empty-cart-icon"></i>
        <p class="empty-cart-text">السلة فارغة</p>
      </div>`;
    const holdBtn = document.getElementById('hold-btn');
    if (holdBtn) holdBtn.disabled = true;
    saveCart();
    return;
  }
  const holdBtn = document.getElementById('hold-btn');
  if (holdBtn) holdBtn.disabled = false;

  body.innerHTML = cart.map(item => `
    <div class="cart-item">
      <div style="flex:1">
        <div class="cart-item-name">${escapeHtml(item.name)}</div>
        <div style="font-size:.75rem;color:#94a3b8">${money(item.price)} × ${item.quantity} | متاح ${item.available}</div>
      </div>
      <div style="display:flex;align-items:center;gap:6px">
        <button class="qty-btn" onclick="changeQty(${item.id},-1)">-</button>
        <span style="font-weight:700;min-width:18px;text-align:center;font-size:.8rem">${item.quantity}</span>
        <button class="qty-btn" onclick="changeQty(${item.id},1)">+</button>
        <span class="cart-item-price">${money(item.price * item.quantity)}</span>
        <button class="del-btn" onclick="removeFromCart(${item.id})"><i class="bi bi-trash"></i></button>
      </div>
    </div>
  `).join('');
}

/* ── Checkout / payment ─────────────────────────────────────────────────────── */
function setPayment(method) {
  const select = document.getElementById('payment-method');
  if (select) select.value = method;
  document.querySelectorAll('.pay-method').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.method === method);
  });
  saveCart();
}

document.getElementById('pay-methods')?.addEventListener('click', e => {
  const btn = e.target.closest('.pay-method');
  if (btn) setPayment(btn.dataset.method);
});

async function checkout() {
  if (cart.length === 0) {
    toast('السلة فارغة', 'error');
    return;
  }

  const total = cart.reduce((s, i) => s + i.price * i.quantity, 0);
  const discountType = document.getElementById('discount-type')?.value || 'amount';
  const discountValue = Math.max(0, parseFloat(document.getElementById('discount')?.value || 0));
  const discount = discountType === 'percent' ? total * Math.min(discountValue, 100) / 100 : discountValue;
  if (discount > total * 0.5 && !confirm('الخصم أكبر من نصف الفاتورة. هل تريد المتابعة؟')) return;
  if (discount > 0 && total > 0) {
    const lossItems = cart.filter(item => {
      if (item.cost_price <= 0) return false;
      const itemTotal = item.price * item.quantity;
      const itemShare = discount * itemTotal / total;
      return (item.price - itemShare / item.quantity) < item.cost_price;
    });
    if (lossItems.length > 0) {
      const names = lossItems.map(i => `"${i.name}"`).join('، ');
      if (!confirm(`الخصم كبير جداً! المنتجات ${names} هتكون أقل من سعر التكلفة وهنخسر فيها.\nهل تريد المتابعة؟`)) return;
    }
  }

  const wrap = document.querySelector('.pos-wrap');
  const servicePercent = Number(wrap?.dataset.service || 0);
  const taxPercent = Number(wrap?.dataset.tax || 0);
  const afterDiscount = Math.max(0, total - discount);
  const service = afterDiscount * servicePercent / 100;
  const tax = afterDiscount * taxPercent / 100;
  const finalTotal = Math.max(0, afterDiscount + service + tax);
  const paymentMethod = document.getElementById('payment-method')?.value || 'كاش';
  const btn = document.getElementById('pay-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>جاري المعالجة...';

  try {
    const res = await fetch('/api/sale/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items: cart.map(i => ({
          product_id: i.id,
          product_name: i.name,
          quantity: i.quantity,
          unit_price: i.price,
          cost_price: i.cost_price,
          total_price: i.price * i.quantity
        })),
        total,
        discount,
        final_total: finalTotal,
        payment_method: paymentMethod,
        notes: document.getElementById('sale-notes')?.value || '',
        customer_id: document.getElementById('customer-id')?.value || null,
        paid_amount: null,
        tax,
        service,
        discount_type: discountType,
        discount_value: discountValue
      })
    });
    const data = await res.json();

    if (data.success) {
      if (data.printer_configured) {
        toast('تم البيع — جاري الطباعة...', 'success');
      } else {
        printReceipt(data.sale_id);
        toast('تم البيع بنجاح ✓', 'success');
      }
      cart = [];
      lastAddedId = null;
      document.getElementById('discount').value = '';
      const sn = document.getElementById('sale-notes'); if (sn) sn.value = '';
      const ci = document.getElementById('customer-id'); if (ci) ci.value = '';
      clearSavedCart();
      renderCart();
      loadProducts(currentCat);
      beep('success');
    } else {
      toast(data.error || 'حدث خطأ', 'error');
      beep('error');
    }
  } catch {
    toast('خطأ في الاتصال', 'error');
    beep('error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-check2-circle me-2"></i>إتمام البيع';
    document.getElementById('scan-input')?.focus();
  }
}

function clearCart() {
  if (cart.length && !confirm('هل تريد مسح السلة؟')) {
    document.getElementById('scan-input')?.focus();
    return;
  }
  cart = [];
  lastAddedId = null;
  document.getElementById('discount').value = '';
  const sn = document.getElementById('sale-notes'); if (sn) sn.value = '';
  clearSavedCart();
  renderCart();
  document.getElementById('scan-input')?.focus();
}

/* ── Held carts ─────────────────────────────────────────────────────────────── */
function getHeldCarts() {
  try {
    return JSON.parse(localStorage.getItem(HELD_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveHeldCarts(list) {
  localStorage.setItem(HELD_KEY, JSON.stringify(list));
}

function holdCart() {
  if (!cart.length) {
    toast('لا توجد سلة لتعليقها', 'error');
    return;
  }
  const name = prompt('اسم الفاتورة المعلقة:', `عميل ${new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}`);
  if (!name) return;
  const list = getHeldCarts();
  list.unshift({
    id: Date.now(),
    name,
    cart,
    discount: document.getElementById('discount').value || 0,
    discountType: document.getElementById('discount-type')?.value || 'amount',
    payment: document.querySelector('#pay-methods .pay-method.active')?.dataset?.method || 'كاش',
    created_at: new Date().toLocaleString('ar-EG')
  });
  saveHeldCarts(list.slice(0, 20));
  cart = [];
  document.getElementById('discount').value = '';
  clearSavedCart();
  renderCart();
  toast('تم تعليق الفاتورة', 'success');
}

function showHeldCarts() {
  const list = getHeldCarts();
  const body = document.getElementById('held-list');
  if (!body) return;
  if (!list.length) {
    body.innerHTML = '<div class="text-center text-muted py-3">لا توجد فواتير معلقة</div>';
  } else {
    body.innerHTML = list.map(item => {
      const total = item.cart.reduce((s, i) => s + i.price * i.quantity, 0);
      return `
        <div class="held-item">
          <div>
            <div class="fw-bold">${escapeHtml(item.name)}</div>
            <div class="text-muted small">${escapeHtml(item.created_at)} | ${item.cart.length} منتجات | ${money(total)}</div>
          </div>
          <div class="d-flex gap-1">
            <button class="btn btn-success" style="padding:8px 16px;font-size:.95rem" onclick="restoreHeldCart(${item.id})">فتح</button>
            <button class="btn btn-outline-danger" style="padding:8px 16px;font-size:.95rem" onclick="deleteHeldCart(${item.id})">حذف</button>
          </div>
        </div>`;
    }).join('');
  }
  new bootstrap.Modal(document.getElementById('heldModal')).show();
}

function restoreHeldCart(id) {
  const list = getHeldCarts();
  const item = list.find(x => x.id === id);
  if (!item) return;
  if (cart.length && !confirm('السلة الحالية سيتم استبدالها. متابعة؟')) return;
  cart = item.cart;
  document.getElementById('discount').value = item.discount || '';
  const dtEl = document.getElementById('discount-type');
  if (dtEl) dtEl.value = item.discountType || 'amount';
  setPayment(item.payment || 'كاش');
  saveHeldCarts(list.filter(x => x.id !== id));
  renderCart();
  document.querySelector('#heldModal .btn-close')?.click();
}

function deleteHeldCart(id) {
  saveHeldCarts(getHeldCarts().filter(x => x.id !== id));
  showHeldCarts();
}

/* ── Quick add / stock update / reports ─────────────────────────────────────── */
function openQuickAdd(prefill = '') {
  document.getElementById('qa-name').value = '';
  document.getElementById('qa-price').value = '';
  document.getElementById('qa-cost').value = '';
  document.getElementById('qa-qty').value = 1;
  document.getElementById('qa-barcode').value = /^\d+$/.test(prefill) ? prefill : '';
  if (prefill && !/^\d+$/.test(prefill)) document.getElementById('qa-name').value = prefill;
  new bootstrap.Modal(document.getElementById('quickAddModal')).show();
  setTimeout(() => document.getElementById('qa-name')?.focus(), 100);
}

async function quickAddProduct() {
  const payload = {
    name: document.getElementById('qa-name').value.trim(),
    price: document.getElementById('qa-price').value || 0,
    cost_price: document.getElementById('qa-cost').value || 0,
    quantity: document.getElementById('qa-qty').value || 0,
    barcode: document.getElementById('qa-barcode').value.trim()
  };
  if (!payload.name || Number(payload.price) <= 0) {
    toast('اكتب اسم المنتج وسعر البيع', 'error');
    return;
  }
  const res = await fetch('/api/products/quick-add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (data.success) {
    document.querySelector('#quickAddModal .btn-close')?.click();
    await loadProducts(currentCat);
    addToCart(data.product);
    toast('تم إضافة المنتج', 'success');
  } else {
    toast(data.error || 'تعذر إضافة المنتج', 'error');
  }
}

function offerStockUpdate(id, message = '') {
  if (!id || !confirm((message ? message + '\n' : '') + 'هل تريد تعديل كمية المنتج الآن؟')) return;
  const qty = prompt('اكتب الكمية الجديدة:');
  if (qty == null) return;
  updateStock(id, qty);
}

async function updateStock(id, qty) {
  const res = await fetch(`/api/product/${id}/quantity`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quantity: qty })
  });
  const data = await res.json();
  if (data.success) {
    toast('تم تحديث الكمية', 'success');
    loadProducts(currentCat);
  } else {
    toast(data.error || 'تعذر تحديث الكمية', 'error');
  }
}

async function openLastReceipt() {
  const res = await fetch('/api/sale/last');
  const data = await res.json();
  if (data.success) window.open(`/receipt/${data.sale.id}`, '_blank');
  else toast(data.error || 'لا توجد فواتير', 'error');
}

async function showDaySummary() {
  const res = await fetch('/api/day-summary');
  const data = await res.json();
  if (!data.success) return;
  const stats = data.stats;
  const payments = data.payments.map(p => `
    <div class="d-flex justify-content-between border-bottom py-1">
      <span>${escapeHtml(p.payment_method)} (${p.count})</span>
      <strong>${money(p.total)}</strong>
    </div>`).join('') || '<div class="text-muted">لا توجد مدفوعات</div>';
  document.getElementById('day-summary-body').innerHTML = `
    <div class="row g-2 mb-3">
      <div class="col-6"><div class="border rounded p-2"><div class="text-muted small">الإيراد</div><strong>${money(stats.revenue)}</strong></div></div>
      <div class="col-6"><div class="border rounded p-2"><div class="text-muted small">الربح</div><strong>${money(stats.profit)}</strong></div></div>
      <div class="col-6"><div class="border rounded p-2"><div class="text-muted small">الفواتير</div><strong>${stats.count}</strong></div></div>
      <div class="col-6"><div class="border rounded p-2"><div class="text-muted small">الخصومات</div><strong>${money(stats.discount)}</strong></div></div>
    </div>
    <h6 class="fw-bold">طرق الدفع</h6>
    ${payments}`;
  new bootstrap.Modal(document.getElementById('daySummaryModal')).show();
}

/* ── Toast ──────────────────────────────────────────────────────────────────── */
function toast(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = `pos-toast pos-toast-${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('show')));
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 350);
  }, 2500);
}

/* ── Init ───────────────────────────────────────────────────────────────────── */
restoreCart();
loadProducts('');
renderCart();
document.getElementById('discount')?.addEventListener('input', saveCart);
document.getElementById('discount-type')?.addEventListener('change', saveCart);
setPayment('كاش');
document.getElementById('scan-input')?.focus();

function toggleTouchMode() {
  document.body.classList.toggle('touch-mode');
  localStorage.setItem('hookshop_touch_mode', document.body.classList.contains('touch-mode') ? '1' : '0');
}

if (localStorage.getItem('hookshop_touch_mode') === '1') {
  document.body.classList.add('touch-mode');
}

document.addEventListener('hidden.bs.modal', function () {
  setTimeout(() => document.getElementById('scan-input')?.focus(), 100);
});
