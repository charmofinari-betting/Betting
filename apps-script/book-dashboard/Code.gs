/**
 * Book dashboard web app (Paolo's own Google account; deploy: Execute as me, access only myself).
 * Read-only: it never writes to the sheet. Setup and updates: README.md in this folder.
 */

var BOOK_KEY = '1zfPQqyLsFtFoDkluO4R7was3wyh5au6jV1Eyayykxdg';

function readTab(book, name, cols) {
  var ws = book.getSheetByName(name);
  if (!ws) return [new Array(cols).fill('')];
  return ws.getRange(1, 1, Math.max(ws.getLastRow(), 1), cols).getDisplayValues();
}

function doGet() {
  var book = SpreadsheetApp.openById(BOOK_KEY);
  var model = buildModel({
    accounts: readTab(book, 'Accounts', 6),
    balances: readTab(book, 'Balances', 15),
    bets: readTab(book, 'Bets', 25),
    checks: readTab(book, 'Balance checks', 7)
  }, new Date());
  model.opened = Utilities.formatDate(new Date(), 'Asia/Manila', 'd MMM yyyy HH:mm');
  var t = HtmlService.createTemplateFromFile('Index');
  t.modelJson = JSON.stringify(model).replace(/</g, '\\u003c');
  return t.evaluate()
    .setTitle('Books')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}
