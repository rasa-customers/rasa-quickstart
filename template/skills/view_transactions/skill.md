---
name: View Transactions
description: >
  Show recent transactions for one of the customer's accounts (checking or
  savings). Activate only when the customer clearly asks about spending
  history, recent charges, transactions, or statement activity.
tool_constraints:
  - get_recent_transactions:
      requires: session.view_transactions.selected_account_id
---

Help the customer view recent transactions on one account. Do not invent
merchants, amounts, dates, account ids, or transaction ids.

1. Call `fetch_accounts` to load the customer's accounts. 
2. Present the accounts
(name and last four digits) and ask which one they want recent transactions
for. When they choose, set `selected_account_id` via `set_fields` to the matching
account id from the tool result. If they already named one account clearly
(by name or last four), set `selected_account_id` without re-asking. Do not
invent accounts.
3. Call `get_recent_transactions` for the selected account. 
Once results are available, present the returned rows briefly (date, merchant, amount). 
If the tool returns no rows, say so plainly.
4. Answer any follow up questions regarding the transactions, the user might have.
5. Do not complete the skill until the user is satisfied.

