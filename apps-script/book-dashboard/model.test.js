// Run: node --test apps-script/book-dashboard/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ctx = {module: {exports: {}}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'Model.gs'), 'utf8'), ctx);
// JSON round-trip: arrays from the vm context have another realm's prototype, which deepStrictEqual rejects
const buildModel = (d, now) => JSON.parse(JSON.stringify(ctx.module.exports.buildModel(d, now)));

const NOW = new Date(Date.UTC(2026, 9, 19, 6, 0)); // 19 Oct 2026 14:00 PHT

const ACC_HEAD = ['Account', 'Book', 'Holder', 'Currency', 'Status', 'Notes'];
const BAL_HEAD = ['Account', 'Opening', 'Deposits', 'Withdrawals', 'Transfers (net)', 'Bonus / adj.', 'Staked',
  'Returned', 'Balance', 'Open stakes', 'Currency', 'FX now', 'Balance ₱', 'Open stakes ₱', 'Holder'];
const CHK_HEAD = ['Checked at (PHT)', 'Account', 'App balance', 'Expected at check', 'Gap', 'Source', 'Note'];

function acc(name, holder = 'Paolo', cur = 'PHP', status = 'Active') { return [name, '', holder, cur, status, '']; }
function bal(name, balance, open = '0.00', cur = 'PHP', fx = '1.0000') {
  return [name, '', '', '', '', '', '', '', balance, open, cur, fx, '', '', ''];
}
function bet(sid, account, result = 'Open', max = '', maxAt = '', placed = '18 Oct 2026 10:00') {
  const r = new Array(25).fill('');
  r[0] = sid; r[1] = placed; r[2] = account; r[7] = result; r[22] = max; r[23] = maxAt;
  return r;
}
function chk(at, account, gap, app = '100.00', exp = '100.00', note = '') { return [at, account, app, exp, gap, 'id', note]; }

function data({accounts, balances, bets = [], checks = []}) {
  return {
    accounts: [ACC_HEAD, ...accounts],
    balances: [BAL_HEAD, ['TOTAL', '', '', '', '', '', '', '', '', '', '', '', '', '', ''], ...balances],
    bets: [new Array(25).fill('h'), ...bets],
    checks: [CHK_HEAD, ...checks],
  };
}

test('gap of 500 is red and sorted first', () => {
  const m = buildModel(data({
    accounts: [acc('bet88'), acc('1xbet PHP')],
    balances: [bal('bet88', '9,000.12'), bal('1xbet PHP', '0.39')],
    checks: [chk('19 Oct 2026 12:00', 'bet88', '0.00'), chk('19 Oct 2026 12:00', '1xbet PHP', '500.00')],
  }), NOW);
  assert.deepStrictEqual(m.own.map(c => [c.account, c.status]), [['1xbet PHP', 'red'], ['bet88', 'green']]);
  assert.strictEqual(m.own[0].check.gap, 500);
});

test('gap of 0.40 is green', () => {
  const m = buildModel(data({accounts: [acc('bet88')], balances: [bal('bet88', '10.00')],
    checks: [chk('19 Oct 2026 12:00', 'bet88', '-0.40')]}), NOW);
  assert.strictEqual(m.own[0].status, 'green');
});

test('no check is amber; check 4 days old is amber; 2 days old matched is green', () => {
  const m = buildModel(data({
    accounts: [acc('A'), acc('B'), acc('C')],
    balances: [bal('A', '1.00'), bal('B', '1.00'), bal('C', '1.00')],
    checks: [chk('15 Oct 2026 13:00', 'B', '0.00'), chk('17 Oct 2026 14:00', 'C', '0.00')],
  }), NOW);
  const s = Object.fromEntries(m.own.map(c => [c.account, c.status]));
  assert.deepStrictEqual(s, {A: 'amber', B: 'amber', C: 'green'});
  assert.strictEqual(m.own.find(c => c.account === 'C').check.ageDays, 2);
});

test('latest check per account wins', () => {
  const m = buildModel(data({accounts: [acc('bet88')], balances: [bal('bet88', '1.00')],
    checks: [chk('18 Oct 2026 09:00', 'bet88', '250.00'), chk('19 Oct 2026 09:00', 'bet88', '0.00')]}), NOW);
  assert.strictEqual(m.own[0].status, 'green');
});

