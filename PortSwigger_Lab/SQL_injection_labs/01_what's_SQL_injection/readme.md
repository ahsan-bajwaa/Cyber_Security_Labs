# SQL Injection: What It Is and How to Detect It

## Introduction

When you hear "injection," you probably think of the kind you feared as a
kid — a needle putting something into your body. SQL injection works on
the same basic idea, except instead of curing something, it harms it.

First, some context: **SQL** is a query language that web servers use to
talk to their databases. Every time a web application needs to fetch,
add, or update data — your username, your order history, a product
listing — it does so by running a SQL query behind the scenes.

**SQL injection** happens when an attacker manipulates that query so the
database returns information it was never meant to hand over. Instead of
the app controlling exactly what data comes back, the attacker takes
partial control of the query itself.

---

## How the Query Actually Runs

Say a URL looks like this:

```
https://insecure-website.com/products?category=Gifts
```

Behind the scenes, the server likely builds a query like this:

```sql
SELECT * FROM products WHERE category = 'Gifts'
```

The `category` value in the URL gets inserted directly into the query. If
the application doesn't sanitize that value first, an attacker can replace
`Gifts` with their own SQL and change what the query actually does.

---

## Consequences

If an attacker successfully injects SQL, they can potentially access any
data stored in that database — usernames, passwords, personal details,
payment information, anything the database holds. In more severe cases,
depending on the database permissions, an attacker may also be able to
modify or delete data, or use the database as a stepping stone into other
parts of the server.

---

## How to Detect SQL Injection Vulnerabilities

The most common first test: add a single quote (`'`) to the end of a URL
parameter or any other input that reaches the server. If the server
responds with an unhandled error or an HTTP 500, that's a strong sign the
input is being inserted directly into a SQL query without being properly
handled — meaning there's likely a vulnerability there.

That confirms *something* is broken, but not that you can control it
usefully. Next you need to check whether the server actually responds
differently based on true/false conditions you control. A common way to
test this is comparing:

```sql
' OR 1=1--
' OR 1=2--
```

If the app behaves differently between these two — different content,
different response length, extra rows showing up — that's confirmation
you can influence what the query returns.

This is just the most basic detection method. There are many more, ranging
from simple to advanced, and a tool like **Burp Suite** is the standard way
to test for these systematically rather than by hand.

---

## Common Types of SQL Injection

SQL injection shows up in a few recurring patterns, depending on the
situation:

1. **Retrieving hidden data** — modifying a query to return extra results
   the application wasn't intended to show you.
2. **Subverting application logic** — changing a query to interfere with
   how the app is supposed to behave (e.g. bypassing a login check).
3. **UNION attacks** — appending your own query to pull data from
   different tables in the database.
4. **Blind SQL injection** — the results of your injected query aren't
   shown directly in the response, so you have to infer them indirectly
   (through true/false differences, timing delays, or forced errors).

Each of these is its own technique with its own methodology — this report
covers the detection basics; UNION attacks and blind SQLi are covered in
separate write-ups in this repo.
