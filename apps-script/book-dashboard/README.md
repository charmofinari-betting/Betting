# Book dashboard — setup (Paolo, once)

A read-only page in **your own Google account** that shows a card per sportsbook account. It reads the Private Betting sheet live every time you open it.

## First time (about 5 minutes, on the laptop)
1. Go to https://script.google.com, signed in as **jnplzr@gmail.com** (not a work account) → **New project**. Name it `Book dashboard`.
2. Delete the sample code in `Code.gs` and paste in this folder's `Code.gs`.
3. **+ → Script**, name it `Model`, and paste in `Model.gs`.
4. **+ → HTML**, name it `Index`, and paste in `Index.html`.
5. **Deploy → New deployment →** gear icon → **Web app**.
   - Execute as: **Me**
   - Who has access: **Only myself**
   → **Deploy** → **Authorize access**. It asks to *view* your spreadsheets. Allow it.
6. Copy the **Web app URL**, open it on your phone (signed in to the same Google account), then **Share → Add to Home screen**.

Keep the URL private. Even if it leaks, "Only myself" means nobody else can open the page.

## After an update in the repo
Paste the changed files over the old ones → **Deploy → Manage deployments → ✏️ → Version: New version → Deploy**. The URL stays the same.

## What the colours mean
- **Red**: the last balance you sent differs from what the sheet expected at that moment by ₱1 or more (or 1 unit for crypto). The note says the most likely cause.
- **Amber**: never checked, or the last check is more than 3 days old.
- **Green**: matched, checked within 3 days.

To check a book, screenshot its balance and drop it in Drive **Betting Inbox → Balances**. Holders can use their own Slips folder. Then ask Claude to check the inbox.
