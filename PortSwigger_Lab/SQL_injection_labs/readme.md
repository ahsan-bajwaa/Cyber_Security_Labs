# SQL Injection — A Hands-On Walkthrough Series

This repo is a collection of SQL injection techniques, each one solved hands-on against a real vulnerable lab, documented in plain English on purpose — no jargon-for-the-sake-of-jargon, no assuming you already know what a "boolean oracle" is. If you're new to SQL injection, start here and work down the list in order. If you already know your way around, jump straight to whichever technique you're after.

Every technique folder follows the same shape: a `README.md` covering the theory, a `walkthrough.docx` (In Boolean Blind Attack) covering the exact practical steps taken against the lab, and — where relevant — a Python script that automates the boring, repetitive parts.

## What is SQL Injection?

SQL injection happens when an application takes input from a user and drops it directly into a database query without properly separating "data" from "code." The database can't tell the difference between a tracking ID you typed and a tracking ID that secretly contains SQL instructions — so if you craft your input carefully, you can make the database run commands it was never supposed to run.

The techniques in this repo all exploit that same root cause in different ways, depending on **how much feedback the application gives back**:

- **The response shows data directly** → you can read stolen data straight off the page (UNION-based, error-based visible).
- **The response only changes subtly, or not at all** → you have to ask yes/no questions and infer the answer from a signal like an error, a content difference, or a delay (boolean-blind, error-based blind, time-based blind).
- **The input is filtered or blocked outright** → you have to get creative about disguising the payload so it doesn't look like SQL until it's too late (filter bypass via encoding).

## A Few Things Worth Knowing Before You Start

**`information_schema` is your best friend.** Every major relational database (PostgreSQL, MySQL, Oracle with slight naming differences, SQL Server) ships with a built-in metadata catalog that describes its own structure — what tables exist, what columns each table has, what type each column is. You don't need to guess table or column names when you can just ask the database to tell you:

```sql
SELECT table_name FROM information_schema.tables
SELECT column_name FROM information_schema.columns WHERE table_name = 'users'
```

This only works when you can see query output directly (non-blind injection). In blind scenarios you don't get to read the catalog back — you're stuck inferring one true/false answer at a time, which is exactly why blind techniques are slower and need automation.

**Column count and column type matter for UNION attacks.** A `UNION SELECT` has to return the same number of columns as the original query, and (in most databases) compatible data types in the same positions. Get either wrong and you get a database error instead of clean output — which, as a side note, is itself a useful way to *find* the right column count: keep adding columns until the error goes away.

**A literal is not a column.** `SELECT 1 FROM users` is syntactically valid and will run fine, but `1` there is just a constant — it doesn't reference any real data in the table. It's useful for confirming a table exists or estimating row count, but it extracts nothing. You need an actual column name in the SELECT list to get real data out.

**Results aren't guaranteed to be in any order unless you say so.** If you're pulling values from two separate queries (say, usernames from one, passwords from another) and hoping they line up row-for-row, they might not. Scope with a `WHERE` clause on a known value instead of assuming order.

**Filters that inspect raw request text can often be bypassed by anything the backend decodes afterward.** If an app checks the request body for banned words before parsing it (as XML, URL-encoding, Unicode, etc.), encoding your payload so it doesn't match the filter's literal string — but still decodes correctly before hitting the database — gets you past it.

## Techniques Covered

| # | Technique | What it teaches |
|---|---|---|
| 1 | [Intro to SQL Injection](./01_what's_SQL_injection) | Core concepts, why injection happens at all |
| 2 | [UNION-Based SQL Injection](./02_union_base) | Reading data directly out of the response using `UNION SELECT` |
| 3 | [Boolean-Based Blind SQL Injection](./03-boolean-blind) | Inferring data one true/false question at a time via response differences (the "Welcome back" cookie oracle) |
| 4 | [Error-Based Blind SQL Injection (Oracle)](./04-error-based-blind) | Forcing an HTTP 500 on true/false conditions using `CASE` + `TO_CHAR(1/0)` |
| 5 | [Visible Error-Based SQL Injection (PostgreSQL)](./05_Error_Based) | Leaking real data straight out of database error messages using `CAST()` type mismatches |
| 6 | [Time-Based Blind SQL Injection (PostgreSQL)](./06_time_delay) | Inferring data via deliberate response delays (`pg_sleep` + `CASE WHEN`), automated with a Python binary-search script |
| 7 | [Filter Bypass via XML Encoding](./07_WAF_bypass) | Sneaking a UNION attack past a keyword-blocking WAF by encoding payloads as XML entities |

## Automation Scripts

A couple of the blind techniques are too slow to do by hand through Burp Suite one character at a time, so those folders include a working Python script (using `requests`) that automates the binary-search extraction loop against the target. Update the `TrackingId`/session cookie in the script before running it — lab sessions expire after a short period of inactivity.

## Notes on This Repo

- Every write-up is written the way I'd explain it to someone who's never done this before — if a step needed an explanation of *why*, not just *what*, that explanation is in there.
- Lab credentials and session identifiers shown in these reports are temporary and regenerate per lab instance — they're dead by the time you're reading this.
- This repo will keep growing as I work through more techniques (second-order injection, out-of-band, NoSQL injection).
