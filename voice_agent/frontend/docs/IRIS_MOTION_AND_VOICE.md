# IRIS: direct access, precise answers, smoother voice

## No admin gate

Open http://127.0.0.1:3000 and click Talk to IRIS. The username, password,
clock-code login, speech-recognition sign-in, login API, lock button and local
signing key have been removed at the user's request. Provider credentials were
not changed. No page polls the old login endpoint. Old browser cookies are
ignored and cannot grant any additional capability.

The development token endpoint no longer requires a login cookie. It still
rejects non-loopback/cross-origin requests and is disabled in production. Keep
the development server bound to 127.0.0.1; do not expose this no-login endpoint
to the internet. Public deployment still needs proper authentication.

## Answer quality

IRIS is instructed to answer the latest question first, use relevant follow-up
context, omit repeated butler catchphrases and unrelated background, distinguish
evidence from uncertainty, and ask clarifying questions only when necessary.
It should use tools for changing facts and answer stable questions directly.
Harmless explanations no longer require confirmation after every step; actual
consequential actions still do. The original identity and safety rules remain.
These are behavioral improvements, not a guarantee of perfect model answers.

## Voice changes and limits

- Browser capture explicitly enables echo cancellation, noise suppression,
  automatic gain and mono input. Normal browser/device support still applies.
- Gemini's automatic speech detector uses lower sensitivity and waits six
  hundred milliseconds of silence before ending the user's turn. A two-hundred
  millisecond prefix helps retain the start of speech. Genuine user speech still
  interrupts the assistant; interruptions have not been globally disabled.
- Public search HTML/XML parsing is moved off the voice event loop. Page lookup
  is bounded to twelve seconds, search to twenty seconds, and individual search
  source reads to six seconds. A timed-out search reports failure, not guessed
  facts. Gemini 3.1 still waits for synchronous tool results, so a search can
  produce a pause even when audio playback itself is healthy.
- The reactor now samples thirty-two bands every hundred milliseconds instead
  of forty-eight every sixty-five milliseconds. Independent CSS image expansion
  remains smooth; the visual meter is less expensive to redraw. Browser debug
  logging is limited to warnings rather than every transport event.

There was no recording of the reported stutter. Network loss, provider delays,
Bluetooth/device problems and acoustic echo can still affect speech. A live-call
test is needed before claiming that intermittent audio interruptions are fixed.
Headphones can help distinguish speaker echo from network or provider issues.
The missing Chromium headless executable found during tests was also repaired.

## Artwork and checks

The original WebP artwork remains in use. Masked inner image layers expand and
contract independently, measured audio affects their glow/expansion, and the
outer frame does not continuously rotate. Pause and reduced-motion support stay.

The earlier reference was only the opening twenty-five seconds of
https://www.youtube.com/watch?v=J-FkR8L2X5E. Frame capture was unavailable, so exact
reference timing was not visually verified. No footage or audio was copied.

Run `npm.cmd run test:local` for local access/audio configuration checks. Set
`IRIS_HTTP_TESTS=1` to include the no-cookie token and removed-login API checks
against the running frontend. Run `uv run pytest -q` in `jarvis_new` for the
Python suite. Paid model evaluations remain opt-in; offline tests do not prove
real-world speech quality or model response precision.
