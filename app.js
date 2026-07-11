const DEFAULT_STATE = {
  gold: 4127.499,
  silver: 61.625,
  source: 'Live market pricing',
  updatedAt: null,
  notes: [],
  status: 'Loading current metals prices…',
};

const JUNK_SILVER_COINS = {
  dimes: { label: 'Dimes', face: 0.10, silverOzt: 0.0715 },
  quarters: { label: 'Quarters', face: 0.25, silverOzt: 0.17875 },
  halves: { label: 'Half dollars', face: 0.50, silverOzt: 0.3575 },
  dollars: { label: 'Morgan / Peace dollars', face: 1.0, silverOzt: 0.77344 },
};

const state = {
  ...DEFAULT_STATE,
  junkMode: 'face',
};

const els = {
  goldPrice: document.querySelector('#goldPrice'),
  silverPrice: document.querySelector('#silverPrice'),
  goldSilverRatio: document.querySelector('#goldSilverRatio'),
  junkFaceSpot: document.querySelector('#junkFaceSpot'),
  marketStatus: document.querySelector('#marketStatus'),
  marketSource: document.querySelector('#marketSource'),
  lastUpdated: document.querySelector('#lastUpdated'),
  refreshPrices: document.querySelector('#refreshPrices'),
  menuButton: document.querySelector('.menu-button'),
  navLinks: document.querySelector('.nav-links'),
  junkResult: document.querySelector('#junkResult'),
  silverResult: document.querySelector('#silverResult'),
  junkFaceMode: document.querySelector('#junkFaceMode'),
  junkCoinsMode: document.querySelector('#junkCoinsMode'),
};

function money(value, digits = 2) {
  return Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function number(value, digits = 2) {
  return Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatUpdatedAt(value) {
  if (!value) return 'Latest update time unavailable';
  const updated = new Date(value);
  if (Number.isNaN(updated.getTime())) return 'Latest update time unavailable';
  return `Last updated ${updated.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })}`;
}

function cleanSourceLabel(source) {
  if (!source) return 'Live market pricing';
  const cleaned = String(source)
    .split('•')[0]
    .replace(/snapshot/gi, 'pricing')
    .replace(/generated/gi, 'updated')
    .trim();
  if (/Swissquote/i.test(cleaned)) return 'Swissquote market feed';
  return cleaned;
}

function getSilverSpot() {
  return Number(state.silver || 0);
}

function getValue(selector) {
  return Number(document.querySelector(selector)?.value || 0);
}

function renderPrices() {
  const gold = Number(state.gold || 0);
  const silver = Number(state.silver || 0);
  const ratio = gold > 0 && silver > 0 ? gold / silver : 0;
  const junkFaceMelt = silver > 0 ? silver * 0.715 : 0;

  if (els.goldPrice) els.goldPrice.textContent = money(gold);
  if (els.silverPrice) els.silverPrice.textContent = money(silver);
  if (els.goldSilverRatio) els.goldSilverRatio.textContent = ratio ? `${number(ratio, 1)}:1` : '—';
  if (els.junkFaceSpot) els.junkFaceSpot.textContent = junkFaceMelt ? money(junkFaceMelt) : '—';
  if (els.lastUpdated) els.lastUpdated.textContent = formatUpdatedAt(state.updatedAt);
  if (els.marketStatus) els.marketStatus.textContent = state.status;
  if (els.marketSource) {
    els.marketSource.textContent = cleanSourceLabel(state.source);
  }
  calculateAll();
}

function loadCachedPrices() {
  try {
    const cached = JSON.parse(localStorage.getItem('cctp-price-cache') || 'null');
    if (!cached) return false;
    if (!Number.isFinite(Number(cached.silver)) || !Number.isFinite(Number(cached.gold))) return false;
    Object.assign(state, cached, {
      status: 'Showing the most recent saved prices',
      source: cached.source || 'Recent market pricing',
      notes: cached.notes || ['Refresh again in a moment for the latest market update.'],
    });
    return true;
  } catch {
    return false;
  }
}

async function refreshPrices() {
  if (els.marketStatus) els.marketStatus.textContent = 'Refreshing prices…';
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
      source: snapshot?.spot?.source || 'Live market pricing',
      notes: Array.isArray(snapshot?.notes) ? snapshot.notes : [],
      status: 'Prices updated',
    });
    localStorage.setItem('cctp-price-cache', JSON.stringify({
      gold: state.gold,
      silver: state.silver,
      updatedAt: state.updatedAt,
      source: state.source,
      notes: state.notes,
    }));
  } catch (error) {
    if (!loadCachedPrices()) {
      Object.assign(state, DEFAULT_STATE, {
        status: 'Live prices are unavailable right now',
        notes: ['Please try the refresh button again in a moment.'],
      });
    }
  }
  renderPrices();
}

