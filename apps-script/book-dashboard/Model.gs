/**
 * Book dashboard: page model (pure, no Google services; tested with Node, see model.test.js).
 * Input: sheet ranges as getDisplayValues() returns them, header row included.
 * Spec: game-tracker/SPEC-book-dashboard.md
 */

var MATCH_TOLERANCE = 1.00; // |gap| below this, in the account's own currency, counts as matched
var STALE_DAYS = 3;
var OWNER = 'Paolo';
var BASE_CURRENCY = 'PHP';
var MONTHS = {Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11};

function num(s) {
  var n = parseFloat(String(s).replace(/,/g, '').replace(/^\+/, ''));
  return isNaN(n) ? 0 : n;
}

/** '19 Oct 2026 14:05' (PHT) -> Date, or null. */
function parsePht(s) {
  var m = /^(\d{1,2}) ([A-Z][a-z]{2}) (\d{4})(?: (\d{1,2}):(\d{2}))?$/.exec(String(s).trim());
  if (!m || !(m[2] in MONTHS)) return null;
  return new Date(Date.UTC(+m[3], MONTHS[m[2]], +m[1], (m[4] ? +m[4] : 0) - 8, m[5] ? +m[5] : 0));
}

function newest(times) {
  var best = '', bestT = null;
  times.forEach(function (s) {
    var t = parsePht(s);
    if (t && (!bestT || t > bestT)) { best = s; bestT = t; }
  });
  return best;
}

var RANK = {red: 0, amber: 1, green: 2};

function sortCards(cards) {
  return cards.sort(function (a, b) {
    if (RANK[a.status] !== RANK[b.status]) return RANK[a.status] - RANK[b.status];
    if (a.status === 'red') return Math.abs(b.check.gap) - Math.abs(a.check.gap);
    return a.account < b.account ? -1 : a.account > b.account ? 1 : 0;
  });
}

function r2(x) { return Math.round(x * 100) / 100; }

function addMoney(sum, c) {
  sum.deposits += c.deposits; sum.withdrawals += c.withdrawals; sum.result += c.result; sum.cash += c.cash;
}

function byAccount(a, b) { return a.account < b.account ? -1 : a.account > b.account ? 1 : 0; }

