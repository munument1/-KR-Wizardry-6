# v0.1.0-alpha.2 build verification

Date: 2026-09-01

The release package was rebuilt from the clean GOG DOS files with the production release builder after Runtime Recovery Test8 was confirmed in-game.

## Build audit

- decoded MSG records: 5,161
- translated rows: 4,720
- actually changed messages: 4,492
- custom Korean glyphs: 1,017 / 1,024 runtime limit
- SCENARIO translation rows: 668
- SCENARIO translated fields: 1,223
- item names: 452
- monster records: 186
- NPC names: 30

## Runtime patch hashes

- `WROOT.EXE`: `fba9eb4f57850ac13cc3b0f39989b6d6b66411f0cd04abcc8480b81abaf54ee1`
- `EGA.DRV`: `3992d5353a0ac48ce207619ef80d7d4fccba424548d718c26adbf3ec84bf345e`
- `WFONT0.EGA`: `6364af3edc61676e166971778ba34e03279689d97827773087f892c9dbd7b8f1`
- `WBASE.OVR`: `a3aa1fa38fa92f6d07a87ef6a42fa445dbaeabfb7741b5892cf124f8f649644c`
- `WPCMK.OVR`: `1e69cd12637ce2e27d9896f13d1bd8b6a8aa11c4baa66873f6f2bf1c1ff1227a`
- `SCENARIO.DBS`: `73a163fecae859447526aa9fc85e98f246e3f05071d38ec513c44d2ee9e0a79f`
- `MSG.DBS`: `be6fe63070b7464ed95c7fbe31578f4ceee8cc9a84c0bfa43e789b48277053ee`

## Test8 equivalence

The rebuilt alpha.2 package was compared against the user-tested Runtime Recovery Test8 package. The following core files were byte-for-byte identical:

- `WROOT.EXE`
- `EGA.DRV`
- `WFONT0.EGA`
- `WBASE.OVR`
- `WPCMK.OVR`
- `SCENARIO.DBS`
- `MSG.DBS`
- `MSG.HDR`
- `MISC.HDR`
- `TITLEPAG.EGA`

Release ZIP SHA-256: `850ec1e0fdaa947a21bd0a112e6e379aafb1dde11a1e603466c795698841fa6d`
