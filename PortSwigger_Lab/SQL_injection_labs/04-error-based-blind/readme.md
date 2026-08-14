# SQL Injection: Error-Based Blind Attacks

## Introduction

Boolean-based blind SQLi relies on the app showing *some* visible
difference between a true and a false condition — a message appearing, a
status code changing, response length shifting. But what happens when the
app gives back the exact same response either way, no matter what
condition you inject?

That's where **error-based blind SQL injection** comes in. Instead of
relying on a difference the app already provides, you deliberately force
the database to throw an error on one branch and not the other. The
error itself (usually an HTTP 500) becomes your true/false signal, even
when nothing else about the response changes.

This report covers the technique against an **Oracle** database, using a
`TrackingId` cookie as the injection point, the same as the boolean-blind
lab.

---

## Step 1: Confirm the Injection Context

Oracle uses `||` for string concatenation. The first thing to confirm is
that basic injected SQL runs without breaking anything:

```sql
' || (SELECT '' FROM dual) || '
```

`dual` is Oracle's built-in single-row table, used here purely to confirm
the injection point accepts a subquery without error. A clean response
confirms the syntax and context are correct.

---

## Step 2: Confirm the Target Table Exists

```sql
' || (SELECT '' FROM users WHERE rownum = 1) || '
```

`rownum = 1` limits the subquery to exactly one row, which Oracle requires
for inline scalar subqueries like this. If the `users` table exists, this
returns cleanly. If it doesn't, Oracle throws a "table or view does not
exist" error — giving you table-existence confirmation for free, before
you've even built the error-oracle logic yet.

---

## Step 3: Build the Conditional Error Oracle

This is the core mechanism the rest of the attack depends on. Using
`CASE`, we make the query throw a divide-by-zero error only when a
condition we control is false:

```sql
' || (SELECT CASE WHEN (1=1) THEN '' ELSE TO_CHAR(1/0) END FROM dual) || '
```

Since `1=1` is always true, this always takes the `THEN ''` branch — no
error, confirming the `CASE` structure itself works correctly before using
it against real data.

The logic:
- Condition **true** → `THEN ''` → returns empty string → normal response.
- Condition **false** → `ELSE TO_CHAR(1/0)` → divide-by-zero → Oracle
  throws `ORA-01476` → HTTP 500.

Note this means the oracle is **inverted** compared to what you might
expect: a *false* condition produces the *error*, not the true one. Every
payload after this point uses `WHEN (1=2)` — a condition that's always
false — as a deliberate trick, so the actual truth value comes entirely
from the surrounding `WHERE` clause of the subquery instead: if the
`WHERE` clause matches a row, the `CASE` gets evaluated at all (and always
takes the error branch); if it matches nothing, the `CASE` never runs, and
nothing errors.

---

## Step 4: Confirm a Specific User Exists

```sql
' || (SELECT CASE WHEN (1=2) THEN '' ELSE TO_CHAR(1/0) END FROM users WHERE username='administrator') || '
```

If `administrator` exists, the `WHERE` clause returns a row, the `CASE`
evaluates, and — since `1=2` is always false — it always takes the error
branch → HTTP 500. If no such user exists, the subquery returns zero rows,
the `CASE` never runs, and the response comes back normal.

---

## Step 5: Find the Password Length

**First attempt:**

```sql
' || (SELECT CASE WHEN (1=2) THEN '' ELSE TO_CHAR(1/0) END FROM users WHERE length(password) > 20) || '
```

This works as a proof of concept, but it has a gap: it checks whether
**any** user in the table has a password longer than 20 characters, not
specifically `administrator`. With more than one user in the table, this
gives a misleading result.

**Corrected version:**

```sql
' || (SELECT CASE WHEN (1=2) THEN '' ELSE TO_CHAR(1/0) END FROM users WHERE username='administrator' AND length(password) > 20) || '
```

Adding `username='administrator' AND` scopes the check to the specific
account being targeted. From here, adjust the number and repeat (ideally
with a binary search) until you find the exact length.

---

## Step 6: Extract the Password Character by Character

```sql
' || (SELECT CASE WHEN (1=2) THEN '' ELSE TO_CHAR(1/0) END FROM users WHERE username='administrator' AND SUBSTR(password,1,1) > 'a') || '
```

Same principle as boolean-based extraction: this asks "is the first
character of the password greater than `a`?" using Oracle's `SUBSTR`.
Use a binary search against the character range rather than testing every
character sequentially, and repeat for each position across the full
length of the password.

---

## Automating the Process

As with boolean-based extraction, testing every character position by
hand doesn't scale — this uses the same length-then-binary-search
approach, sending requests programmatically instead of through Burp
Repeater/Intruder. See `error_base_sql.char_BF.py` in this folder for the
working script.

---

## Common Pitfalls

- **Forgetting to scope conditions to the specific user.** As shown in
  Step 5, a `WHERE` clause without a `username=` filter checks the
  condition across the entire table, not the account you're targeting —
  easy to get a false result without noticing.
- **Misreading which branch is "true."** Because this technique
  deliberately inverts the `CASE` logic (`WHEN 1=2` — always false — is
  used as a constant), it's easy to get turned around on which HTTP
  response actually means "condition true." Always confirm with a known
  true/false pair (like Step 3's `dual` test) before trusting results.
- **Assuming `rownum = 1` is optional.** Oracle's scalar subqueries
  require exactly one row. Skipping this on a multi-row table produces a
  different error (`ORA-01427`) that has nothing to do with whether your
  actual condition is true or false — don't mistake it for a real signal.