function buildModel(data, now) {
  var latest = {};
  data.checks.slice(1).forEach(function (r) {
    var at = parsePht(r[0]);
    if (!r[1] || !at) return;
    if (!latest[r[1]] || at >= latest[r[1]].t) latest[r[1]] = {t: at, row: r};
  });

  var tickets = {};
  data.bets.slice(1).forEach(function (r) {
    if (!r[0] || r[7] !== 'Open') return;
    var t = tickets[r[2]] || (tickets[r[2]] = {n: 0, max: 0});
    t.n += 1;
    t.max += num(r[22]);
  });

  var bal = {};
  data.balances.slice(2).forEach(function (r) { if (r[0]) bal[r[0]] = r; });

  var model = {summary: {cash: 0, openStakes: 0, maxReturn: 0, maxReturnAt: '', matched: 0, total: 0},
    own: [], crypto: [], holders: {}, empty: [],
    money: {own: [], crypto: [], holders: {}, summary: {deposits: 0, withdrawals: 0, result: 0, cash: 0}},
    newestBet: newest(data.bets.slice(1).map(function (r) { return r[1]; })),
    newestCheck: newest(data.checks.slice(1).map(function (r) { return r[0]; }))};
  model.summary.maxReturnAt = newest(data.bets.slice(1).filter(function (r) { return r[7] === 'Open'; })
    .map(function (r) { return r[23]; }));

  data.accounts.slice(1).forEach(function (a) {
    var name = a[0];
    if (!name || !bal[name]) return;
    var b = bal[name], holder = a[2] || OWNER, currency = a[3] || b[10];
    var t = tickets[name] || {n: 0, max: 0};
    var card = {account: name, holder: holder, currency: currency, expected: num(b[8]), openStakes: num(b[9]),
      openTickets: t.n, maxReturn: Math.round(t.max * 100) / 100, check: null, status: 'amber'};
    var c = latest[name];
    if (c) {
      card.check = {at: c.row[0], app: num(c.row[2]), expectedAtCheck: num(c.row[3]), gap: num(c.row[4]),
        note: c.row[6] || '', ageDays: Math.floor((now - c.t) / 86400000)};
      if (Math.abs(card.check.gap) >= MATCH_TOLERANCE) card.status = 'red';
      else if (card.check.ageDays <= STALE_DAYS) card.status = 'green';
    }
    // Money page card: all from the Balances row. result = settled only (Returned - Staked, with open stakes added back).
    var mc = {account: name, currency: currency, deposits: r2(num(b[1]) + num(b[2])), withdrawals: r2(num(b[3])),
      transfers: r2(num(b[4])), bonus: r2(num(b[5])), result: r2(num(b[7]) - num(b[6]) + num(b[9])),
      openStakes: r2(num(b[9])), cash: r2(num(b[8]))};
    if (mc.deposits || mc.withdrawals || mc.transfers || mc.bonus || mc.result || mc.openStakes || mc.cash) {
      if (holder !== OWNER) {
        var mh = model.money.holders[holder] || (model.money.holders[holder] = {summary: {deposits: 0, withdrawals: 0, result: 0, cash: 0}, cards: []});
        mh.cards.push(mc);
        if (currency === BASE_CURRENCY) addMoney(mh.summary, mc);
      } else if (currency !== BASE_CURRENCY) {
        model.money.crypto.push(mc);
      } else {
        model.money.own.push(mc);
        addMoney(model.money.summary, mc);
      }
    }
    var isEmpty = card.expected === 0 && card.openStakes === 0 && card.status !== 'red';
    if (isEmpty) {
      model.empty.push(card);
      if (a[4] === 'Active' && holder === OWNER) { // active empty books still count; closed ones never did
        model.summary.total += 1;
        if (card.status === 'green') model.summary.matched += 1;
      }
      return;
    }
    if (holder !== OWNER) {
      var h = model.holders[holder] || (model.holders[holder] = {summary: {cash: 0, openStakes: 0, maxReturn: 0}, cards: []});
      h.cards.push(card);
      if (currency === BASE_CURRENCY) {
        h.summary.cash += card.expected;
        h.summary.openStakes += card.openStakes;
        h.summary.maxReturn += card.maxReturn;
      }
      return;
    }
    model.summary.total += 1;
    if (card.status === 'green') model.summary.matched += 1;
    if (currency !== BASE_CURRENCY) {
      model.crypto.push(card);
      return;
    }
    model.own.push(card);
    model.summary.cash += card.expected;
    model.summary.openStakes += card.openStakes;
    model.summary.maxReturn += card.maxReturn;
  });

  ['cash', 'openStakes', 'maxReturn'].forEach(function (k) { model.summary[k] = r2(model.summary[k]); });
  Object.keys(model.holders).forEach(function (h) {
    var s = model.holders[h].summary;
    ['cash', 'openStakes', 'maxReturn'].forEach(function (k) { s[k] = r2(s[k]); });
    sortCards(model.holders[h].cards);
  });
  sortCards(model.own);
  sortCards(model.empty);
  ['deposits', 'withdrawals', 'result', 'cash'].forEach(function (k) { model.money.summary[k] = r2(model.money.summary[k]); });
  model.money.own.sort(byAccount);
  model.money.crypto.sort(byAccount);
  Object.keys(model.money.holders).forEach(function (h) {
    var x = model.money.holders[h];
    ['deposits', 'withdrawals', 'result', 'cash'].forEach(function (k) { x.summary[k] = r2(x.summary[k]); });
    x.cards.sort(byAccount);
  });
  // all PHP pots together = Paolo's money in total (holders' pots are his money too)
  var all = {deposits: 0, withdrawals: 0, result: 0, cash: 0};
  [model.money.summary].concat(Object.keys(model.money.holders).map(function (h) { return model.money.holders[h].summary; }))
    .forEach(function (x) { addMoney(all, x); });
  ['deposits', 'withdrawals', 'result', 'cash'].forEach(function (k) { all[k] = r2(all[k]); });
  model.money.all = all;
  sortCards(model.crypto);
  return model;
}

// ---- Months page: performance per calendar month (PHT). Tickets count in the month they were placed;
// Ledger lines and Costs by their date. PHP pots only (own books = 'Mine', each holder their own pot).
// The 'Month close' tab freezes what was agreed for a month: its result and the next month's opening.

var MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
var MINE = 'Mine';
var MONTH_FIELDS = ['tickets', 'staked', 'result', 'open', 'deposits', 'withdrawals', 'transfers', 'bonus', 'costs'];

