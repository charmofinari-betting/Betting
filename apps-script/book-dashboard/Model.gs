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
    own: [], crypto: [], holders: {}, hidden: [],
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
    if (card.expected === 0 && card.openStakes === 0 && a[4] !== 'Active' && card.status !== 'red') {
      model.hidden.push(card);
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

  var r2 = function (x) { return Math.round(x * 100) / 100; };
  ['cash', 'openStakes', 'maxReturn'].forEach(function (k) { model.summary[k] = r2(model.summary[k]); });
  Object.keys(model.holders).forEach(function (h) {
    var s = model.holders[h].summary;
    ['cash', 'openStakes', 'maxReturn'].forEach(function (k) { s[k] = r2(s[k]); });
    sortCards(model.holders[h].cards);
  });
  sortCards(model.own);
  sortCards(model.crypto);
  return model;
}

if (typeof module !== 'undefined') module.exports = {buildModel: buildModel, parsePht: parsePht};
