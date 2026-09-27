/* ── Returns & Exchange Page ────────────────────────────────────────────────── */

function escapeR(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function moneyR(value) {
  return Number(value || 0).toFixed(2) + ' ج';
}

function toastR(msg, type = 'success') {
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

function showLoading(el) {
  if (el) el.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>';
}

/* ── Return History (AJAX + Pagination) ───────────────────────────────────── */
let historyPage = 1;
let historySearch = '';
let historyDateFrom = '';
let historyDateTo = '';

async function loadReturnHistory(page = 1) {
  historyPage = page;
  const container = document.getElementById('return-history-body');
  if (!container) return;
  showLoading(container);

  const params = new URLSearchParams({ page, per_page: 15 });
  if (historySearch) params.set('search', historySearch);
  if (historyDateFrom) params.set('date_from', historyDateFrom);
  if (historyDateTo) params.set('date_to', historyDateTo);

  try {
    const res = await fetch(`/api/returns/history?${params}`);
    const data = await res.json();
    if (!data.success) {
      container.innerHTML = '<div class="text-center text-muted py-4">خطأ في التحميل</div>';
      return;
    }
    renderReturnHistory(data);
    renderHistoryPagination(data);
  } catch {
    container.innerHTML = '<div class="text-center text-muted py-4">خطأ في الاتصال</div>';
  }
}

function renderReturnHistory(data) {
  const container = document.getElementById('return-history-body');
  if (!container) return;
  if (!data.returns || !data.returns.length) {
    container.innerHTML = '<div class="text-center text-muted py-4"><i class="bi bi-inbox" style="font-size:2rem"></i><p class="mt-2">لا توجد عمليات مرتجعات</p></div>';
    return;
  }
  container.innerHTML = data.returns.map(r => `
    <div class="return-row" data-id="${r.id}">
      <div class="return-row-top">
        <div class="return-row-info">
          <span class="badge ${r.return_type === 'exchange' ? 'bg-primary' : 'bg-warning text-dark'}" style="font-size:.85rem">
            ${r.return_type === 'exchange' ? 'استبدال' : 'مرتجع'}
          </span>
          <strong class="return-row-product">${escapeR(r.product_name)}</strong>
          <span class="text-muted">×${r.quantity}</span>
        </div>
        <div class="return-row-right">
          <span class="return-row-amount">${moneyR(r.amount)}</span>
          ${HOOK_IS_ADMIN ? `
            <button class="btn btn-sm btn-outline-secondary return-undo-btn" onclick="undoReturn(${r.id})" title="تراجع">
              <i class="bi bi-arrow-counterclockwise"></i>
            </button>
          ` : ''}
        </div>
      </div>
      <div class="return-row-bottom">
        <a href="/returns?sale_id=${r.sale_id}" class="text-decoration-none">فاتورة #${r.sale_id}</a>
        <span class="text-muted">${r.created_at || ''}</span>
        ${r.notes ? `<span class="text-muted">— ${escapeR(r.notes)}</span>` : ''}
      </div>
    </div>
  `).join('');
}

function renderHistoryPagination(data) {
  const nav = document.getElementById('history-pagination');
  if (!nav) return;
  if (data.total_pages <= 1) { nav.innerHTML = ''; return; }
  let html = '<div class="d-flex justify-content-center align-items-center gap-2">';
  html += `<button class="btn btn-sm btn-outline-primary" ${data.page <= 1 ? 'disabled' : ''} onclick="loadReturnHistory(${data.page - 1})"><i class="bi bi-chevron-right"></i></button>`;
  html += `<span class="text-muted">صفحة ${data.page} / ${data.total_pages}</span>`;
  html += `<button class="btn btn-sm btn-outline-primary" ${data.page >= data.total_pages ? 'disabled' : ''} onclick="loadReturnHistory(${data.page + 1})"><i class="bi bi-chevron-left"></i></button>`;
  html += '</div>';
  nav.innerHTML = html;
}

function searchHistory() {
  historySearch = document.getElementById('history-search')?.value?.trim() || '';
  historyDateFrom = document.getElementById('history-date-from')?.value || '';
  historyDateTo = document.getElementById('history-date-to')?.value || '';
  loadReturnHistory(1);
}

/* ── Undo Return ──────────────────────────────────────────────────────────── */
async function undoReturn(returnId) {
  if (!confirm('هل تريد التراجع عن عملية المرتجع هذه؟')) return;
  try {
    const res = await fetch('/api/returns/undo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ return_id: returnId })
    });
    const data = await res.json();
    toastR(data.message || data.error, data.success ? 'success' : 'error');
    if (data.success) {
      loadReturnHistory(historyPage);
      const saleId = document.getElementById('sale-id-input')?.value;
      if (saleId) loadSale(saleId);
    }
  } catch {
    toastR('خطأ في الاتصال', 'error');
  }
}

/* ── Sale Lookup ──────────────────────────────────────────────────────────── */
async function loadSale(saleId) {
  if (!saleId) return;
  const container = document.getElementById('sale-details');
  if (!container) return;
  showLoading(container);

  try {
    const res = await fetch(`/api/returns/sale/${encodeURIComponent(saleId)}`);
    const data = await res.json();
    if (!data.success) {
      container.innerHTML = `<div class="empty-state"><i class="bi bi-exclamation-circle"></i><p>${escapeR(data.error)}</p></div>`;
      return;
    }
    renderSaleDetails(data.sale);
  } catch {
    container.innerHTML = '<div class="empty-state"><i class="bi bi-wifi-off"></i><p>خطأ في الاتصال</p></div>';
  }
}

function renderSaleDetails(sale) {
  const container = document.getElementById('sale-details');
  if (!container) return;

  const totalReturned = sale.total_returned_amount || 0;
  const totalOriginal = sale.total_original_amount || 0;
  const remaining = sale.remaining_amount_calc || 0;
  const allReturned = sale.items.every(i => i.available_to_return <= 0);

  let html = '';

  /* Summary card */
  html += `
    <div class="sale-summary">
      <div class="sale-summary-header">
        <div>
          <h5><i class="bi bi-receipt me-2"></i>فاتورة #${sale.id}</h5>
          <span class="text-muted">${sale.created_at || ''}</span>
        </div>
        <div class="sale-summary-actions">
          ${!allReturned ? `
            <button class="btn btn-md btn-warning" onclick="returnAll(${sale.id})">
              <i class="bi bi-arrow-return-left me-1"></i>إرجاع الكل
            </button>
          ` : ''}
          ${HOOK_IS_ADMIN ? (
            !sale.voided ? `
              <button class="btn btn-md btn-outline-danger" onclick="voidSale(${sale.id})">
                <i class="bi bi-x-circle me-1"></i>إلغاء الفاتورة
              </button>
            ` : '<span class="badge bg-danger" style="font-size:.9rem;padding:8px 14px">ملغاة</span>'
          ) : (sale.voided ? '<span class="badge bg-danger" style="font-size:.9rem;padding:8px 14px">ملغاة</span>' : '')}
        </div>
      </div>
      <div class="sale-summary-stats">
        <div class="sale-stat">
          <span class="sale-stat-label">المبيعات</span>
          <span class="sale-stat-value">${moneyR(totalOriginal)}</span>
        </div>
        <div class="sale-stat">
          <span class="sale-stat-label">مرتجع</span>
          <span class="sale-stat-value ${totalReturned > 0 ? 'text-warning' : ''}">${moneyR(totalReturned)}</span>
        </div>
        <div class="sale-stat">
          <span class="sale-stat-label">المتبقي</span>
          <span class="sale-stat-value">${moneyR(remaining)}</span>
        </div>
        <div class="sale-stat">
          <span class="sale-stat-label">المنتجات</span>
          <span class="sale-stat-value">${sale.items.length}</span>
        </div>
      </div>
    </div>
  `;

  /* Items */
  if (!sale.items.length) {
    html += '<div class="text-center text-muted py-3">لا توجد منتجات في الفاتورة</div>';
  } else {
    html += '<div class="sale-items-list">';
    sale.items.forEach(item => {
      const fullyReturned = item.available_to_return <= 0;
      const partial = item.already_returned > 0 && !fullyReturned;
      const statusClass = fullyReturned ? 'item-fully-returned' : (partial ? 'item-partial' : 'item-available');

      html += `
        <div class="sale-item-card ${statusClass}">
          <div class="sale-item-header">
            <div class="sale-item-info">
              <strong>${escapeR(item.product_name)}</strong>
              <span class="text-muted">${moneyR(item.unit_price)} × ${item.quantity}</span>
            </div>
            <div class="sale-item-status">
              ${fullyReturned
                ? '<span class="badge bg-secondary">تم الإرجاع بالكامل</span>'
                : partial
                  ? `<span class="badge bg-warning text-dark">مرتجع ${item.already_returned} / ${item.quantity}</span>`
                  : `<span class="badge bg-success">متاح للإرجاع</span>`
              }
            </div>
          </div>
          ${!fullyReturned ? `
          <div class="sale-item-actions">
            ${item.available_to_return > 0 ? `
            <div class="return-action-group">
              <label class="action-label">إرجاع:</label>
              <input type="number" id="ret-qty-${item.product_id}" min="1" max="${item.available_to_return}" value="1" class="form-control action-qty">
              <input type="text" id="ret-notes-${item.product_id}" class="form-control action-notes" placeholder="ملاحظة">
              <button class="btn btn-sm btn-outline-danger" onclick="returnItem(${sale.id}, ${item.product_id}, ${item.available_to_return})">
                <i class="bi bi-arrow-return-left me-1"></i>إرجاع
              </button>
            </div>
            <div class="exchange-action-group">
              <label class="action-label">استبدال:</label>
              <input type="number" id="exch-qty-${item.product_id}" min="1" max="${item.available_to_return}" value="1" class="form-control action-qty">
              <div class="exchange-search-wrap" id="exch-search-wrap-${item.product_id}">
                <input type="text" class="form-control exchange-search-input" placeholder="بحث المنتج الجديد..."
                       id="exch-search-${item.product_id}" oninput="searchExchangeProduct(${item.product_id})" autocomplete="off">
                <div class="exchange-dropdown" id="exch-dropdown-${item.product_id}"></div>
                <input type="hidden" id="exch-new-id-${item.product_id}">
                <div class="exchange-selected" id="exch-selected-${item.product_id}"></div>
              </div>
              <div class="exchange-price-diff" id="exch-diff-${item.product_id}"></div>
              <button class="btn btn-sm btn-outline-primary" id="exch-btn-${item.product_id}" onclick="exchangeItem(${sale.id}, ${item.product_id}, ${item.available_to_return})" disabled>
                <i class="bi bi-arrow-left-right me-1"></i>استبدال
              </button>
            </div>
            ` : ''}
          </div>
          ` : ''}
        </div>
      `;
    });
    html += '</div>';
  }

  container.innerHTML = html;
}

/* ── Return All ───────────────────────────────────────────────────────────── */
async function returnAll(saleId) {
  if (!confirm('هل تريد إرجاع كل المنتجات في الفاتورة؟\nسيتم استرجاع الكمية للمخزون.')) return;
  try {
    const res = await fetch('/api/returns/return-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sale_id: saleId })
    });
    const data = await res.json();
    toastR(data.message || data.error, data.success ? 'success' : 'error');
    if (data.success) {
      loadSale(saleId);
      loadReturnHistory(1);
    }
  } catch {
    toastR('خطأ في الاتصال', 'error');
  }
}

