"""The sheet formulas and formatting for the new Sheet1 layout. Single source of
truth: the migration writes exactly these.

New Sheet1 (header row 2, data from row 3):
  A ID  B Kickoff  C Sport  D Country  E League  F Match  G Home  H Away  I Market
  J Period  K Side  L Line  M Selection (as sent)  N Tip odds  O Score  P Result
  Q Status  R Closing odds  S Notes
Calc keeps its old columns (row n+1 mirrors Sheet1 row n+2) so Positions and
Dashboard keep working; only its formulas change.
"""
from parse import MARKETS, PERIODS, SIDES

MARKETS_NEW = ("Home team cards", "Away team cards", "Cards handicap", "Set handicap", "HT/FT")
RESULTS = ("Won", "Lost", "Half Won", "Half Lost", "Void")

# Row guard: a Sheet1 row exists when it has an ID.
_G = 'Sheet1!A3:A=""'

SHEET1_STATUS = {
    "Q3": '=ARRAYFORMULA(IF(A3:A="",,IF(TRIM(P3:P)<>"","Settled",IF(B3:B="","No kickoff",'
          'IF(B3:B+2.5/24<NOW(),"Needs result",IF(B3:B<NOW(),"In play","Upcoming"))))))',
}

CALC = {
    # Kickoff, Kickoff day
    "A2": f'=ARRAYFORMULA(IF({_G},,IF(Sheet1!B3:B="",,Sheet1!B3:B)))',
    "B2": '=ARRAYFORMULA(IF(F2:F="",,IF(A2:A="",,INT(A2:A))))',
    # Sport (written by the script; "Unmapped" if missing)
    "C2": f'=ARRAYFORMULA(IF({_G},,IF(Sheet1!C3:C="","Unmapped",Sheet1!C3:C)))',
    # Country, League, Match
    "D2": f'=ARRAYFORMULA(IF({_G},,Sheet1!D3:F))',
    # Selection (as sent)
    "G2": f'=ARRAYFORMULA(IF({_G},,Sheet1!M3:M))',
    # Bet type (market group)
    "H2": f'''=ARRAYFORMULA(LET(mk,Sheet1!I3:I,pd,Sheet1!J3:J,IF({_G},,
IF(mk="Total",IF(pd="1H","Total (1st half)","Total"),
IF(REGEXMATCH(mk,"team total$"),"Team goals",
IF(REGEXMATCH(mk,"(?i)cards"),"Cards",
IF(REGEXMATCH(mk,"half|halves"),"Half markets",
mk)))))))''',
    # Odds, Result, Units P&L, Status
    "I2": f'=ARRAYFORMULA(IF({_G},,Sheet1!N3:N))',
    "J2": f'=ARRAYFORMULA(IF({_G},,PROPER(TRIM(Sheet1!P3:P))))',
    "K2": f'''=ARRAYFORMULA(LET(r,PROPER(TRIM(Sheet1!P3:P)),o,Sheet1!N3:N,IF({_G},,
IF(r="Won",o-1,IF(r="Lost",-1,IF(r="Half Won",(o-1)/2,IF(r="Half Lost",-0.5,
IF(REGEXMATCH(r,"^(Void|Push|Refund|Cancelled)$"),0,))))))))''',
    "L2": f'=ARRAYFORMULA(IF({_G},,IF(TRIM(Sheet1!P3:P)="","Pending","Settled")))',
    # Market (detail) — same labels as parse.market_detail
    "M2": f'''=ARRAYFORMULA(LET(mk,Sheet1!I3:I,pd,Sheet1!J3:J,sd,Sheet1!K3:K,ln,Sheet1!L3:L,bk,Sheet1!C3:C="Basketball",IF({_G},,
IF(mk="Handicap",IF(pd="1H",IF(bk,"1st-half spread","1st-half Asian handicap"),
  IF(bk,IF(ln<0,"Spread - favourite","Spread - underdog"),
  IF(ln=0,"Draw no bet (0.0)",IF(ln<0,"Asian handicap - giving","Asian handicap - getting")))),
IF(mk="Total",IF(pd="1H","1st-half "&sd,IF(bk,"Points ","Goals ")&sd),
IF(REGEXMATCH(mk,"team total$"),"Team goals "&sd&IF(pd="1H"," (1st half)",""),
IF(mk="BTTS",IF(pd="2H","BTTS 2nd half","BTTS "&sd),
IF((mk="Corners")+(mk="Cards"),mk&" "&sd,
IF(REGEXMATCH(mk,"team cards$"),"Team cards "&sd,
mk)))))))))''',
    # Side, Position (match | side). Side keeps the old grouping: team-total Overs
    # count as that team's side, Unders as Under; Cards (all card markets) and Corners are their own side.
    "N2": f'''=ARRAYFORMULA(LET(mk,Sheet1!I3:I,sd,Sheet1!K3:K,s,
IF(REGEXMATCH(mk,"(?i)cards"),"Cards",IF(mk="Set handicap","Set handicap",IF(mk="HT/FT","HT/FT",IF(mk="Corners","Corners",IF(mk="BTTS","BTTS "&sd,
IF(REGEXMATCH(mk,"team total$"),IF(sd="Under","Under",LEFT(mk,4)),sd)))))),
HSTACK(IF({_G},,s),IF({_G},,Sheet1!F3:F&" | "&s))))''',
    # Odds band
    "P2": f'''=ARRAYFORMULA(LET(o,Sheet1!N3:N,IF({_G},,IF(o<1.7,"1) under 1.70",IF(o<2,"2) 1.70-1.99",
IF(o<2.5,"3) 2.00-2.49",IF(o<3.5,"4) 2.50-3.49","5) 3.50+")))))))''',
}