/** '31 Oct 2026 23:50' or 'Oct 2026' -> '2026-10', or ''. */
function monthOf(s) {
  var m = /^(?:\d{1,2} )?([A-Z][a-z]{2}) (\d{4})/.exec(String(s).trim());
  if (!m || !(m[1] in MONTHS)) return '';
  return m[2] + '-' + ('0' + (MONTHS[m[1]] + 1)).slice(-2);
}

function monthLabel(key) { return MONTH_NAMES[+key.slice(5) - 1] + ' ' + key.slice(0, 4); }

function prevMonth(key) {
  var y = +key.slice(0, 4), m = +key.slice(5) - 1;
  if (m === 0) { y -= 1; m = 12; }
  return y + '-' + ('0' + m).slice(-2);
}

function emptyPot() {
  var p = {opening: null, close: null, drift: 0};
  MONTH_FIELDS.forEach(function (k) { p[k] = 0; });
  return p;
}

function finishPot(p) {
  MONTH_FIELDS.forEach(function (k) { p[k] = r2(p[k]); });
  p.net = r2(p.result + p.bonus - p.costs);
  p.roi = p.staked ? Math.round(p.result / p.staked * 10000) / 10000 : null;
  return p;
}

function buildMonths(data) {
  var potOf = {}, pots = [MINE];
  data.accounts.slice(1).forEach(function (a) {
    if (!a[0] || (a[3] || BASE_CURRENCY) !== BASE_CURRENCY) return;
    var pot = (a[2] || OWNER) === OWNER ? MINE : a[2];
    potOf[a[0]] = pot;
    if (pots.indexOf(pot) < 0) pots.push(pot);
  });
  var closes = data.closes.slice(1).filter(function (r) { return monthOf(r[0]) && r[1]; });
  closes.forEach(function (r) { if (pots.indexOf(r[1]) < 0) pots.push(r[1]); });

  var months = {};
  function pot(key, name) {
    var m = months[key] || (months[key] = {key: key, label: monthLabel(key), pots: {}});
    pots.forEach(function (p) { if (!m.pots[p]) m.pots[p] = emptyPot(); });
    return m.pots[name];
  }

  data.bets.slice(1).forEach(function (r) {
    var key = monthOf(r[1]), name = potOf[r[2]];
    if (!r[0] || !key || !name) return;
    var p = pot(key, name);
    p.tickets += 1;
    if (r[7] === 'Open' || !r[7]) { p.open += num(r[17]); return; }
    p.staked += num(r[17]);
    p.result += num(r[18]);
  });

  var LEDGER = {'Opening balance': ['deposits', 1], 'Deposit': ['deposits', 1], 'Withdrawal': ['withdrawals', 1],
    'Transfer in': ['transfers', 1], 'Transfer out': ['transfers', -1], 'Bonus': ['bonus', 1], 'Adjustment': ['bonus', 1]};
  data.ledger.slice(1).forEach(function (r) {
    var key = monthOf(r[0]), name = potOf[r[1]], how = LEDGER[r[2]];
    if (!key || !name || !how) return;
    pot(key, name)[how[0]] += how[1] * num(r[3]);
  });

  data.costs.slice(1).forEach(function (r) {
    var key = monthOf(r[0]);
    if (!key || !r[1]) return;
    var named = pots.filter(function (p) { return p !== MINE && new RegExp('\\b' + p + '\\b').test(r[1]); });
    if (!named.length) named = [MINE];
    named.forEach(function (p) { pot(key, p).costs += num(r[4]) / named.length; });
  });

  closes.forEach(function (r) {
    pot(monthOf(r[0]), r[1]).close = {resultAtClose: num(r[2]), costsAtClose: num(r[3]), nextOpening: num(r[4]),
      closedOn: r[5] || '', note: r[6] || ''};
  });

  var out = Object.keys(months).sort().map(function (key) {
    var m = months[key], all = emptyPot();
    pots.forEach(function (name) {
      var p = finishPot(m.pots[name]);
      var before = months[prevMonth(key)];
      if (before && before.pots[name] && before.pots[name].close) p.opening = before.pots[name].close.nextOpening;
      if (p.close) {
        var d = r2(p.result + p.bonus - p.close.resultAtClose);
        p.drift = Math.abs(d) >= 0.01 ? d : 0;
      }
      MONTH_FIELDS.forEach(function (k) { all[k] += p[k]; });
    });
    m.all = finishPot(all);
    delete m.all.opening; delete m.all.close; delete m.all.drift;
    return m;
  });
  return out;
}

if (typeof module !== 'undefined') module.exports = {buildModel: buildModel, buildMonths: buildMonths, parsePht: parsePht};
