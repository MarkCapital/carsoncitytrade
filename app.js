const state = {
  gold: 4331.90,
  silver: 68.74,
  source: 'fallback demo values',
  updatedAt: null,
};

const els = {
  goldPrice: document.querySelector('#goldPrice'),
  silverPrice: document.querySelector('#silverPrice'),
  goldSilverRatio: document.querySelector('#goldSilverRatio'),
  marketStatus: document.querySelector('#marketStatus'),
  lastUpdated: document.querySelector('#lastUpdated'),
  refreshPrices: document.querySelector('#refreshPrices'),
  menuButton: document.querySelector('.menu-button'),
  navLinks: document.querySelector('.nav-links'),
};

function money(value) {
  return Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function renderPrices() {
  els.goldPrice.textContent = money(state.gold);
  els.silverPrice.textContent = money(state.silver);
  const ratio = Number(state.gold) > 0 && Number(state.silver) > 0 ? Number(state.gold) / Number(state.silver) : 0;
  if (els.goldSilverRatio) els.goldSilverRatio.textContent = ratio ? `${ratio.toFixed(1)}:1` : '—';
  const updated = state.updatedAt ? new Date(state.updatedAt) : new Date();
  els.lastUpdated.textContent = `Updated ${updated.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  els.marketStatus.textContent = state.source === 'live'
    ? 'Live market data loaded'
    : 'Using saved fallback prices';
  calculateAll();
}

async function fetchMetal(symbol) {
  const response = await fetch(`https://api.gold-api.com/price/${symbol}`, {
    headers: { accept: 'application/json' },
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`${symbol} price request failed`);
  return response.json();
}

async function refreshPrices() {
  els.marketStatus.textContent = 'Refreshing live market data…';
  try {
    const [gold, silver] = await Promise.all([fetchMetal('XAU'), fetchMetal('XAG')]);
    if (!Number.isFinite(Number(gold.price)) || !Number.isFinite(Number(silver.price))) {
      throw new Error('Invalid metals response');
    }
    state.gold = Number(gold.price);
    state.silver = Number(silver.price);
    state.updatedAt = gold.updatedAt || silver.updatedAt || new Date().toISOString();
    state.source = 'live';
    localStorage.setItem('cctp-price-cache', JSON.stringify(state));
  } catch (error) {
    const cached = localStorage.getItem('cctp-price-cache');
    if (cached) {
      try {
        Object.assign(state, JSON.parse(cached));
        state.source = state.source === 'live' ? 'live' : 'cached fallback';
      } catch {}
    }
    els.marketStatus.textContent = 'Live pricing unavailable — using saved fallback';
  }
  renderPrices();
}

function getSilverSpot() { return Number(state.silver || 0); }
function getValue(id) { return Number(document.querySelector(id)?.value || 0); }

function calculateJunkSilver() {
  const face = getValue('#junkFace');
  const premium = getValue('#junkPremium');
  const melt = face * 0.715 * getSilverSpot();
  const withPremium = melt * (1 + premium / 100);
  const multiple = face > 0 ? withPremium / face : 0;
  document.querySelector('#junkResult').innerHTML = `
    <strong>${money(withPremium)}</strong><br>
    Melt: ${money(melt)} • ${multiple.toFixed(2)}× face value
  `;
}

function convertToTroyOunces(weight, unit) {
  if (unit === 'grams') return weight / 31.1034768;
  if (unit === 'avoirdupois') return weight * 0.911458333;
  return weight;
}

function calculateSilverValue() {
  const weight = getValue('#silverWeight');
  const purity = getValue('#silverPurity') / 100;
  const unit = document.querySelector('#silverUnit').value;
  const troy = convertToTroyOunces(weight, unit);
  const pureOunces = troy * purity;
  const value = pureOunces * getSilverSpot();
  document.querySelector('#silverResult').innerHTML = `
    <strong>${money(value)}</strong><br>
    ${pureOunces.toFixed(4)} pure troy oz silver at ${money(getSilverSpot())}/oz
  `;
}

function calculateBreakEven() {
  const cost = getValue('#purchasePrice');
  const ounces = getValue('#pureOunces');
  const neededSpot = ounces > 0 ? cost / ounces : 0;
  const currentSpot = getSilverSpot();
  const difference = neededSpot - currentSpot;
  const status = difference <= 0
    ? `${money(Math.abs(difference))}/oz above break-even right now`
    : `${money(difference)}/oz more needed to break even`;
  document.querySelector('#breakevenResult').innerHTML = `
    <strong>${money(neededSpot)}/oz break-even</strong><br>
    Current silver spot: ${money(currentSpot)} • ${status}
  `;
}

function calculateAll() {
  calculateJunkSilver();
  calculateSilverValue();
  calculateBreakEven();
}

function setupCalculators() {
  ['#junkFace', '#junkPremium', '#silverWeight', '#silverPurity', '#silverUnit', '#purchasePrice', '#pureOunces']
    .forEach(selector => document.querySelector(selector)?.addEventListener('input', calculateAll));
  document.querySelector('#junkCalculate')?.addEventListener('click', calculateJunkSilver);
  document.querySelector('#silverCalculate')?.addEventListener('click', calculateSilverValue);
  document.querySelector('#breakevenCalculate')?.addEventListener('click', calculateBreakEven);
}

function setupContactForm() {
  const form = document.querySelector('#contactForm');
  const note = document.querySelector('#formNote');
  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    const subjectReason = data.reason ? ` — ${data.reason}` : '';
    const subject = `Website inquiry${subjectReason}`;
    const lines = [
      `Name: ${data.name || ''}`,
      `Email: ${data.email || ''}`,
      `Phone: ${data.phone || ''}`,
      `Reason: ${data.reason || ''}`,
      '',
      data.message || '',
    ];
    const body = lines.join('\n');
    const href = `mailto:carsoncity1889@gmail.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    window.location.href = href;
    note.textContent = 'Your email app should open with this request addressed to Carson City Trade.';
    note.classList.add('success');
  });
}

function setupMenu() {
  els.menuButton?.addEventListener('click', () => {
    const open = els.navLinks.classList.toggle('open');
    els.menuButton.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  els.navLinks?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    els.navLinks.classList.remove('open');
    els.menuButton?.setAttribute('aria-expanded', 'false');
  }));
}

setupMenu();
setupCalculators();
setupContactForm();
renderPrices();
refreshPrices();
setInterval(refreshPrices, 10 * 60 * 1000);
els.refreshPrices?.addEventListener('click', refreshPrices);
