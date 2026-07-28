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

  /* Top navigation wiring (all pages share the same topbar structure) */
  initNav(activeId) {
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.classList.toggle('active', item.dataset.page === activeId);
      item.addEventListener('click', () => {
        const href = item.dataset.href;
        if (href) window.location.href = href;
      });
    });
    const burger = document.querySelector('.topbar .hamburger');
    const links = document.querySelector('.topbar .nav-links');
    if (burger && links) {
      burger.addEventListener('click', () => links.classList.toggle('open'));
    }
    this.initUserMenu();
  },

  /* User menu in the topbar: shows username + logout when authenticated,
     otherwise a Login link. Filled from /api/auth/me. */
  async initUserMenu() {
    const slot = document.getElementById('userMenu');
    if (!slot) return;
    try {
      const r = await fetch('/api/auth/me');
      const data = await r.json();
      if (data.authenticated) {
        slot.innerHTML = `<span class="user-name">${data.username}</span>
          <button class="btn btn-ghost btn-sm" id="logoutBtn" style="color:var(--text-on-dark)">${I18n.t('auth.signout')}</button>`;
        document.getElementById('logoutBtn').addEventListener('click', async () => {
          await fetch('/api/auth/logout', { method: 'POST' });
          window.location.reload();
        });
      } else {
        slot.innerHTML = `<a href="login.html" class="btn btn-outline btn-sm" style="color:white;border-color:rgba(255,255,255,0.4)">${I18n.t('auth.login')}</a>`;
      }
    } catch { /* server down — leave the slot empty */ }
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
  },

  /* AI provenance badge */
  engineBadge(engine, lastError = '') {
    const labels = {
      llm: {
        en: { text: 'AI-generated', cls: 'badge-success' },
        ar: { text: 'مولّد بالذكاء الاصطناعي', cls: 'badge-success' }
      },
      deterministic: {
        en: { text: 'Rule-based (LLM offline)', cls: 'badge' },
        ar: { text: 'قواعد محددة (الذكاء غير متصل)', cls: 'badge' }
      },
      'deterministic+llm': {
        en: { text: 'Computed, AI-explained', cls: 'badge-info' },
        ar: { text: 'محسوب، موضّح بالذكاء', cls: 'badge-info' }
      }
    };
    const entry = labels[engine] || labels.deterministic;
    const l = I18n.lang === 'ar' ? entry.ar : entry.en;
    const tooltip = lastError ? `title="${lastError.replace(/"/g, '&quot;')}"` : '';
    return `<span class="badge ${l.cls}" ${tooltip}>${l.text}</span>`;
  },

  /* Connection / demo-mode banner */
  initConnectionBanner() {
    if (document.getElementById('piq-connection-banner')) return;
    fetch('/api/health', { credentials: 'include' })
      .then(r => r.json())
      .then(data => {
        const status = data.llm || {};
        if (!status.available) {
          const banner = document.createElement('div');
          banner.id = 'piq-connection-banner';
          const msg = I18n.lang === 'ar'
            ? `الذكاء الاصطناعي غير متصل: ${status.last_error || 'مفتاح GROQ_API_KEY غير مضبوط'}. العمل قواعد محددة.`
            : `AI offline: ${status.last_error || 'GROQ_API_KEY not set'}. Running rule-based.`;
          banner.style.cssText = 'background:var(--danger-bg);color:var(--danger);padding:10px 16px;text-align:center;font-size:0.8125rem;font-weight:500;border-bottom:1px solid rgba(239,68,68,0.2);';
          banner.textContent = msg;
          document.body.insertBefore(banner, document.body.firstChild);
        }
      })
      .catch(() => {});
  },

  async checkHealth() {
    try {
      const r = await fetch('/api/health', { credentials: 'include' });
      const d = await r.json();
      return d.llm || { available: false, last_error: 'unknown' };
    } catch {
      return { available: false, last_error: 'server unreachable' };
    }
  }
};
