# Spec: Account holders (Pat and Tish) in the Private Betting book

Status: **approved and built 11 Oct 2026** (steps 1-4: accounts, deposits, fee, Holders tab, Dashboard split, first slips S-0056 Tish and S-0057 Pat). Step 5 (funds-dashboard Holder filter) handed to that session.

## 1. Facts so far (from Paolo, 11 Oct)
- It is **Paolo's money**. Pat and Tish only hold the accounts and place the bets themselves, from Paolo's picks.
- Pat: **msw.ph**. Tish: **bet88** (a separate account from Paolo's own bet88). PHP only.
- Funded 11 Oct: Pat ₱5,200 (₱5,000 + ₱200 processing fee), Tish ₱5,000.
- They send Paolo **slip screenshots**; he logs them with log-bets.
- Draft deal, **not final, to be decided later**: each holder gets max(₱5,000, 10% of net result) per month. Net result = money out minus money in (exact definition open). Period, payout mechanics and what they can see are all undecided. Rules are loose between close friends; the sheet records now, decides later.

## 2. Recommendation: same sheet, holder-tagged
Use the existing Private Betting book. Do **not** create a separate sheet now.

Why:
- No third-party money, so there is no pot to wall off. "Pot" stays Paolo; only "Holder" and "Placed by" change.
- The columns already exist (Accounts.Holder, Bets.Placed by). No restructure.
- One sheet means one set of tools: log-bets, book_sync, positions, projections, tip links, funds dashboard. Their picks are Paolo's picks, so tip-ID links and drift analysis stay valid.
- One true view of Paolo's total exposure and capital, including money sitting in friends' accounts.

Cost: Paolo's own figures (cash, ROI, capital baseline) would get mixed with holder accounts unless filtered. Fixed in section 4 by splitting on Holder.
Exposure: the sheet stays private. Pat and Tish are never added to it. If they ever need numbers, give them a separate read-only view (section 6), never the book.

What would change the recommendation:
- Their own money enters an account → separate pot, probably a separate sheet.
- They need to see or edit anything in the book → separate holder-facing sheet.
- Holder accounts outgrow Paolo's own and clutter the main view → split then; the tools take a sheet key, so it is cheap to move.

## 3. Sheet structure (minimal)
- **Accounts:** add rows `msw.ph Pat` (book msw.ph, holder Pat, PHP) and `bet88 Tish` (book bet88, holder Tish, PHP). Account names must be unique, hence the holder suffix.
- **Ledger:** one `Deposit` per account for the funding that actually landed (Pot = Paolo). Withdrawals back to Paolo, and top-ups, are `Withdrawal` / `Deposit` lines when he tells me.
- **Bets:** `Placed by` = Pat or Tish, `Pot` = Paolo, `Account` = their account. Add Pat and Tish to the Placed-by dropdown.
- **Costs:** the ₱200 processing fee goes in Costs (kind: holder funding fee), not into stake or capital. Later payouts to holders also go in Costs (kind: holder payout), so they count against profit.
- **Holders (new tab):** one row per holder: holder, account, start date, funded to date, deal text (free text, as agreed), and computed **net result** = balance + withdrawals − deposits − opening, plus a column "10% of net" and "Floor". It computes the numbers but pays nothing and enforces nothing. The deal terms are editable cells so changing them later is easy.
- **Balances / Dashboard:** add a Holder column to Balances; Dashboard splits **Own accounts** vs **Holder accounts** (balance, open stakes, P&L, ROI). Paolo's capital baseline and profit figures stay on own accounts only, as now, with holder-account money shown on its own line.

## 4. Capital treatment (to confirm)
Funding Pat and Tish is not a loss: it is Paolo's money sitting in their accounts. In the "profit" view I would count it as capital deployed in holder accounts (their balance + open stakes + withdrawals counts as value) and show the ₱10,000 as funded, not as new outside deposits. Simplest rule: **holder-account deposits are Transfers from Paolo's cash, not new capital.** Needs his OK.

## 5. Logging
- Pat/Tish send screenshots → log-bets as now, with account and Placed-by set. Dry run first.
- Risk: msw.ph slips may not parse yet. First slip is a dry run and may need a small parser addition.
- Results still come from the shared tips sheet via book_sync; no change.

## 6. Visibility (open)
Default: nothing shared. If wanted later: a generated read-only holder view with only their balance, month-to-date net result and what they are owed. Not built now.

## 7. Open decisions (Paolo: later is fine)
Month definition; payout timing and method; net-result definition (bonuses, fees, mid-month top-ups, loss carry-forward); whether to add a soft per-account loss limit; whether they see numbers.

## 8. Build steps (after approval)
1. Confirm the actual amounts that landed in each account (₱5,000 each?), and capital treatment (section 4).
2. Dry run, then add the two Accounts rows, two Ledger deposits, the ₱200 Costs row, and Placed-by dropdown values.
3. Add Holders tab and Holder column on Balances; Dashboard split. Dry run each.
4. First holder slip through log-bets (dry run); parser tweak for msw.ph if needed.
5. Tell the funds-dashboard session to filter on Holder.