/* ── Void Sale ────────────────────────────────────────────────────────────── */
async function voidSale(saleId) {
  if (!confirm('إلغاء الفاتورة بالكامل؟\nسيتم استرجاع كل الكميات ولا يمكن التراجع.')) return;
  try {
    const res = await fetch('/api/returns/void', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sale_id: saleId })
    });
    const data = await res.json();
    toastR(data.message || data.error, data.success ? 'success' : 'error');
    if (data.success) {
      loadSale(saleId);
      loadReturnHistory(1);
    }
  } catch {
    toastR('خطأ في الاتصال', 'error');
  }
}

/* ── Return Single Item ───────────────────────────────────────────────────── */
async function returnItem(saleId, productId, maxQty) {
  const qtyEl = document.getElementById(`ret-qty-${productId}`);
  const notesEl = document.getElementById(`ret-notes-${productId}`);
  const qty = parseInt(qtyEl?.value || 1);
  if (qty <= 0 || qty > maxQty) {
    toastR(`الكمية يجب أن تكون بين 1 و ${maxQty}`, 'error');
    return;
  }
  if (!confirm(`إرجاع ${qty} من هذا المنتج؟`)) return;

  try {
    const res = await fetch('/api/returns/return', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sale_id: saleId,
        product_id: productId,
        quantity: qty,
        notes: notesEl?.value || ''
      })
    });
    const data = await res.json();
    toastR(data.message || data.error, data.success ? 'success' : 'error');
    if (data.success) {
      loadSale(saleId);
      loadReturnHistory(1);
    }
  } catch {
    toastR('خطأ في الاتصال', 'error');
  }
}

