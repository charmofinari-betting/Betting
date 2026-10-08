"""The sheet formulas for the new Sheet1 layout. Single source of truth: the
migration writes exactly these.

New Sheet1 (header row 2, data from row 3):
  A ID  B Kickoff  C Sport  D Country  E League  F Home  G Away  H Market  I Period
  J Side  K Line  L Selection (as sent)  M Tip odds  N Score  O Result  P Status
  Q Closing odds  R Notes
Calc keeps its old columns (row n+1 mirrors Sheet1 row n+2) so Positions and
Dashboard keep working; only its formulas change.
"""

# Row guard: a Sheet1 row exists when it has an ID.
_G = 'Sheet1!A3:A=""'

SHEET1_STATUS = {
    "P3": '=ARRAYFORMULA(IF(A3:A="",,IF(TRIM(O3:O)<>"","Settled",IF(B3:B="","No kickoff",'
          'IF(B3:B+2.5/24<NOW(),"Needs result",IF(B3:B<NOW(),"In play","Upcoming"))))))',
}

CALC = {
    # Kickoff, Kickoff day
    "A2": f'=ARRAYFORMULA(IF({_G},,IF(Sheet1!B3:B="",,Sheet1!B3:B)))',
    "B2": '=ARRAYFORMULA(IF(F2:F="",,IF(A2:A="",,INT(A2:A))))',
    # Sport (written by the script; "Unmapped" if missing)
    "C2": f'=ARRAYFORMULA(IF({_G},,IF(Sheet1!C3:C="","Unmapped",Sheet1!C3:C)))',
    # Country, League
    "D2": f'=ARRAYFORMULA(IF({_G},,Sheet1!D3:E))',
    # Match, Selection (as sent)
    "F2": f'=ARRAYFORMULA(IF({_G},,Sheet1!F3:F&" vs "&Sheet1!G3:G))',
    "G2": f'=ARRAYFORMULA(IF({_G},,Sheet1!L3:L))',
    # Bet type (market group)
    "H2": f'''=ARRAYFORMULA(LET(mk,Sheet1!H3:H,pd,Sheet1!I3:I,IF({_G},,
IF(mk="Total",IF(pd="1H","Total (1st half)","Total"),
IF(REGEXMATCH(mk,"team total$"),"Team goals",
IF(REGEXMATCH(mk,"half|halves"),"Half markets",
mk))))))''',
    # Odds, Result, Units P&L, Status
    "I2": f'=ARRAYFORMULA(IF({_G},,Sheet1!M3:M))',
    "J2": f'=ARRAYFORMULA(IF({_G},,PROPER(TRIM(Sheet1!O3:O))))',
    "K2": f'''=ARRAYFORMULA(LET(r,PROPER(TRIM(Sheet1!O3:O)),o,Sheet1!M3:M,IF({_G},,
IF(r="Won",o-1,IF(r="Lost",-1,IF(r="Half Won",(o-1)/2,IF(r="Half Lost",-0.5,
IF(REGEXMATCH(r,"^(Void|Push|Refund|Cancelled)$"),0,))))))))''',
    "L2": f'=ARRAYFORMULA(IF({_G},,IF(TRIM(Sheet1!O3:O)="","Pending","Settled")))',
    # Market (detail) — same labels as parse.market_detail
    "M2": f'''=ARRAYFORMULA(LET(mk,Sheet1!H3:H,pd,Sheet1!I3:I,sd,Sheet1!J3:J,ln,Sheet1!K3:K,bk,Sheet1!C3:C="Basketball",IF({_G},,
IF(mk="Handicap",IF(pd="1H",IF(bk,"1st-half spread","1st-half Asian handicap"),
  IF(bk,IF(ln<0,"Spread - favourite","Spread - underdog"),
  IF(ln=0,"Draw no bet (0.0)",IF(ln<0,"Asian handicap - giving","Asian handicap - getting")))),
IF(mk="Total",IF(pd="1H","1st-half "&sd,IF(bk,"Points ","Goals ")&sd),
IF(REGEXMATCH(mk,"team total$"),"Team goals "&sd&IF(pd="1H"," (1st half)",""),
IF(mk="BTTS",IF(pd="2H","BTTS 2nd half","BTTS "&sd),
IF((mk="Corners")+(mk="Cards"),mk&" "&sd,
mk))))))))''',
    # Side, Position (match | side). Side keeps the old grouping: team-total Overs
    # count as that team's side, Unders as Under; Cards and Corners are their own side.
    "N2": f'''=ARRAYFORMULA(LET(mk,Sheet1!H3:H,sd,Sheet1!J3:J,s,
IF(mk="Cards","Cards",IF(mk="Corners","Corners",IF(mk="BTTS","BTTS "&sd,
IF(REGEXMATCH(mk,"team total$"),IF(sd="Under","Under",LEFT(mk,4)),sd)))),
HSTACK(IF({_G},,s),IF({_G},,Sheet1!F3:F&" vs "&Sheet1!G3:G&" | "&s))))''',
    # Odds band
    "P2": f'''=ARRAYFORMULA(LET(o,Sheet1!M3:M,IF({_G},,IF(o<1.7,"1) under 1.70",IF(o<2,"2) 1.70-1.99",
IF(o<2.5,"3) 2.00-2.49",IF(o<3.5,"4) 2.50-3.49","5) 3.50+")))))))''',
}

DASHBOARD = {
    # "Needs result" count now reads the new Status column (was Sheet1!H3:H)
    "D6": '=COUNTIF(Sheet1!P3:P,"Needs result")',
}
