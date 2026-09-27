(function () {
  function closeModal(modal) {
    if (!modal) return;
    modal.classList.remove('show');
    modal.style.display = 'none';
    document.body.classList.remove('modal-open');
    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
  }

  function showModal(modal) {
    if (!modal) return;
    modal.style.display = 'block';
    modal.classList.add('show');
    document.body.classList.add('modal-open');
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop show';
    backdrop.addEventListener('click', () => closeModal(modal));
    document.body.appendChild(backdrop);
  }

  window.bootstrap = window.bootstrap || {};
  window.bootstrap.Modal = function (element) {
    return {
      show: () => showModal(element),
      hide: () => closeModal(element)
    };
  };

  document.addEventListener('click', event => {
    const dismiss = event.target.closest('[data-bs-dismiss="modal"]');
    if (dismiss) closeModal(dismiss.closest('.modal'));

    const alertDismiss = event.target.closest('[data-bs-dismiss="alert"]');
    if (alertDismiss) {
      const alert = alertDismiss.closest('.alert');
      if (alert) alert.remove();
    }
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      document.querySelectorAll('.modal.show').forEach(closeModal);
    }
  });

  // CSRF token helper for AJAX POST requests
  window.getCsrfToken = function() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  };

  const _origFetch = window.fetch;
  window.fetch = function(url, opts) {
    if (opts && opts.method && opts.method.toUpperCase() === 'POST') {
      opts.headers = opts.headers || {};
      if (typeof opts.headers.set === 'function') {
        opts.headers.set('X-CSRFToken', window.getCsrfToken());
      } else if (!opts.headers['X-CSRFToken']) {
        opts.headers['X-CSRFToken'] = window.getCsrfToken();
      }
    }
    return _origFetch.call(this, url, opts);
  };
})();
