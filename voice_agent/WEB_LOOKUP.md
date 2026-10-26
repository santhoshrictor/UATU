# Background web answers and current time

IRIS now has three answer-first tools registered on the voice agent:

- `get_current_time`: obtains the current instant from the computer system clock
  and converts it with timezone data. India/IST/Chennai use Asia/Kolkata. Windows
  gets the timezone database through the explicit `tzdata` dependency. This does
  not depend on search snippets or the model's knowledge. Keep the Windows clock
  synchronized: a wrong computer clock still produces a wrong current instant.
- `lookup_website`: fetches and extracts public page text in the background in
  one call, including title, final URL and a retrieval timestamp.
- `search_internet`: reads public DuckDuckGo results, with Bing RSS as a fallback,
  and reads up to two source pages concurrently. Blocked sources are explicitly
  marked as snippet-only. Retrieval time is not an article's publication date.

No additional search API key is required. Public search engines can still rate
limit, return irrelevant results or change their formats. The agent is instructed
to check dates/relevance, answer concisely from evidence, and report failures
instead of inventing an answer. Existing browser tools remain as a hidden
JavaScript/interaction fallback; no window is opened or focused by the agent.
Requests to open a named site are interpreted as background reading in this mode.

The HTTP reader is read-only and does not use logged-in cookies, ambient proxies,
or browser profile data. It blocks credentials in URLs, local/private destinations
and nonstandard ports; its connector validates the actual DNS answers used for
the connection. Redirect targets are checked individually, downloads are capped,
and page content is treated as untrusted information rather than instructions.
These public-reader restrictions do not replace the separate existing browser
tool confirmation rules.

Not all sites expose useful public HTML. Paywalls, login-only information,
CAPTCHAs, live video/audio and JavaScript-only content may be unavailable. Reading
a YouTube page is not watching its video; ask for a transcript when needed.
The reader does not bypass these restrictions. The app retains its guardrails
and must not treat a failed lookup as permission to perform consequential actions.

## Apply and test

Restart the Python worker in its existing terminal, from `jarvis_new`:

```powershell
uv run python src/agent.py dev
```

Then start a new call. The already-running worker/call will not load Python
changes automatically. Leave the frontend running; no frontend rebuild is needed.
Try “What is the current time in India?” or “Read python.org and tell me what it
is.” If the hidden browser fallback reports a missing executable, install it with
`uv run playwright install chromium`; ordinary HTTP lookups do not require it.

The offline suite covers timezone/date rollover, registered tools, page/search
parsing, DNS/private URL rejection, bounded extraction, fallback source labels,
and browser startup cleanup. Public-network tests are opt-in:

```powershell
$env:IRIS_RUN_WEB_CHECKS = '1'
uv run pytest -q
```

The live checks successfully read a public example page and searched for/read
Python's official documentation without opening a browser. No paid model calls
or microphone recording were used. Actual speech recognition and Gemini choosing
the tools still need a live-call check after restarting the worker.