/* ── Exchange Product Search ──────────────────────────────────────────────── */
let exchangeSearchTimers = {};

function searchExchangeProduct(productId) {
  clearTimeout(exchangeSearchTimers[productId]);
  exchangeSearchTimers[productId] = setTimeout(async () => {
    const input = document.getElementById(`exch-search-${productId}`);
    const dropdown = document.getElementById(`exch-dropdown-${productId}`);
    const q = input?.value?.trim();
    if (!q || q.length < 1) {
      if (dropdown) dropdown.style.display = 'none';
      return;
    }
    try {
      const res = await fetch(`/api/products/search?q=${encodeURIComponent(q)}`);
      const products = await res.json();
      if (!products.length) {
        if (dropdown) dropdown.style.display = 'none';
        return;
      }
      dropdown.innerHTML = products.slice(0, 8).map(p => `
        <div class="exchange-option" onclick="selectExchangeProduct(${productId}, ${p.id}, '${escapeR(p.name).replace(/'/g, "\\'")}', ${p.price}, ${p.quantity || 0})">
          <span class="exchange-option-name">${escapeR(p.name)}</span>
          <span class="exchange-option-meta">${moneyR(p.price)} | مخزون: ${p.quantity || 0}</span>
        </div>
      `).join('');
      dropdown.style.display = 'block';
    } catch {}
  }, 200);
}

