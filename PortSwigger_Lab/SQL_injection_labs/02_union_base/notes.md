# SQL Injection: UNION-Based Attacks

## Introduction

A UNION attack lets an attacker take a query the application already runs and
stitch their own query onto the end of it, using SQL's `UNION` keyword. The
database then returns both result sets combined — the app's original data
plus whatever the attacker asked for. If the app displays query results on
the page (like a product list or search results), the attacker's injected
data gets displayed right alongside it.

Think of `UNION` like combining two sets of numbers into one list:

```sql
SELECT a, b FROM table1
UNION
SELECT c, d FROM table2
```

The database runs both `SELECT` statements and merges the rows into a single
result. This only works under two conditions, which is why the steps below
exist:

1. Both queries must return the **same number of columns**.
2. The columns being combined must have **compatible data types** (you can't
   UNION a text column with a number column in most databases).

Before attempting a UNION attack, you should already have basic SQL and
database knowledge (tables, columns, `SELECT`, `WHERE`) — this guide assumes
that.

---

## Step 1: Confirm the Injection Point Exists

Before building anything complex, confirm the input is actually vulnerable.
Try breaking the query with a single quote and see if the app errors or
behaves differently:

```sql
'
```

If you get a database error, a blank page, or a different response than
normal, the input is likely being inserted directly into a SQL query —
you have an injection point to work with.

---

## Step 2: Find the Number of Columns

The original query returns a fixed number of columns, and your injected
`UNION SELECT` must match that number exactly, or the database will throw
an error. There are two common ways to find it.

### Method A — `ORDER BY`

```sql
' ORDER BY 1--
' ORDER BY 2--
' ORDER BY 3--
```

`ORDER BY` sorts results by column position. Keep increasing the number
until the query errors out — that tells you the column count. For example,
if `ORDER BY 3` throws an error but `ORDER BY 2` doesn't, the table has
**2 columns**.

### Method B — `UNION SELECT NULL`

```sql
' UNION SELECT NULL--
' UNION SELECT NULL,NULL--
' UNION SELECT NULL,NULL,NULL--
```

Keep adding `NULL` values until the query succeeds without error. `NULL` is
used here because it's valid for any data type (text, number, date), so it
won't trigger a type-mismatch error — only a column-count error, which is
exactly what you're testing for.

---

## Step 3: Find Which Columns Accept Text

Once you know the column count, you need to know **which columns can hold
string data** — because that's where you'll extract usernames, passwords,
and other text later.

Test this by replacing one `NULL` at a time with a string:

```sql
' UNION SELECT 'a',NULL--
' UNION SELECT NULL,'a'--
```

- If a column accepts text, the query runs fine.
- If a column is expecting a number (or another incompatible type), the
  query throws a data-type error.

Repeat this for every column position until you know exactly which ones you
can safely put your extracted string data into.

---

## Step 4: Retrieve Interesting Data

Say you've confirmed the table has 2 columns, both accept text, and you
suspect a `users` table exists with `username` and `password` columns. You
can now pull that data directly into the page's output:

```sql
' UNION SELECT username, password FROM users--
```

If this table/column combination exists and the columns are the right data
type, the app will render the usernames and passwords right on the page
alongside its normal content.

---

## Step 5: Combining Multiple Values Into a Single Column

Sometimes the app only actually displays **one** of the columns back to
you, even though the query returns two or three. In that case, extracting
`username` and `password` as separate columns is useless — only one of them
will ever show up on screen.

The fix: squeeze both values into a single column using string
concatenation, so they travel together in the one column the app does
display.

Different databases use different syntax for this:

| Database   | Concatenation syntax |
|------------|----------------------|
| Oracle / PostgreSQL / SQLite | `||` |
| MySQL      | `CONCAT(a, b)` |
| MSSQL      | `+` |

Example (Oracle/PostgreSQL):

```sql
' UNION SELECT NULL, username || '~' || password FROM users--
```

Here, `||` joins the two values into one string, and `~` is just a
separator character so you can visually tell where `username` ends and
`password` begins once it's rendered on the page. The result looks
something like:

```
administrator~s3cure
wiener~peter
carlos~montoya
```

---

## Common Pitfalls

- **Column count mismatch** — the single most common error. Always confirm
  the count with Step 2 before moving on.
- **Data type mismatch** — putting a string into a column the database
  expects to be a number (or vice versa) will error out even if the column
  count is correct.
- **Forgetting the comment sequence** (`--`, or `#` in MySQL) — without it,
  whatever the app appends after your input can break the query syntax.
- **Assuming column names before checking** — always confirm the table and
  column names actually exist (via `information_schema`, if unknown) rather
  than guessing blindly.
