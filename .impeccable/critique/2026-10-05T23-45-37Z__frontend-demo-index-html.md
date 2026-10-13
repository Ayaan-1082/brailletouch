---
target: frontend-demo dashboard
total_score: 23
max_score: 36
na_heuristics: 10
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Users\\khana\\OneDrive\\Documents\\1imp project\\brailletouch\\frontend-demo\\index.html"
target_fingerprint: "sha256:7174e179158930d672f9bf80d112a5b04e3932e451b8c378bfe0f3dd59f91847"
target_path: "C:\\Users\\khana\\OneDrive\\Documents\\1imp project\\brailletouch\\frontend-demo\\index.html"
timestamp: 2026-10-05T23-45-37Z
slug: frontend-demo-index-html
---
# Critique of the BrailleTouch demo dashboard (frontend-demo/)

Method: dual-agent (A design review, B detector + browser evidence; two isolated general-purpose subagents).

## Design Health Score: 23/36 applicable (heuristic 10 n/a), 64%, Acceptable

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | isPlaying never rendered; "Playing..." cleared by next message; stale content bright on disconnect |
| 2 | Match system / real world | 3 | Cell + board layout match device; uppercase T beside lowercase "t" pattern |
| 3 | User control and freedom | 3 | Controls exist; Start/Pause show no current state |
| 4 | Consistency and standards | 3 | Yellow = connected and playing; dock wider than stage |
| 5 | Error prevention | 2 | Parked Camera capture looks like a normal button |
| 6 | Recognition rather than recall | 3 | Letter shown three times |
| 7 | Flexibility and efficiency | 2 | No keyboard transport shortcuts |
| 8 | Aesthetic and minimalist design | 3 | ~12 simultaneous readouts |
| 9 | Error recovery | 2 | Errors tiny, bottom, content not dimmed |
| 10 | Help and documentation | n/a | Live console for its own team |

## Design specificity: specific (plate), conventional elsewhere
Detector: 3 warnings (broken-image false positive, cramped-padding false positive, dark-glow judgement call); browser live detector: none; contrast, overflow, 44px targets, focus rings all pass.

## Priority issues
- [P1] Playback state invisible (clarify, harden)
- [P1] Dots look raised while motor chips say OFF (clarify, shape)
- [P1] Long text and disconnect break layout and trust (harden, layout)
- [P2] Too many readouts, six equal buttons, parked Camera (distill)
- [P2] Empty state looks broken; dock/stage misaligned (polish)
- [P3] Uppercase T versus lowercase t pattern (clarify; display-only, backend untouched)

## Personas: Alex (no keyboard transport), Sam (no live announcements, colour-only highlight, unreachable scroll box), Riley (no click feedback, stale on disconnect, layout jump on long text)