function selectExchangeProduct(oldProductId, newId, newName, newPrice, stock) {
  const dropdown = document.getElementById(`exch-dropdown-${oldProductId}`);
  const hiddenInput = document.getElementById(`exch-new-id-${oldProductId}`);
  const selectedDiv = document.getElementById(`exch-selected-${oldProductId}`);
  const searchInput = document.getElementById(`exch-search-${oldProductId}`);
  const btn = document.getElementById(`exch-btn-${oldProductId}`);

  if (dropdown) dropdown.style.display = 'none';
  if (hiddenInput) hiddenInput.value = newId;
  if (searchInput) searchInput.value = '';
  if (btn) btn.disabled = false;

  if (selectedDiv) {
    selectedDiv.innerHTML = `
      <div class="exchange-selected-product">
        <i class="bi bi-check-circle-fill text-success me-1"></i>
        <strong>${escapeR(newName)}</strong>
        <span class="text-muted">${moneyR(newPrice)} | مخزون: ${stock}</span>
        <button type="button" class="btn btn-sm btn-link text-danger p-0" onclick="clearExchangeSelection(${oldProductId})">
          <i class="bi bi-x"></i>
        </button>
      </div>
    `;
  }

  updatePriceDiff(oldProductId, newPrice);
}

function clearExchangeSelection(oldProductId) {
  const hiddenInput = document.getElementById(`exch-new-id-${oldProductId}`);
  const selectedDiv = document.getElementById(`exch-selected-${oldProductId}`);
  const diffDiv = document.getElementById(`exch-diff-${oldProductId}`);
  const btn = document.getElementById(`exch-btn-${oldProductId}`);
  if (hiddenInput) hiddenInput.value = '';
  if (selectedDiv) selectedDiv.innerHTML = '';
  if (diffDiv) diffDiv.innerHTML = '';
  if (btn) btn.disabled = true;
}