DASHBOARD = {
    # "Needs result" count now reads the new Status column (was Sheet1!H3:H)
    "D6": '=COUNTIF(Sheet1!Q3:Q,"Needs result")',
}

# Sheet1 formatting, rebuilt from scratch (old rules were tied to old column positions).
# Column index is 0-based; rows 3..1000.
DROPDOWNS = {8: MARKETS, 9: PERIODS, 10: SIDES, 15: RESULTS}  # I Market, J Period, K Side, P Result
STATUS_COL = 16  # Q
STATUS_COLOURS = {  # same colours as the old sheet: (background, text)
    "No kickoff": ({"red": 0.949, "green": 0.949, "blue": 0.949}, {"red": 0.4, "green": 0.4, "blue": 0.4}),
    "In play": ({"red": 1, "green": 0.949, "blue": 0.8}, {"red": 0.549, "green": 0.4, "blue": 0}),
    "Needs result": ({"red": 0.988, "green": 0.847, "blue": 0.847}, {"red": 0.698, "green": 0.047, "blue": 0.047}),
}


def format_requests(sheet_id, existing_rule_count, last_row=1000):
    """Sheets API batchUpdate requests: drop every old colour rule and dropdown on
    Sheet1, then add the new ones."""
    def rng(col):
        return {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": last_row,
                "startColumnIndex": col, "endColumnIndex": col + 1}
    reqs = [{"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": 0}} for _ in range(existing_rule_count)]
    reqs.append({"setDataValidation": {"range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": last_row,
                                                 "startColumnIndex": 0, "endColumnIndex": 26}}})  # no rule = clear
    for col, options in DROPDOWNS.items():
        reqs.append({"setDataValidation": {"range": rng(col), "rule": {
            "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": o} for o in options]},
            "strict": True, "showCustomUi": True}}})
    for i, (text, (bg, fg)) in enumerate(STATUS_COLOURS.items()):
        reqs.append({"addConditionalFormatRule": {"index": i, "rule": {"ranges": [rng(STATUS_COL)], "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": text}]},
            "format": {"backgroundColor": bg, "textFormat": {"foregroundColor": fg, "bold": True}}}}}})
    return reqs

# "Open picks" tab: every pick whose match isn't finished, soonest kickoff first
# (picks without a kickoff sink to the bottom), same-match picks together.
OPEN_PICKS_TAB = "Open picks"
OPEN_PICKS_HEADER = ["Kickoff (PHT)", "Sport", "League", "Match", "Selection", "Tip odds", "Status", "ID"]
OPEN_PICKS = {
    "A2": '''=IFERROR(SORT(FILTER({Sheet1!B3:B,Sheet1!C3:C,Sheet1!E3:E,Sheet1!F3:F,Sheet1!M3:M,Sheet1!N3:N,Sheet1!Q3:Q,Sheet1!A3:A},
(Sheet1!Q3:Q="Upcoming")+(Sheet1!Q3:Q="In play")+(Sheet1!Q3:Q="No kickoff")),1,TRUE,4,TRUE),"No open picks")''',
}
