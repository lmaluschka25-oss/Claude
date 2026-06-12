# Scope, fair play, and limitations

This document explains exactly what the Vision Coach does and does not do, and
why the line is drawn where it is.

## The boundary

This is a **post-match** analysis tool. It consumes a video file *after* you
have finished playing — the same recording a coach or analyst would scrub
through. It is architecturally incapable of affecting a live game.

**It only ever uses information that was already visible on your screen:**

- enemies and agents visible in the 3D viewport,
- enemy markers that were **revealed on your own minimap** during play,
- the killfeed, the scoreboard, the round timer, the spike state when shown,
- the map and agents in play.

**It deliberately does NOT:**

- run in real time or overlay anything on a live match,
- read or write game memory,
- inspect, capture, or modify network packets,
- access hidden/unseen enemy positions or any non-visible game state,
- automate, assist, or trigger any in-game input.

These are not just policy promises — the codebase has no component that reads
memory, hooks the game process, sniffs traffic, or injects input. The only
input is a video file you provide.

## Why this design

A real-time tool that tracks enemies, predicts rotations, and estimates site
pressure *during* a match would provide an in-game advantage. Riot's third-party
application policy prohibits software that does this, regardless of how the data
is obtained — and the Vanguard anti-cheat exists to enforce it. Building the
low-latency, live screen-capture detection half of such a tool is also the hard
core of modern "external" cheats, even with the final step withheld.

Post-match review sidesteps all of that. It is the category legitimate Valorant
tools operate in, and it is better coaching anyway: you review what information
you actually had and what you missed, instead of outsourcing game sense in the
moment.

## Use your own footage

Only analyze recordings you have the right to use — your own gameplay, or
footage you are licensed to process. Train any detection model on the same
basis. Do not label or infer enemies that were not visible on screen; that would
defeat the purpose of the tool and falls outside its scope.

## Honest limitations

- **Location accuracy.** Viewport sightings are localized to *your* position as
  a proxy, which is approximate. Precise enemy coordinates come only from
  revealed minimap markers.
- **Rotation estimates are inferences,** not facts — transparent dead-reckoning
  over a callout graph, bounded by elapsed time. Treat likelihoods as hints.
- **Detection quality depends on your model.** The shipped default is a
  synthetic mock; real accuracy requires a model you train on representative
  footage (see [SETUP.md](SETUP.md)).
- **OCR is best-effort** and sensitive to HUD scale/resolution; calibrate the
  regions for your setup.
- **Map metadata is approximate.** The callout coordinates are hand-placed and
  meant to be refined per map.

This tool is not affiliated with or endorsed by Riot Games.