test('a re-check with the same time: the later sheet row wins', () => {
  const m = buildModel(data({accounts: [acc('bet88')], balances: [bal('bet88', '1.00')],
    checks: [chk('19 Oct 2026 09:00', 'bet88', '-5000.00'), chk('19 Oct 2026 09:00', 'bet88', '0.00')]}), NOW);
  assert.strictEqual(m.own[0].status, 'green');
});

test('a red card is never hidden, even on an inactive empty account', () => {
  const m = buildModel(data({accounts: [acc('winzir', 'Paolo', 'PHP', 'Closed')], balances: [bal('winzir', '0.00')],
    checks: [chk('19 Oct 2026 12:00', 'winzir', '300.00')]}), NOW);
  assert.deepStrictEqual(m.own.map(c => [c.account, c.status]), [['winzir', 'red']]);
  assert.deepStrictEqual(m.empty, []);
});

test('holder accounts are grouped under the holder and excluded from summary.cash', () => {
  const m = buildModel(data({
    accounts: [acc('bet88'), acc('msw.ph Pat', 'Pat'), acc('bet88 Tish', 'Tish')],
    balances: [bal('bet88', '1,000.00', '200.00'), bal('msw.ph Pat', '36,000.84', '22,749.00'), bal('bet88 Tish', '5.00')],
  }), NOW);
  assert.strictEqual(m.summary.cash, 1000);
  assert.strictEqual(m.summary.openStakes, 200);
  assert.deepStrictEqual(Object.keys(m.holders).sort(), ['Pat', 'Tish']);
  assert.strictEqual(m.holders.Pat.summary.cash, 36000.84);
  assert.strictEqual(m.holders.Pat.summary.openStakes, 22749);
  assert.deepStrictEqual(m.own.map(c => c.account), ['bet88']);
});

test('crypto card stays in native units', () => {
  const m = buildModel(data({accounts: [acc('bet88'), acc('1xbet TRX', 'Paolo', 'TRX')],
    balances: [bal('bet88', '10.00'), bal('1xbet TRX', '0.84', '0.00', 'TRX', '21.0800')]}), NOW);
  assert.strictEqual(m.crypto.length, 1);
  assert.strictEqual(m.crypto[0].expected, 0.84);
  assert.strictEqual(m.crypto[0].currency, 'TRX');
  assert.strictEqual(m.summary.cash, 10);
});

test('inactive empty account goes to empty', () => {
  const m = buildModel(data({accounts: [acc('winzir', 'Paolo', 'PHP', 'Closed'), acc('bet88')],
    balances: [bal('winzir', '0.00'), bal('bet88', '1.00')]}), NOW);
  assert.deepStrictEqual(m.own.map(c => c.account), ['bet88']);
  assert.deepStrictEqual(m.empty.map(c => c.account), ['winzir']);
});

test('maxReturn sums Bets W for open own PHP tickets; maxReturnAt is the newest X', () => {
  const m = buildModel(data({
    accounts: [acc('Solaire'), acc('msw.ph Pat', 'Pat')],
    balances: [bal('Solaire', '1.00', '6,489.00'), bal('msw.ph Pat', '1.00', '6,000.00')],
    bets: [bet('S-1', 'Solaire', 'Open', '25996.45', '19 Oct 2026 10:15'),
      bet('S-2', 'Solaire', 'Open', '9250.00', '19 Oct 2026 17:40'),
      bet('S-3', 'msw.ph Pat', 'Open', '31731.06', '19 Oct 2026 11:00'),
      bet('S-4', 'Solaire', 'Lost')],
  }), NOW);
  assert.strictEqual(m.summary.maxReturn, 35246.45);
  assert.strictEqual(m.summary.maxReturnAt, '19 Oct 2026 17:40');
  assert.strictEqual(m.own[0].openTickets, 2);
  assert.strictEqual(m.holders.Pat.summary.maxReturn, 31731.06);
});

test('books matched counts own green cards out of own shown cards', () => {
  const m = buildModel(data({accounts: [acc('A'), acc('B'), acc('1xbet TRX', 'Paolo', 'TRX')],
    balances: [bal('A', '1.00'), bal('B', '1.00'), bal('1xbet TRX', '0.84', '0.00', 'TRX')],
    checks: [chk('19 Oct 2026 12:00', 'A', '0.00')]}), NOW);
  assert.deepStrictEqual([m.summary.matched, m.summary.total], [1, 3]);
});

