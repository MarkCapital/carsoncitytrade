const DEFAULT_STATE = {
  gold: 4127.499,
  silver: 61.625,
  source: 'Live prices are temporarily unavailable — showing the last available pricing view',
  updatedAt: null,
};

const state = { ...DEFAULT_STATE };

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

function formatUpdatedAt(value) {
  if (!value) return 'Waiting for the latest market update';
  const updated = new Date(value);
  if (Number.isNaN(updated.getTime())) return 'Waiting for the latest market update';
  return `Updated ${updated.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })}`;
}

function renderPrices() {
  els.goldPrice.textContent = money(state.gold);
  els.silverPrice.textContent = money(state.silver);
  const ratio = Number(state.gold) > 0 && Number(state.silver) > 0 ? Number(state.gold) / Number(state.silver) : 0;
  if (els.goldSilverRatio) els.goldSilverRatio.textContent = ratio ? `${ratio.toFixed(1)}:1` : '—';
  if (els.lastUpdated) els.lastUpdated.textContent = formatUpdatedAt(state.updatedAt);
  if (els.marketStatus) els.marketStatus.textContent = state.source;
  calculateAll();
}

function loadCachedPrices() {
  try {
    const cached = JSON.parse(localStorage.getItem('cctp-price-cache') || 'null');
    if (!cached) return false;
    if (!Number.isFinite(Number(cached.silver)) || !Number.isFinite(Number(cached.gold))) return false;
    Object.assign(state, cached, {
      source: `${cached.source || 'Saved market pricing'} — showing last saved prices`,
    });
    return true;
  } catch {
    return false;
  }
}

async function refreshPrices() {
  if (els.marketStatus) els.marketStatus.textContent = 'Refreshing live spot prices…';
  try {
    const response = await fetch(`./data/prices.json?v=${Date.now()}`, {
      cache: 'no-store',
      headers: { accept: 'application/json' },
    });
    if (!response.ok) throw new Error('snapshot request failed');
    const snapshot = await response.json();
    const silver = Number(snapshot?.spot?.silver);
    const gold = Number(snapshot?.spot?.gold);
    if (!Number.isFinite(silver) || !Number.isFinite(gold) || silver <= 0 || gold <= 0) {
      throw new Error('snapshot returned invalid prices');
    }
    Object.assign(state, {
      silver,
      gold,
      updatedAt: snapshot.updatedAt || new Date().toISOString(),
      source: `Live spot prices • ${snapshot?.spot?.source || 'market feed'}`,
    });
    localStorage.setItem('cctp-price-cache', JSON.stringify(state));
  } catch (error) {
    if (!loadCachedPrices()) {
      Object.assign(state, DEFAULT_STATE, {
        source: 'Live prices are temporarily unavailable — showing the last available pricing view',
      });
    }
  }
  renderPrices();
}

function getSilverSpot() { return Number(state.silver || 0); }
function getValue(selector) { return Number(document.querySelector(selector)?.value || 0); }

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
  const unit = document.querySelector('#silverUnit')?.value || 'toz';
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
  ['#junkFace', '#junkPremium', '#silverWeight', '#silverPurity', '#purchasePrice', '#pureOunces']
    .forEach((selector) => document.querySelector(selector)?.addEventListener('input', calculateAll));
  document.querySelector('#silverUnit')?.addEventListener('change', calculateAll);
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
  els.navLinks?.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
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