function convertToTroyOunces(weight, unit) {
  if (unit === 'grams') return weight / 31.1034768;
  if (unit === 'avoirdupois') return weight * 0.911458333;
  return weight;
}

function setJunkMode(mode) {
  state.junkMode = mode === 'coins' ? 'coins' : 'face';
  document.querySelectorAll('[data-junk-mode]').forEach((button) => {
    button.classList.toggle('active', button.dataset.junkMode === state.junkMode);
    button.setAttribute('aria-pressed', button.dataset.junkMode === state.junkMode ? 'true' : 'false');
  });
  els.junkFaceMode?.classList.toggle('hidden', state.junkMode !== 'face');
  els.junkCoinsMode?.classList.toggle('hidden', state.junkMode !== 'coins');
  calculateJunkSilver();
}

function getCoinCounts() {
  return {
    dimes: getValue('#junkDimes'),
    quarters: getValue('#junkQuarters'),
    halves: getValue('#junkHalves'),
    dollars: getValue('#junkDollars'),
  };
}

function renderJunkResult({ melt, total, premium, pureOunces, faceValue, breakdown, entryLabel }) {
  const premiumLabel = premium > 0 ? `${number(premium, 1)}% premium added` : 'No premium added';
  const breakdownHtml = breakdown.length
    ? `<div class="result-subgrid">${breakdown.map((item) => `<span>${item}</span>`).join('')}</div>`
    : '';

  els.junkResult.innerHTML = `
    <strong>${money(total)}</strong>
    <span class="result-kicker">${entryLabel} • ${premiumLabel}</span>
    <div class="result-subgrid">
      <span>Melt value: ${money(melt)}</span>
      <span>Pure silver: ${number(pureOunces, 4)} troy oz</span>
      <span>Face value: ${money(faceValue)}</span>
      <span>Silver spot used: ${money(getSilverSpot())}/oz</span>
    </div>
    ${breakdownHtml}
  `;
}

function calculateJunkSilver() {
  const premium = getValue('#junkPremium');
  const spot = getSilverSpot();
  if (spot <= 0) {
    els.junkResult.innerHTML = 'Silver spot is unavailable. Refresh the metals board to calculate junk silver.';
    return;
  }

  if (state.junkMode === 'face') {
    const face = getValue('#junkFace');
    if (face <= 0) {
      els.junkResult.innerHTML = 'Enter a face value to estimate 90% silver melt.';
      return;
    }
    const pureOunces = face * 0.715;
    const melt = pureOunces * spot;
    const total = melt * (1 + premium / 100);
    renderJunkResult({
      melt,
      total,
      premium,
      pureOunces,
      faceValue: face,
      breakdown: [`${money(spot * 0.715)} per $1 face value`],
      entryLabel: `${money(face)} face value`,
    });
    return;
  }

  const counts = getCoinCounts();
  const entries = Object.entries(counts)
    .filter(([, qty]) => qty > 0)
    .map(([key, qty]) => ({
      key,
      qty,
      ...JUNK_SILVER_COINS[key],
    }));

  if (!entries.length) {
    els.junkResult.innerHTML = 'Enter coin counts to estimate mixed junk silver melt.';
    return;
  }

  const pureOunces = entries.reduce((sum, entry) => sum + entry.qty * entry.silverOzt, 0);
  const faceValue = entries.reduce((sum, entry) => sum + entry.qty * entry.face, 0);
  const melt = pureOunces * spot;
  const total = melt * (1 + premium / 100);
  const breakdown = entries.map((entry) => `${entry.qty} ${entry.label} • ${number(entry.qty * entry.silverOzt, 4)} troy oz silver`);

  renderJunkResult({
    melt,
    total,
    premium,
    pureOunces,
    faceValue,
    breakdown,
    entryLabel: 'Coin count estimate',
  });
}