test('an active account at 0 with nothing open goes to empty, and still counts in books matched', () => {
  const m = buildModel(data({accounts: [acc('A'), acc('B')], balances: [bal('A', '5.00'), bal('B', '0.00')],
    checks: [chk('19 Oct 2026 12:00', 'A', '0.00'), chk('19 Oct 2026 12:00', 'B', '0.00')]}), NOW);
  assert.deepStrictEqual(m.own.map(c => c.account), ['A']);
  assert.deepStrictEqual(m.empty.map(c => c.account), ['B']);
  assert.deepStrictEqual([m.summary.matched, m.summary.total], [2, 2]);
});

test('an active account at 0 but with open stakes stays in its list', () => {
  const m = buildModel(data({accounts: [acc('A')], balances: [bal('A', '0.00', '500.00')]}), NOW);
  assert.deepStrictEqual(m.own.map(c => c.account), ['A']);
  assert.deepStrictEqual(m.empty, []);
});

test('a red card at 0 is never moved to empty', () => {
  const m = buildModel(data({accounts: [acc('A')], balances: [bal('A', '0.00')],
    checks: [chk('19 Oct 2026 12:00', 'A', '250.00')]}), NOW);
  assert.deepStrictEqual(m.own.map(c => c.account), ['A']);
  assert.deepStrictEqual(m.empty, []);
});

// Balances columns: B Opening, C Deposits, D Withdrawals, E Transfers, F Bonus, G Staked, H Returned, I Balance, J Open stakes
function mbal(name, o, dep, wd, tr, bon, staked, ret, balance, open, cur = 'PHP') {
  return [name, o, dep, wd, tr, bon, staked, ret, balance, open, cur, '1.0000', '', '', ''];
}

test('money card: deposits include opening; result is settled only; ties to cash', () => {
  // 17,000 in, 260.54 bonus, staked 9,000 of which 4,300 still open, returned 5,450.45 -> settled result +750.45
  const m = buildModel(data({accounts: [acc('1xbet PHP')],
    balances: [mbal('1xbet PHP', '15,000.00', '2,000.00', '0.00', '0.00', '260.54', '9,000.00', '5,450.45', '13,710.99', '4,300.00')]}), NOW);
  const c = m.money.own[0];
  assert.deepStrictEqual([c.account, c.deposits, c.withdrawals, c.bonus, c.result, c.openStakes, c.cash],
    ['1xbet PHP', 17000, 0, 260.54, 750.45, 4300, 13710.99]);
  assert.strictEqual(Math.round((c.deposits - c.withdrawals + c.transfers + c.bonus + c.result - c.openStakes) * 100) / 100, c.cash);
});

test('money: own PHP totals; crypto in own units; holders apart; all-zero accounts left out', () => {
  const m = buildModel(data({
    accounts: [acc('bet88'), acc('Solaire'), acc('1xbet USDT', 'Paolo', 'USDT'), acc('msw.ph Pat', 'Pat'), acc('unused')],
    balances: [mbal('bet88', '0.00', '30,000.00', '20,000.00', '0.00', '0.00', '2,000.00', '101.00', '8,101.00', '0.00'),
      mbal('Solaire', '3,000.00', '0.00', '0.00', '0.00', '0.00', '1,000.00', '0.10', '2,000.10', '0.00'),
      mbal('1xbet USDT', '100.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '100.00', '0.00', 'USDT'),
      mbal('msw.ph Pat', '3,000.00', '0.00', '0.00', '0.00', '0.00', '0.00', '200.00', '3,200.00', '0.00'),
      mbal('unused', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00')],
  }), NOW);
  assert.deepStrictEqual(m.money.own.map(c => c.account), ['Solaire', 'bet88']);
  assert.deepStrictEqual(m.money.summary, {deposits: 33000, withdrawals: 20000, result: -2898.9, cash: 10101.1});
  assert.deepStrictEqual(m.money.crypto.map(c => [c.account, c.deposits, c.currency]), [['1xbet USDT', 100, 'USDT']]);
  assert.deepStrictEqual(Object.keys(m.money.holders), ['Pat']);
  assert.strictEqual(m.money.holders.Pat.cards[0].result, 200);
  assert.strictEqual(m.money.holders.Pat.summary.cash, 3200);
});

test('money: an emptied account that withdrew everything still shows', () => {
  const m = buildModel(data({accounts: [acc('A')],
    balances: [mbal('A', '0.00', '1,000.00', '1,000.00', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00')]}), NOW);
  assert.deepStrictEqual(m.money.own.map(c => c.account), ['A']);
});
