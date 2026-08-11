# **Boolean-Based Blind SQL Injection - Practical Walkthrough**

This walks through the actual attack step by step, with screenshots from the lab. See README.md in this folder for the underlying theory.

## **Step 1: Observe the Baseline Behavior**

First, load the site fresh - no "Welcome back" message appears, since this is treated as a new visit.

![](images/image1.png)

Reload the page. This time, "Welcome back" appears - the app recognized the tracking cookie from the first visit.

![](images/image2.png)

This confirms the app's behavior changes based on the TrackingId cookie - exactly the kind of signal blind SQLi relies on.

## **Step 2: Intercept Traffic in Burp Suite**

Open Burp Suite and intercept the request so we can see and edit the TrackingId cookie directly.

![](images/image3.png)

Send the intercepted request to **Repeater**, so it can be edited and re-sent repeatedly without needing to reload the page each time.

![](images/image4.png)

## **Step 3: Confirm the Boolean Signal**

Send the request normally first, with a **grep-match filter** set for "Welcome Back" in Repeater's options. One match, HTTP 200 - this is the baseline true case.

![](images/image5.png)

Now inject a true condition onto the tracking ID:

Cookie: TrackingId=xyz' AND '1'='1

No error, and "Welcome back" still appears - the true condition passed through cleanly.

![](images/image6.png)

Now flip it to a false condition:

Cookie: TrackingId=xyz' AND '1'='2

This time "Welcome back" disappears. Falsifying the condition breaks the match against the real tracking ID stored server-side, so the app no longer recognizes the session.

![](images/image7.png)

This confirms we have a reliable true/false oracle to work with.

## **Step 4: Confirm the Table and Columns Exist**

Test whether the users table exists:

' AND EXISTS(SELECT 1 FROM users)--

![](images/image8.png)

Then confirm the username and password columns exist, by swapping the column name in the same style of payload and checking for the same true/false signal.

![](images/image9.png)

## **Step 5: Find the Password Length**

Before extracting characters, we need to know how long the password is. Manually sending one request per length guess is slow, so this step moves to **Intruder** to automate it.

The payload:

' AND LENGTH((SELECT password FROM users WHERE username='administrator')) > §1§--

Set up a **Sniper attack** with a numeric payload set from 1 to 30 - each request substitutes a different number in place of the length check, and Intruder sends them all automatically.

![](images/image10.png)

Reviewing the results with the "Welcome back" grep filter still applied: requests up through length 19 return a match (true), and 20 onward returns no match (false). That means the true/false boundary sits at **19 → 20**, so the password is **19 characters long**.

![](images/image11.png)

## **Step 6: Extract the Password**

Manually testing every character position through Burp's free Intruder is slow - Burp intentionally throttles Community Edition to push users toward the paid version. Instead, this step uses a Python script that sends the requests directly and applies binary search per character.

You only need two values from Burp: the current TrackingId prefix and session cookie. Paste them into the script's configuration fields.

![](images/image12.png)

Then run the script from the terminal, passing the lab URL as the argument:

python ./blind_sql_injection_BF_script.py "<https://your-lab-id.web-security-academy.net/>"

![](images/image13.png)

## **Step 7: Log In**

With the extracted password, log in as administrator on the site.

![](images/image14.png)

Lab solved.

## **Notes**

- The TrackingId and session values shown in these screenshots are tied to a single, short-lived lab instance and expire automatically - they're not usable outside that session.
- See extract_password.py in this folder for the full automation script used in Step 6.