function updatePriceDiff(oldProductId, newPrice) {
  const saleItemCard = document.querySelector(`[onclick*="returnItem"][onclick*="${oldProductId}"]`)?.closest('.sale-item-card');
  if (!saleItemCard) return;
  const oldPriceText = saleItemCard.querySelector('.sale-item-info .text-muted')?.textContent || '';
  const oldPrice = parseFloat(oldPriceText) || 0;
  const diff = newPrice - oldPrice;
  const diffDiv = document.getElementById(`exch-diff-${oldProductId}`);
  if (!diffDiv) return;

  if (Math.abs(diff) < 0.01) {
    diffDiv.innerHTML = '<span class="text-muted" style="font-size:.9rem">السعر متساوي</span>';
  } else if (diff > 0) {
    diffDiv.innerHTML = `<span class="text-danger fw-bold" style="font-size:.95rem">العميل يدفع ${moneyR(diff)}</span>`;
  } else {
    diffDiv.innerHTML = `<span class="text-success fw-bold" style="font-size:.95rem">استرداد ${moneyR(Math.abs(diff))}</span>`;
  }
}

/* ── Exchange Item ────────────────────────────────────────────────────────── */
async function exchangeItem(saleId, productId, maxQty) {
  const qtyEl = document.getElementById(`exch-qty-${productId}`);
  const newIdEl = document.getElementById(`exch-new-id-${productId}`);
  const notesEl = document.getElementById(`ret-notes-${productId}`);
  const qty = parseInt(qtyEl?.value || 1);
  const newProductId = newIdEl?.value;

  if (!newProductId) {
    toastR('اختر المنتج الجديد للاستبدال', 'error');
    return;
  }
  if (qty <= 0 || qty > maxQty) {
    toastR(`الكمية يجب أن تكون بين 1 و ${maxQty}`, 'error');
    return;
  }
  if (!confirm(`استبدال ${qty} من هذا المنتج بالمنتج الجديد؟`)) return;

  try {
    const res = await fetch('/api/returns/exchange', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sale_id: saleId,
        product_id: productId,
        new_product_id: newProductId,
        quantity: qty,
        notes: notesEl?.value || ''
      })
    });
    const data = await res.json();
    toastR(data.message || data.error, data.success ? 'success' : 'error');
    if (data.success) {
      loadSale(saleId);
      loadReturnHistory(1);
    }
  } catch {
    toastR('خطأ في الاتصال', 'error');
  }
}

/* ── Keyboard Shortcuts ────────────────────────────────────────────────────── */
document.addEventListener('keydown', function (e) {
  const tag = e.target.tagName.toLowerCase();
  const saleInput = document.getElementById('sale-id-input');

  if (e.key === 'F2') {
    e.preventDefault();
    saleInput?.focus();
    saleInput?.select();
    return;
  }

  if (e.key === 'Enter' && document.activeElement === saleInput) {
    e.preventDefault();
    const id = saleInput.value.trim();
    if (id) loadSale(id);
    return;
  }
});

/* ── Init ─────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
  loadReturnHistory(1);

  const saleInput = document.getElementById('sale-id-input');
  if (saleInput?.value) {
    loadSale(saleInput.value);
  }

  document.getElementById('sale-search-form')?.addEventListener('submit', function (e) {
    e.preventDefault();
    const id = document.getElementById('sale-id-input')?.value?.trim();
    if (id) loadSale(id);
  });

  document.addEventListener('click', function (e) {
    document.querySelectorAll('.exchange-dropdown').forEach(dd => {
      if (!dd.contains(e.target) && !e.target.classList.contains('exchange-search-input')) {
        dd.style.display = 'none';
      }
    });
  });
});
