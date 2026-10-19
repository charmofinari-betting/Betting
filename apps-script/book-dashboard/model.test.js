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

test('inactive empty account is hidden', () => {
  const m = buildModel(data({accounts: [acc('winzir', 'Paolo', 'PHP', 'Closed'), acc('bet88')],
    balances: [bal('winzir', '0.00'), bal('bet88', '1.00')]}), NOW);
  assert.deepStrictEqual(m.own.map(c => c.account), ['bet88']);
  assert.deepStrictEqual(m.hidden.map(c => c.account), ['winzir']);
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
