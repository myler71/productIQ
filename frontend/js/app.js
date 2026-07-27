/* ProductIQ — shared app utilities */
const App = {
  /* Number formatting: 1,234,567 EGP */
  egp(n) {
    if (n === null || n === undefined) return '—';
    const formatted = Math.round(n).toLocaleString('en-EG');
    return I18n.lang === 'ar' ? `${formatted} ج.م` : `EGP ${formatted}`;
  },
  num(n) {
    return (n === null || n === undefined) ? '—' : Number(n).toLocaleString('en-EG');
  },
  pct(n, sign = true) {
    if (n === null || n === undefined) return '—';
    const s = sign && n > 0 ? '+' : '';
    return `${s}${n}%`;
  },

  /* Localized product name helper */
  pname(obj) {
    return I18n.lang === 'ar' && obj.name_ar ? obj.name_ar : obj.name;
  },
  pcat(obj) {
    return I18n.lang === 'ar' && obj.category_ar ? obj.category_ar : obj.category;
  },

  /* Sidebar wiring (all pages share the same structure) */
  initSidebar(activeId) {
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.classList.toggle('active', item.dataset.page === activeId);
      item.addEventListener('click', () => {
        const href = item.dataset.href;
        if (href) window.location.href = href;
      });
    });
    const burger = document.querySelector('.hamburger');
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    if (burger && sidebar) {
      burger.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        if (overlay) overlay.classList.toggle('show');
      });
      if (overlay) overlay.addEventListener('click', () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('show');
      });
    }
  },

  /* Loading overlay */
  showLoading(show = true) {
    let el = document.getElementById('piq-loading');
    if (!el) {
      el = document.createElement('div');
      el.id = 'piq-loading';
      el.style.cssText = 'position:fixed;inset:0;background:rgba(11,31,58,0.45);display:flex;align-items:center;justify-content:center;z-index:9999;backdrop-filter:blur(2px);';
      el.innerHTML = `<div style="background:#fff;padding:24px 32px;border-radius:12px;font-weight:600;display:flex;align-items:center;gap:12px;">
        <span class="piq-spinner"></span><span data-i18n="common.loading">${I18n.t('common.loading')}</span></div>`;
      const style = document.createElement('style');
      style.textContent = '.piq-spinner{width:18px;height:18px;border:3px solid #E2E8F0;border-top-color:#00A6A6;border-radius:50%;animation:piqspin 0.8s linear infinite;}@keyframes piqspin{to{transform:rotate(360deg);}}';
      document.head.appendChild(style);
      document.body.appendChild(el);
    }
    el.style.display = show ? 'flex' : 'none';
  },

  /* Health score → color */
  healthColor(score) {
    if (score >= 70) return '#10B981';
    if (score >= 45) return '#F59E0B';
    return '#EF4444';
  },
  healthLabel(score) {
    if (I18n.lang === 'ar') {
      return score >= 70 ? 'صحي' : score >= 45 ? 'يحتاج متابعة' : 'معرّض للخطر';
    }
    return score >= 70 ? 'Healthy' : score >= 45 ? 'Watch' : 'At Risk';
  },

  riskBadge(level) {
    const map = {
      low: { cls: 'badge-success', en: 'Low risk', ar: 'مخاطرة منخفضة' },
      medium: { cls: 'badge-warning', en: 'Medium risk', ar: 'مخاطرة متوسطة' },
      high: { cls: 'badge-danger', en: 'High risk', ar: 'مخاطرة مرتفعة' }
    };
    const m = map[level] || map.medium;
    return `<span class="badge ${m.cls}">${I18n.lang === 'ar' ? m.ar : m.en}</span>`;
  }
};
