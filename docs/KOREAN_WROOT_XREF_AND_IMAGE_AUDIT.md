# Wizardry VI Korean localization: WROOT xref and image-text audit

Date: 2026-08-31  
Branch: `korean-localization`

This note records the second static localization audit against the user's original DOS data. No commercial game binary or generated full asset is committed.

## 1. `WROOT.EXE` reference audit

`WROOT.EXE` is an MZ executable with:

- MZ header size: `0x200`
- entry relocation count: `1`
- pre-relocation DGROUP segment: `0x0FD8`
- DGROUP file base: `0x0FF80`

The sole relocation points into the startup `mov bp,<segment>` immediate. This makes it possible to recover DGROUP and turn file offsets for static strings into the 16-bit offsets used by normal game code.

`korean/tools/xref_wroot_strings.py` scans printable runs and retains only strings with a plausible static reference. For DGROUP strings it checks `MOV r16,imm16`; for code-segment fatal messages it checks the `MOV DX,imm16` DOS-output path, including a short CR/LF/BEL prefix before the printable run.

Result on the audited original:

- referenced printable strings: **30**
- technical filenames/module names: **18**
- localization candidates: **12**

This matches the earlier conservative binary scan exactly; the 12 candidates are no longer just `strings` hits.

### Confirmed user-visible / diagnostic strings

| File offset | Text | Static evidence | Classification |
|---:|---|---|---|
| `0x021BE` | `Unable to load display driver` | CS offset `0x1FBB`, `MOV DX` then DOS `AH=09/int 21h` | fatal DOS output |
| `0x02339` | `Unable to allocate sufficient memory to run.` | CS offset `0x2136`, DOS `AH=09/int 21h` | fatal DOS output |
| `0x0243D` | `I/O error loading font` | CS offset `0x223A`, DOS `AH=09/int 21h` | fatal DOS output |
| `0x02BB8` | `I/O error loading Misc. table.` | CS offset `0x29B5`, DOS `AH=09/int 21h` | fatal DOS output |
| `0x03105` | `Invalid font in refreshwindow` | CS offset `0x2F02`, DOS `AH=09/int 21h` | fatal/debug DOS output |
| `0x10506` | `INSERT SAVEGAME DISK` | DGROUP `0x0586`, referenced at file `0x01019` | in-game prompt |
| `0x1051B` | `INSERT DISK (^)` | DGROUP `0x059B`, referenced at file `0x01038` | in-game prompt |
| `0x1052B` | `INTO DRIVE ^` | DGROUP `0x05AB`, referenced at file `0x01095` | in-game prompt |
| `0x10538` | `PRESS X` | DGROUP `0x05B8`, referenced at file `0x010D7` | in-game prompt |
| `0x105BB` | `Error %d loading overlay: %s$` | DGROUP `0x063B`, formatted at file `0x039D2`, then DOS output wrapper | runtime diagnostic |
| `0x105F0` | `8087/80287 is required!` | DGROUP `0x0670`, `MOV DX` at `0x043AD`, DOS `AH=09/int 21h` | startup diagnostic |
| `0x1060D` | `Too many args.` | DGROUP `0x068D`, referenced at file `0x0445B` | startup diagnostic |

The four disk/prompt strings are built into a temporary text buffer and flow through the game's normal screen text path. They should therefore be treated as actual localization targets, not as technical/debug strings.

### OVR result

A raw ASCII review of `WBASE.OVR`, `WMAZE.OVR`, `WMNPC.OVR`, `WPCMK.OVR`, `WPCVW.OVR`, `WMELE.OVR`, `WMEXE.OVR`, `WDOPT.OVR`, `WINIT.OVR`, `WTREA.OVR`, `WPOPS.OVR` did not expose additional natural-language UI strings. The stable ASCII runs are mostly filenames (`SOUND00.SND`, `MON00.PIC`, `PCFILE.DBS`, `WPORT*.EGA`, etc.) or binary data that happens to be printable.

This is consistent with normal dialogue/UI wording living primarily in `MSG.DBS` rather than in the overlays.

## 2. Full-screen EGA image-text audit

The repository's `file_format_docs/FULLSCREEN_EGA.md` is correct for these files:

- exact size `32768`
- 4 plane slots of `8192` bytes
- first `8000` bytes of each slot are 320x200 plane pixels
- final `192` bytes per slot are padding
- sequential planar EGA, **not** row-interleaved

A previous scratch helper (`scratch/load_titlepag.py`) skips 768 bytes and uses row-interleaved decoding; that path is unsuitable for localization image auditing. `korean/tools/export_image_text_previews.py` uses the documented full-screen layout instead.

### Visual findings

- `TITLEPAG.EGA`: contains rasterized title text **`BANE OF THE COSMIC FORGE`**. This is a real image-localization target if the title screen is to be fully localized.
- `GRAVEYRD.EGA`: no normal prose, but the gravestone contains **`RIP`**. This is conventional artwork text and can remain unchanged unless an all-Korean art pass is desired.
- `DRAGONSC.EGA`: contains the stylized **`Wizardry`** logo. Treat as brand/logo artwork; do not translate by default.
- `CREDITS.PIC`: RLE decompression yields **13 sparse sprite frames**. The frames contain credit headings, names, copyright text, Sir-Tech branding and title/logo artwork. Text is rasterized into the PIC frames rather than rendered through `WFONT`.

Consequences:

1. Title/credit artwork cannot be fixed by the runtime Hangul font alone.
2. If credits are localized, preserve personal names and translate only role/headline text unless a separate editorial decision is made.
3. Generated preview PNGs are local QA output only and must not be committed.

## 3. Next static targets

1. Keep the 12 WROOT strings in the translation inventory with their exact file/xref evidence.
2. Keep `TITLEPAG.EGA` as a later image-patch target.
3. Keep `CREDITS.PIC` as a later optional/secondary image-patch target.
4. Continue structural extraction of non-ASCII / non-plain-text system names from `SCENARIO.DBS` and message IDs before implementing Hangul rendering.
