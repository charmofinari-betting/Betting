/**
 * Always-on results fetch for Paolo's betting tracker (Google Apps Script, runs in his account).
 *
 * Twice a day it saves api-sports fixtures for yesterday, today and tomorrow (PHT) into
 * Drive `Betting Inbox/_results`, one raw JSON file per sport per day:
 *   football_2026-10-16.json, basketball_2026-10-16.json
 * Same content as the laptop cache (game-tracker/data/api/<sport>/<date>.json); sync.py pulls
 * them before matching. It never touches the sheet.
 *
 * Setup (once):
 *  1. Project Settings -> Script Properties -> add API_SPORTS_KEY = <the api-sports key>.
 *  2. Run `installTriggers` once and approve the access prompt.
 *  3. Run `fetchResults` once to check; files appear in _results.
 * A failed fetch makes the run throw, so Google emails the failure (trigger notifications).
 * Copy of this file lives in the repo: apps-script/results_fetch.gs.
 */

var RESULTS_FOLDER_ID = '1ikv3MHSqtN9busGPGpNjt7OIxqMfjnO8';
var TZ = 'Asia/Manila';
var ENDPOINTS = {
  football: 'https://v3.football.api-sports.io/fixtures?date={date}&timezone=Asia/Manila',
  basketball: 'https://v1.basketball.api-sports.io/games?date={date}&timezone=Asia/Manila'
};
var RUN_HOURS = [6, 14]; // PHT

function fetchResults() {
  var key = PropertiesService.getScriptProperties().getProperty('API_SPORTS_KEY');
  if (!key) throw new Error('Set API_SPORTS_KEY in Project Settings -> Script Properties');
  var folder = DriveApp.getFolderById(RESULTS_FOLDER_ID);
  var now = new Date();
  var log = {run: Utilities.formatDate(now, TZ, "yyyy-MM-dd'T'HH:mm:ssXXX"), saved: [], skipped: [], failed: []};

  [-1, 0, 1].forEach(function (offset) {
    var date = Utilities.formatDate(new Date(now.getTime() + offset * 86400000), TZ, 'yyyy-MM-dd');
    Object.keys(ENDPOINTS).forEach(function (sport) {
      var name = sport + '_' + date + '.json';
      try {
        var resp = UrlFetchApp.fetch(ENDPOINTS[sport].replace('{date}', date),
          {headers: {'x-apisports-key': key}, muteHttpExceptions: true});
        if (resp.getResponseCode() !== 200) throw new Error('HTTP ' + resp.getResponseCode());
        var text = resp.getContentText();
        var errors = JSON.parse(text).errors;
        if (errors && Object.keys(errors).length) {
          if (errors.plan) { log.skipped.push(name + ': outside free-plan window'); return; }
          throw new Error(JSON.stringify(errors));
        }
        save_(folder, name, text);
        log.saved.push(name);
      } catch (e) {
        log.failed.push(name + ': ' + e.message);
      }
    });
  });

  save_(folder, '_status.json', JSON.stringify(log, null, 1));
  if (log.failed.length) throw new Error('Results fetch failed: ' + log.failed.join('; '));
}

function save_(folder, name, text) {
  var files = folder.getFilesByName(name);
  if (files.hasNext()) files.next().setContent(text);
  else folder.createFile(name, text, 'application/json');
}

function installTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'fetchResults') ScriptApp.deleteTrigger(t);
  });
  RUN_HOURS.forEach(function (h) {
    ScriptApp.newTrigger('fetchResults').timeBased().everyDays(1).atHour(h).inTimezone(TZ).create();
  });
}
