/* ProductIQ — API client with offline mock fallback.
   Tries the FastAPI backend first; falls back to realistic mock data
   so the UI is fully demoable even without the backend running. */

const API_BASE = 'http://127.0.0.1:8000';

const Api = {
  async request(path, options = {}) {
    try {
      const res = await fetch(API_BASE + path, { ...options, credentials: 'include' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn(`[Api] Backend unavailable for ${path}, using mock.`, err.message);
      return null;
    }
  },

  /* ── Analytics ── */
  async getAnalytics() {
    const data = await this.request('/api/analytics');
    return data || MockData.analytics();
  },

  /* ── AI recommendations ── */
  async getRecommendations(lang = 'en') {
    const data = await this.request(`/api/recommendations?lang=${lang}`);
    return data || MockData.recommendations(lang);
  },

  /* ── Product DNA ── */
  async getProductList() {
    const data = await this.request('/api/products');
    return data || MockData.productList();
  },
  async getProductDNA(productId) {
    const data = await this.request(`/api/product-dna/${encodeURIComponent(productId)}`);
    return data || MockData.productDNA(productId);
  },

  /* ── CEO report ── */
  async getCeoReport(lang = 'en') {
    const data = await this.request(`/api/ceo-report?lang=${lang}`, { method: 'POST' });
    return data || MockData.ceoReport(lang);
  },

  /* ── What-if simulator ── */
  async simulate(payload) {
    const data = await this.request('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return data || MockData.simulate(payload);
  },

  /* ── Upload ── */
  async uploadFiles(files) {
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    const data = await this.request('/api/upload', { method: 'POST', body: fd });
    return data || MockData.uploadResult();
  },
  async loadSample() {
    const data = await this.request('/api/load-sample', { method: 'POST' });
    return data || MockData.uploadResult(true);
  },

  /* ── Board meeting ── */
  async boardMeeting(productId, lang = 'en') {
    const data = await this.request('/api/board-meeting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: productId, lang })
    });
    return data || MockData.boardMeeting(productId);
  }
};

/* ═══════════════ Mock data (Egyptian electronics shop) ═══════════════ */
const MockData = {
  _products: [
    { id: 'P001', name: 'Samsung Galaxy A56', name_ar: 'سامسونج جالاكسي A56', category: 'Smartphones', category_ar: 'هواتف ذكية', price: 5990, cost: 5100, stock: 120, sold30: 45, revenue: 269550 },
    { id: 'P002', name: 'iPhone 16 Pro', name_ar: 'آيفون 16 برو', category: 'Smartphones', category_ar: 'هواتف ذكية', price: 39990, cost: 32000, stock: 30, sold30: 12, revenue: 479880 },
    { id: 'P003', name: 'Xiaomi Redmi Note 14', name_ar: 'شاومي ريدمي نوت 14', category: 'Smartphones', category_ar: 'هواتف ذكية', price: 1800, cost: 1500, stock: 0, sold30: 78, revenue: 140400 },
    { id: 'P004', name: 'Sony WH-1000XM6', name_ar: 'سوني WH-1000XM6', category: 'Audio', category_ar: 'صوتيات', price: 14990, cost: 10500, stock: 5, sold30: 8, revenue: 119920 },
    { id: 'P005', name: 'Samsung Galaxy Tab S10', name_ar: 'سامسونج جالاكسي تاب S10', category: 'Tablets', category_ar: 'تابلت', price: 14990, cost: 11500, stock: 20, sold30: 15, revenue: 224850 },
    { id: 'P006', name: 'Anker PowerCore 20000', name_ar: 'أنكر باوركور 20000', category: 'Accessories', category_ar: 'إكسسوارات', price: 1450, cost: 980, stock: 65, sold30: 52, revenue: 75400 },
    { id: 'P007', name: 'JBL Flip 7', name_ar: 'جي بي ال فليب 7', category: 'Audio', category_ar: 'صوتيات', price: 4200, cost: 3100, stock: 18, sold30: 6, revenue: 25200 },
    { id: 'P008', name: 'Huawei Watch Fit 4', name_ar: 'هواوي ووتش فيت 4', category: 'Wearables', category_ar: 'أجهزة قابلة للارتداء', price: 3500, cost: 2600, stock: 40, sold30: 22, revenue: 77000 },
    { id: 'P009', name: 'HP LaserJet Pro M404', name_ar: 'اتش بي ليزر جيت برو', category: 'Printers', category_ar: 'طابعات', price: 9500, cost: 7800, stock: 8, sold30: 0, revenue: 0 },
    { id: 'P010', name: 'Canon EOS R50', name_ar: 'كانون EOS R50', category: 'Cameras', category_ar: 'كاميرات', price: 32000, cost: 27500, stock: 3, sold30: 1, revenue: 32000 }
  ],

  analytics() {
    const totalRevenue = 1464200;
    const totalProfit = 301800;
    return {
      kpis: {
        revenue: totalRevenue,
        revenue_change: 12.4,
        profit: totalProfit,
        profit_change: 8.1,
        margin: 20.6,
        margin_change: -1.2,
        turnover: 8.2,
        turnover_change: 0.6
      },
      top_sellers: this._products.slice(0, 5).map(p => ({
        name: p.name, name_ar: p.name_ar, sold: p.sold30, revenue: p.revenue,
        margin: Math.round(((p.price - p.cost) / p.price) * 100)
      })),
      category_revenue: [
        { category: 'Smartphones', category_ar: 'هواتف ذكية', revenue: 889830 },
        { category: 'Tablets', category_ar: 'تابلت', revenue: 224850 },
        { category: 'Audio', category_ar: 'صوتيات', revenue: 145120 },
        { category: 'Wearables', category_ar: 'أجهزة قابلة للارتداء', revenue: 77000 },
        { category: 'Accessories', category_ar: 'إكسسوارات', revenue: 75400 },
        { category: 'Cameras', category_ar: 'كاميرات', revenue: 32000 }
      ],
      weekly_trend: [
        { week: 'W1', revenue: 98500 }, { week: 'W2', revenue: 112300 },
        { week: 'W3', revenue: 105800 }, { week: 'W4', revenue: 128400 },
        { week: 'W5', revenue: 119200 }, { week: 'W6', revenue: 134600 },
        { week: 'W7', revenue: 142100 }, { week: 'W8', revenue: 151300 }
      ],
      slow_movers: [
        { name: 'HP LaserJet Pro M404', name_ar: 'اتش بي ليزر جيت برو', days_no_sale: 47, stock: 8, tied_capital: 62400, lost_profit_egp: 12200, recovery_suggestion: 'Liquidate \u2014 discount 20-30% or bundle to clear' },
        { name: 'Canon EOS R50', name_ar: 'كانون EOS R50', days_no_sale: 21, stock: 3, tied_capital: 82500, lost_profit_egp: 3400, recovery_suggestion: 'Run a 10-15% discount campaign for 2 weeks; reassess' },
        { name: 'JBL Flip 7', name_ar: 'جي بي ال فليب 7', days_no_sale: 12, stock: 18, tied_capital: 55800, lost_profit_egp: 1200, recovery_suggestion: 'Bundle with a fast-moving product to move stock' }
      ],
      stock_risk: [
        { name: 'Xiaomi Redmi Note 14', name_ar: 'شاومي ريدمي نوت 14', stock: 0, status: 'out' },
        { name: 'Sony WH-1000XM6', name_ar: 'سوني WH-1000XM6', stock: 5, status: 'critical' },
        { name: 'Canon EOS R50', name_ar: 'كانون EOS R50', stock: 3, status: 'critical' }
      ]
    };
  },

  recommendations(lang = 'en') {
    const recs = [
      { product: 'Xiaomi Redmi Note 14', product_ar: 'شاومي ريدمي نوت 14', action: 'restock', reason_en: 'Out of stock with the highest sales velocity (78 units/30d). Restock ~120 units immediately — you are losing sales daily.', reason_ar: 'نفد المخزون مع أعلى سرعة مبيعات (78 وحدة/30 يوم). أعد الطلب فوراً ~120 وحدة — تخسر مبيعات يومياً.', confidence: 96 },
      { product: 'HP LaserJet Pro M404', product_ar: 'اتش بي ليزر جيت برو', action: 'discount', reason_en: 'Zero sales in 47 days with 8 units tying up 62,400 EGP. Discount 15% or bundle with office supplies to clear.', reason_ar: 'لا مبيعات منذ 47 يوماً و8 وحدات تحجز 62,400 ج.م. خصم 15% أو حزمة مع مستلزمات مكتبية لتصفية المخزون.', confidence: 88 },
      { product: 'Sony WH-1000XM6', product_ar: 'سوني WH-1000XM6', action: 'bundle', reason_en: 'High margin (30%) but low volume. Bundle with Samsung Galaxy Tab S10 for a premium "work-from-anywhere" kit.', reason_ar: 'هامش مرتفع (30%) لكن حجم منخفض. حزمة مع جالاكسي تاب S10 كعرض "اعمل من أي مكان" المميز.', confidence: 74 },
      { product: 'Canon EOS R50', product_ar: 'كانون EOS R50', action: 'remove', reason_en: 'One sale in 30 days, 82,500 EGP tied in 3 units. Stop restocking and liquidate current stock.', reason_ar: 'بيع واحد في 30 يوماً و82,500 ج.م محجوزة في 3 وحدات. أوقف إعادة الطلب وصفِّ المخزون الحالي.', confidence: 81 }
    ];
    return {
      summary_en: 'Store health is good overall (8.2 turns/year), but capital is misallocated: your best seller is out of stock while 145,000 EGP sits in dead printer/camera stock. Fix the Xiaomi restock first, then clear the LaserJet.',
      summary_ar: 'صحة المتجر جيدة عموماً (8.2 دورة/سنة)، لكن رأس المال موزع بشكل خاطئ: الأكثر مبيعاً نفد من المخزون بينما 145,000 ج.م محجوزة في مخزون راكد. أعد طلب الشاومي أولاً، ثم صفِّ الطابعة.',
      recommendations: recs
    };
  },

  productList() {
    return this._products.map(p => ({
      id: p.id, name: p.name, name_ar: p.name_ar,
      category: p.category, category_ar: p.category_ar, price: p.price
    }));
  },

  productDNA(productId) {
    const base = {
      P001: { popularity: 82, margin: 55, demand: 88, risk: 78, competitiveness: 70, turnover: 84, growth: 72, value: 79 },
      P002: { popularity: 90, margin: 62, demand: 55, risk: 65, competitiveness: 85, turnover: 40, growth: 68, value: 72 },
      P003: { popularity: 95, margin: 38, demand: 96, risk: 85, competitiveness: 60, turnover: 98, growth: 80, value: 83 },
      P004: { popularity: 48, margin: 85, demand: 35, risk: 45, competitiveness: 72, turnover: 28, growth: 40, value: 52 },
      P005: { popularity: 62, margin: 70, demand: 58, risk: 72, competitiveness: 66, turnover: 55, growth: 60, value: 64 },
      P006: { popularity: 75, margin: 68, demand: 80, risk: 88, competitiveness: 55, turnover: 82, growth: 58, value: 74 },
      P007: { popularity: 40, margin: 60, demand: 25, risk: 52, competitiveness: 48, turnover: 30, growth: 32, value: 40 },
      P008: { popularity: 68, margin: 58, demand: 66, risk: 75, competitiveness: 62, turnover: 64, growth: 70, value: 66 },
      P009: { popularity: 22, margin: 48, demand: 8, risk: 15, competitiveness: 40, turnover: 5, growth: 10, value: 18 },
      P010: { popularity: 30, margin: 52, demand: 12, risk: 20, competitiveness: 45, turnover: 8, growth: 15, value: 25 }
    };
    const p = this._products.find(x => x.id === productId) || this._products[0];
    const dims = base[p.id] || base.P001;
    const health = Math.round(Object.values(dims).reduce((a, b) => a + b, 0) / Object.keys(dims).length);
    return { product: p, dimensions: dims, health_score: health };
  },

  ceoReport(lang = 'en') {
    return {
      week: 'Jul 21 – Jul 27, 2026',
      week_ar: '21 – 27 يوليو 2026',
      summary_en: 'Revenue grew 12.4% week-over-week driven by smartphone sales. However, your #1 seller (Xiaomi Redmi Note 14) has been out of stock for 3 days — estimated 18,000 EGP in lost sales. Meanwhile 145,000 EGP sits idle in the HP LaserJet and Canon EOS R50. Priority one: restock the Xiaomi. Priority two: liquidate dead stock to free capital.',
      summary_ar: 'نمت الإيرادات 12.4% عن الأسبوع الماضي مدفوعة بمبيعات الهواتف. لكن المنتج الأول (شاومي ريدمي نوت 14) نفد من المخزون منذ 3 أيام — خسارة مقدرة 18,000 ج.م. في المقابل 145,000 ج.م مجمّدة في طابعة HP وكاميرا كانون. الأولوية الأولى: إعادة طلب الشاومي. الثانية: تصفية المخزون الراكد لتحرير رأس المال.',
      revenue: { this_week: 412800, last_week: 367200, change_pct: 12.4, profit: 85200, profit_change_pct: 8.1 },
      top_products: [
        { name: 'Xiaomi Redmi Note 14', name_ar: 'شاومي ريدمي نوت 14', revenue: 140400, units: 78 },
        { name: 'iPhone 16 Pro', name_ar: 'آيفون 16 برو', revenue: 479880, units: 12 },
        { name: 'Samsung Galaxy A56', name_ar: 'سامسونج جالاكسي A56', revenue: 269550, units: 45 }
      ],
      needs_attention: [
        { name: 'Xiaomi Redmi Note 14', name_ar: 'شاومي ريدمي نوت 14', issue_en: 'OUT OF STOCK — losing ~2,600 EGP/day', issue_ar: 'نفد المخزون — خسارة ~2,600 ج.م/يوم' },
        { name: 'HP LaserJet Pro M404', name_ar: 'اتش بي ليزر جيت برو', issue_en: 'No sales in 47 days — 62,400 EGP tied up', issue_ar: 'لا مبيعات منذ 47 يوماً — 62,400 ج.م محجوزة' }
      ],
      action_items_en: [
        'Order 120 units of Xiaomi Redmi Note 14 today (supplier lead time: 2 days)',
        'Launch 15% clearance on HP LaserJet Pro M404 this week',
        'Bundle Sony WH-1000XM6 + Galaxy Tab S10 as a premium kit before back-to-school season',
        'Negotiate better cost with الجمعة للتكنولوجيا — iPhone margin dropped 2% this month',
        'Do not restock Canon EOS R50 until current 3 units sell'
      ],
      action_items_ar: [
        'اطلب 120 وحدة من شاومي ريدمي نوت 14 اليوم (مدة التوريد: يومان)',
        'أطلق تصفية 15% على طابعة HP ليزر جيت هذا الأسبوع',
        'حزمة سوني WH-1000XM6 + جالاكسي تاب S10 كعرض مميز قبل موسم المدارس',
        'تفاوض على سعر أفضل مع الجمعة للتكنولوجيا — هامش الآيفون انخفض 2% هذا الشهر',
        'لا تعد طلب كانون EOS R50 حتى تباع الوحدات الثلاث الحالية'
      ],
      supplier_alerts_en: ['النور للتوريدات: delivery improved to 2 days (was 4)', 'الجمعة للتكنولوجيا: 2 price increases this month'],
      supplier_alerts_ar: ['النور للتوريدات: تحسّن التسليم إلى يومين (كان 4)', 'الجمعة للتكنولوجيا: زيادتا أسعار هذا الشهر']
    };
  },

  simulate(payload) {
    const isDecrease = (payload.change_type || '').includes('decrease') || (payload.change_type || '').includes('discount');
    const v = parseFloat(payload.change_value) || 10;
    const cost = 5100;
    const curPrice = payload.current_price || 5990;
    const curMarginPct = Math.round(((curPrice - cost) / curPrice) * 100 * 10) / 10;
    const newPrice = isDecrease ? curPrice * (1 - v / 100) : curPrice * (1 + v / 100);
    const projMarginPct = Math.round(((newPrice - cost) / newPrice) * 100 * 10) / 10;
    return {
      product: payload.product_name || 'Samsung Galaxy A56',
      current_price: curPrice,
      demand_change_pct: isDecrease ? Math.round(v * 2.1) : -Math.round(v * 1.6),
      revenue_impact_egp: isDecrease ? Math.round(v * 850) : -Math.round(v * 620),
      profit_impact_egp: isDecrease ? -Math.round(v * 180) : Math.round(v * 240),
      current_margin_pct: curMarginPct,
      projected_margin_pct: projMarginPct,
      breakeven_units: isDecrease ? Math.ceil(45 * (curPrice - cost) / (newPrice - cost)) : 0,
      profit_breakdown: {
        volume_impact_egp: isDecrease ? Math.round(v * 400) : -Math.round(v * 300),
        margin_impact_egp: isDecrease ? -Math.round(v * 580) : Math.round(v * 540),
      },
      risk_level: v > 15 ? 'high' : v > 7 ? 'medium' : 'low',
      confidence_pct: 72,
      assumptions_en: [
        'Price elasticity estimated from category history (smartphones ~2.1)',
        'Competitor prices assumed stable during the period',
        'No seasonal event (Ramadan / back-to-school) within the window'
      ],
      assumptions_ar: [
        'مرونة السعر مقدّرة من تاريخ الفئة (هواتف ~2.1)',
        'أسعار المنافسين مفترضة ثابتة خلال الفترة',
        'لا يوجد موسم (رمضان / المدارس) خلال النافذة الزمنية'
      ]
    };
  },

  uploadResult(sample = false) {
    return {
      ok: true,
      sample,
      files: [
        { name: 'products.csv', rows: 10, valid: 10, flagged: 0, rejected: 0 },
        { name: 'sales.csv', rows: 312, valid: 308, flagged: 3, rejected: 1 },
        { name: 'inventory.csv', rows: 10, valid: 10, flagged: 0, rejected: 0 },
        { name: 'suppliers.csv', rows: 5, valid: 5, flagged: 0, rejected: 0 }
      ],
      flags: [
        { file: 'sales.csv', row: 88, reason_en: 'Price mismatch vs catalog (flagged for review)', reason_ar: 'سعر مختلف عن الكتالوج (للمراجعة)' },
        { file: 'sales.csv', row: 151, reason_en: 'Suspected duplicate transaction', reason_ar: 'اشتباه في معاملة مكررة' },
        { file: 'sales.csv', row: 240, reason_en: 'Unusual quantity (18 units) — confirm', reason_ar: 'كمية غير معتادة (18 وحدة) — تأكيد' }
      ]
    };
  },

  boardMeeting(productId) {
    const p = this._products.find(x => x.id === productId) || this._products[0];
    return {
      product_name: p.name,
      context: `Product: ${p.name}\nCost: ${p.cost} EGP | Price: ${p.price} EGP\nStock: ${p.stock} units | Sold (30d): ${p.sold30}\nRevenue (30d): ${p.revenue} EGP`,
      transcript: [
        { role_en: 'CFO', role_ar: 'المدير المالي', color: '#3B82F6',
          analysis: `${p.name} carries a margin of ~${Math.round((p.price - p.cost) / p.price * 100)}% on a ${p.cost} EGP cost base. With ${p.stock} units on hand, capital exposure is ${(p.stock * p.cost).toLocaleString()} EGP. Sell-through must stay strong to justify this position. RECOMMENDATION: monitor margin closely, proceed if turnover holds.` },
        { role_en: 'Marketing Director', role_ar: 'مدير التسويق', color: '#10B981',
          analysis: `${p.name} is a ${p.category} product with solid brand recognition in Egypt. Sold ${p.sold30} units last month — demand signal is ${p.sold30 > 20 ? 'strong' : 'moderate'}. Competitors position aggressively on price in this segment. RECOMMENDATION: keep stocked, consider a targeted campaign if velocity drops.` },
        { role_en: 'Inventory Manager', role_ar: 'مدير المخزون', color: '#F59E0B',
          analysis: `Current stock is ${p.stock} units against a 30-day pace of ${p.sold30}. That is ${p.sold30 > 0 ? Math.round(p.stock / Math.max(p.sold30 / 30, 1)) + ' days of cover' : 'no velocity'}. Supplier lead time factors into reorder timing. RECOMMENDATION: ${p.stock === 0 ? 'restock immediately' : p.stock > p.sold30 * 2 ? 'hold orders, reduce overstock' : 'maintain current levels'}.` },
        { role_en: 'CEO', role_ar: 'الرئيس التنفيذي', color: '#0B1F3A', is_final: true,
          analysis: `After hearing all departments: ${p.name} shows ${p.sold30 > 20 ? 'strong velocity with acceptable margin' : 'moderate performance'}. The financial exposure is manageable and market demand exists. FINAL DECISION: ${p.stock === 0 ? 'restock 50-100 units now' : p.stock > p.sold30 * 2 ? 'pause restocking, run a clearance campaign' : 'stock conservatively at current levels and reassess in 30 days'}.` }
      ]
    };
  }
};
