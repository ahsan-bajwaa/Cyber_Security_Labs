# SQL Injection: Boolean-Based Blind Attacks

## Introduction

Up to now, we could get the query's actual output shown back to us on the
page — either directly, or by riding along with a UNION attack. That's
great for an attacker, and it's also easy for a developer to notice and
fix. Once developers stop reflecting raw query results back to the user,
that door closes.

But closing that door doesn't fix the underlying flaw — it just makes it
harder to see. **Blind SQL injection** is what you use when the
application is still vulnerable, but no longer shows you any query output
directly. You can't see your query's result on the page anymore, so
instead you learn things indirectly, one true/false answer at a time.

---

## How Blind Detection Works

Even with no visible output, the app usually still behaves *slightly*
differently depending on whether your injected condition is true or false.
Common signals:

- A different HTTP status code (e.g. 200 vs 500).
- A different page — for example, a "Welcome back" message shown to
  recognized users but not new ones.
- A different response length or load time.

This report focuses on the "Welcome back" style signal, tied to a
`TrackingId` cookie that most sites assign to every visitor.

A tracking cookie looks like this:

```
Cookie: TrackingId=u5YD3PapBcR4lN3e7Tj4
```

And the server-side query behind it typically looks like:

```sql
SELECT TrackingId FROM TrackedUsers WHERE TrackingId = 'u5YD3PapBcR4lN3e7Tj4'
```

---

## Testing With Boolean Conditions

Since we know roughly what the query looks like, we can append our own
condition onto the real tracking ID and see how the app reacts:

```
Cookie: TrackingId=u5YD3PapBcR4lN3e7Tj4' AND '1'='1
Cookie: TrackingId=u5YD3PapBcR4lN3e7Tj4' AND '1'='2
```

Both payloads keep the real tracking ID intact, so the underlying `WHERE`
match still succeeds — we're only adding an extra condition on top.

- `AND '1'='1'` is always true → the tracking ID still matches → you see
  the "Welcome back" message.
- `AND '1'='2'` is always false → the match fails → no "Welcome back"
  message, even though the tracking ID itself was valid.

That difference — message vs. no message — is your oracle. From here on,
every question you ask the database gets rephrased as a true/false
condition and read through that same signal.

---

## Extracting Data

Knowing you *can* get a true/false answer is only step one. To actually
pull out a password, you need to ask the right sequence of true/false
questions.

### Step 1: Find the Length

Before guessing characters, find out how long the value is — otherwise
you don't know when to stop:

```sql
' AND LENGTH((SELECT password FROM users WHERE username='administrator')) > 10--
```

Adjust the number up or down (ideally with a binary search) until you find
the exact length.

### Step 2: Extract Character by Character

Once you know the length, test each character position individually using
`SUBSTRING`:

```sql
' AND SUBSTRING((SELECT password FROM users WHERE username='administrator'), 1, 1) > 'm'--
```

This asks: "Is the first character of the password greater than `m`?"
Rather than testing all 26+ letters one at a time, use a **binary search**
— compare against the midpoint of the possible character range, and narrow
down based on true/false, roughly halving the possibilities each time.
This gets you to the exact character in about 5–7 requests instead of 30+.

Repeat this for every position until the full value is extracted.

---

## Automating the Process

Doing this by hand in Burp Repeater works, but it's painfully slow once
you're extracting a full password character by character. Once you
understand the manual process, the natural next step is scripting it —
send the requests programmatically, apply the binary search logic in code,
and let it run through every position automatically instead of you
clicking through each one.

See `extract_password.py` in this folder for the working script.

---

## Common Pitfalls

- **Confusing HTTP status code with the actual boolean signal.** A 200 OK
  just means the page rendered — it does not mean your condition was true.
  Check the response *content* (e.g. does "Welcome back" actually appear),
  not just the status line.
- **Manually URL-encoding payloads that don't need it.** If you're typing
  a raw HTTP request by hand (e.g. in Burp Repeater), send real spaces and
  quotes — don't pre-encode them yourself, or the server receives garbage.
- **Skipping the baseline check.** Always confirm a known-true and a
  known-false condition give visibly different results before trusting any
  extracted data — if both look the same, something upstream is broken
  and every result after that point is meaningless.