function calculateSilverValue() {
  const weight = getValue('#silverWeight');
  const quantity = Math.max(1, getValue('#silverQuantity') || 1);
  const purityPercent = getValue('#silverPurity');
  const purity = purityPercent / 100;
  const unit = document.querySelector('#silverUnit')?.value || 'toz';
  const spot = getSilverSpot();

  if (spot <= 0) {
    els.silverResult.innerHTML = 'Silver spot is unavailable. Refresh the metals board to calculate melt value.';
    return;
  }
  if (weight <= 0 || purity <= 0) {
    els.silverResult.innerHTML = 'Enter weight and purity to estimate silver value.';
    return;
  }

  const perItemTroy = convertToTroyOunces(weight, unit);
  const totalTroy = perItemTroy * quantity;
  const pureOunces = totalTroy * purity;
  const totalValue = pureOunces * spot;
  const perItemValue = totalValue / quantity;

  els.silverResult.innerHTML = `
    <strong>${money(totalValue)}</strong>
    <span class="result-kicker">${quantity} item${quantity === 1 ? '' : 's'} • ${number(purityPercent, 1)}% silver</span>
    <div class="result-subgrid">
      <span>Per item: ${money(perItemValue)}</span>
      <span>Total pure silver: ${number(pureOunces, 4)} troy oz</span>
      <span>Total gross weight: ${number(totalTroy, 4)} troy oz</span>
      <span>Silver spot used: ${money(spot)}/oz</span>
    </div>
  `;
}

function calculateAll() {
  calculateJunkSilver();
  calculateSilverValue();
}

function setupPurityPresets() {
  document.querySelectorAll('.preset-chip').forEach((button) => {
    button.addEventListener('click', () => {
      const purity = button.dataset.purity;
      const input = document.querySelector('#silverPurity');
      if (!input || !purity) return;
      input.value = purity;
      document.querySelectorAll('.preset-chip').forEach((chip) => chip.classList.remove('active'));
      button.classList.add('active');
      calculateSilverValue();
    });
  });

  document.querySelector('#silverPurity')?.addEventListener('input', () => {
    const purity = String(document.querySelector('#silverPurity')?.value || '');
    document.querySelectorAll('.preset-chip').forEach((chip) => {
      chip.classList.toggle('active', chip.dataset.purity === purity);
    });
  });
}

function setupCalculators() {
  ['#junkFace', '#junkPremium', '#junkDimes', '#junkQuarters', '#junkHalves', '#junkDollars', '#silverWeight', '#silverPurity', '#silverQuantity']
    .forEach((selector) => document.querySelector(selector)?.addEventListener('input', calculateAll));

  document.querySelector('#silverUnit')?.addEventListener('change', calculateSilverValue);
  document.querySelector('#junkCalculate')?.addEventListener('click', calculateJunkSilver);
  document.querySelector('#silverCalculate')?.addEventListener('click', calculateSilverValue);
  document.querySelectorAll('[data-junk-mode]').forEach((button) => {
    button.addEventListener('click', () => setJunkMode(button.dataset.junkMode));
  });

  setupPurityPresets();
  setJunkMode('face');
}

function setupContactForm() {
  const form = document.querySelector('#contactForm');
  const note = document.querySelector('#formNote');
  const submitButton = form?.querySelector('button[type="submit"]');
  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    const subjectReason = data.reason ? ` — ${data.reason}` : '';
    formData.set('_subject', `Carson City Trading Post website inquiry${subjectReason}`);
    submitButton?.setAttribute('disabled', 'disabled');
    if (note) {
      note.textContent = 'Sending your request…';
      note.classList.remove('success');
    }
    try {
      const response = await fetch('https://formsubmit.co/ajax/21d37ea7857eedb26aeff4c6472d93ed', {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: formData,
      });
      if (!response.ok) throw new Error('request failed');
      if (note) {
        note.textContent = 'Thanks — your request was sent directly to Carson City Trading Post.';
        note.classList.add('success');
      }
      form.reset();
    } catch (error) {
      if (note) {
        note.textContent = 'There was a problem sending your request. Please email carsoncity1889@gmail.com directly.';
        note.classList.remove('success');
      }
    } finally {
      submitButton?.removeAttribute('disabled');
    }
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
