# IRIS reactor interface

The UI is built around the user's cyan/orange circular HUD reference. The generated
artwork is installed at `public/iris-reactor.webp` (1254 × 1254, 287,432 bytes).
It was prepared with the built-in image-generation tool and compressed to WebP
with Sharp. The original generated PNG remains in the image-generation library.

The interface uses actual LiveKit connection, microphone, camera, screen-share,
and transcript states. The reactor reads 32 measured audio bands
from IRIS's output while speaking and the local microphone otherwise. Masked
regions inside the artwork expand independently; the peripheral frame no longer
rotates. Amber pulses indicate
thinking/connecting; microphone/speaker energy controls the spectrum and glow.
The waveform shown before the first exchange is explicitly decorative, not telemetry.

Camera/screen sharing remain opt-in. Animation can be paused from the header and
respects the operating system's reduced-motion preference. Both side panels have
been removed at every size, leaving a centered reactor and call controls. The
independent internal ring layers expand at different rates; actual audio still drives
the spectrum and glow. The header's Restart conversation button ends the call
and starts a fresh session, without carrying over prior voice context.

The clock-code/admin gate has been removed. The app opens directly to the reactor.
See `IRIS_MOTION_AND_VOICE.md` for current audio settings, no-login local-only
access, answer-quality changes, and the remaining verification limits.

## Repeated-response recovery

The original failed call was not saved, so its provider-side trigger is unknown.
`src/recovery.py` detects only the specific generic language-model boilerplate
repeated in response to two different user turns. It requests a new Assistant
with a fresh model and empty context, once per call. The replacement retains the
original persona, safety rules and tools, discards pending tool confirmations,
discloses that context was refreshed, and asks for a new request. It does not
replay the refused request or disable legitimate refusals. Browser state stays
available, but old conversation context is not passed to the new model.

This is a bounded recovery measure, not proof that Gemini cannot repeat again.
Unit tests simulate the loop, duplicate events, normal answers, legitimate
refusals, interrupted output, and preservation of the original instructions.
No paid/live model calls or microphone recording were used for these tests.
Restart the Python worker to load this change; an existing call still uses the
old worker. Use Restart conversation if the issue returns after recovery.

## Verification

### Development asset recovery

If the page appears as unstyled text or an oversized SVG, check the linked
`/_next/static/css/app/layout.css` request. A missing stylesheet was reproduced
when overlapping development/build output left stale asset references.

Development now uses `.next-dev/`, while production builds/start use `.next/`.
The development command explicitly reserves port 3000, so launching it twice
fails clearly instead of silently opening a second instance on port 3001.
Keep one frontend terminal running and open `http://127.0.0.1:3000`.
After a restart, use Ctrl+Shift+R if an existing browser tab retains old assets.

### Interface checks

- The simplified layout was checked through the browser DOM at 1280 × 720:
  no side panels, one centered column, and no page overflow. Ring motion and
  pause/resume were verified through computed styles. Screenshot capture was
  unavailable during this update; existing preview images show the prior layout.

- TypeScript checking and the optimized production build passed.
- ESLint passed for the changed application components.
- Chrome desktop (1536 × 776) and phone (390 × 844) layouts were inspected.
  Neither viewport had horizontal overflow; the phone layout fit within one screen.
- The animation pause/resume buttons were checked against actual computed animation
  state. The help panel opened and closed with Escape.
- No rendering errors were recorded after fixing cross-engine SVG coordinate
  rounding. Voice input was not recorded during automated visual checks; audio
  reaction should be checked during the user's next live call.

## Final image prompt (built-in image generation)

Use case: precise-object-edit. Edit target: the user's latest reference image, a cyan and orange circular science-fiction HUD/reactor on black. Asset type: central animated voice-assistant interface artwork, not a website screenshot. Refine and upscale that reactor into an exceptionally crisp, photorealistic luminous holographic optical mechanism. Preserve the reference's concentric circular composition, electric cyan left/lower rings and warm amber upper-right arcs, dense fine radial ticks and circuitry, black background, straight-on centered circular perspective. Improve clean microdetail, layered glass/metal depth, controlled bloom and realistic light scattering without losing fine lines. Keep the complete mechanism and fine peripheral radial connectors inside generous pure black margins (outermost details within 90% of frame). No UI panels, no title, no labels, no readable text, no watermark, no people. One centered reactor only on seamless pure black, square format. This will sit beneath independent code-animated orbital rings and sound-reactive glow; do not add any surrounding layout.
