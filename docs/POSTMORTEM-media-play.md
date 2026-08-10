# Postmortem: “play the song on my screen” (2026-08-10)

## What the user saw
1. Music started (correct track: *Jesus Be The Name*).  
2. Then it **paused**.  
3. Then it **played again**.  
4. Then it **jumped to another song**.

That was **not** an intentional test. It was a control error.

## Root causes

| Mistake | Why it happened |
|---------|------------------|
| Multiple attempts in one turn | Agent retried after partial success instead of verifying “already playing” |
| `hotkey("space")` / media keys | Space **toggles** play/pause — second press undoes the first |
| Loose match on `"Play"` | Hit **Playing from** / later **Play all** instead of transport **Play** only |
| Clicked **Play all** while **Pause** was already visible | Search loop matched any label containing `"play"`; ignored Pause = already playing |
| No “look then act once” rule | No `media_transport` helper yet |

## Fixes shipped
- Better `find` scoring: exact label > short-word false friends (`Play` vs `Play all` / `Playing from`)  
- `click_text(..., exact=True)`  
- `media_transport()` / `ensure_media_playing()` — noop if Pause is visible  
- Skill rules: never spam Space; one action; don’t change track unless asked  

## Agent rule of thumb
```text
read media_transport()
if playing → done
if paused  → press exact Play once → re-read → done
else       → report unknown; don't thrash
```
