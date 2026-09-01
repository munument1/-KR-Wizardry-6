# Wizardry VI SCENARIO 기존 번역 대조 QA

Date: 2026-09-01

사용자가 제공한 `Wizardry 6 - Scenario` 워크북의 Wizardry VII 참조 번역을 현재 Wizardry VI SCENARIO 번역과 대조했다. 참조 번역을 일괄 덮어쓰지 않고, W6의 16-byte C-string 필드 제한과 현재 용어 품질을 함께 검토해 선별 반영했다.

## 참조 데이터 범위

- SCENARIO 필드 전체: 1,223
- 아이템 이름: 452
- 몬스터 필드: 741
  - name: 186
  - name_plural: 185
  - short_name: 185
  - short_name_plural: 185
- NPC 이름: 30
- W7 참조 번역이 연결된 필드: 277
  - 아이템: 218
  - 몬스터: 58
  - NPC: 1

## Batch 1 반영

- 아이템 이름 교정: 73개
- 몬스터 정식 이름 교정: 6개
- 몬스터 short_name 명시 오버라이드: 12개
- 몬스터 short_name_plural 명시 오버라이드: 12개
- SCENARIO 번역 CSV 행 수: 668 -> 692

대표적인 교정:

- `BROADSWORD`: `브로드검` -> `브로드소드`
- `BIPENNIS`: `비페니스` -> `양날도끼`
- `NUNCHAKA`: `눈차카` -> `눈차쿠`
- `FAUCHARD`: `포차드` -> `포샤르`
- `ROBES (U)/(L)`: `법의상/법의하` -> `로브상/로브하`
- `TARNISHED MAIL`: `변색된메일` -> `녹슨메일`
- `DISPLACER CLOAK`: `전이망토` -> `변위망토`
- `GREATER DEMON`: `대악마` -> `상급악마`
- `LESSER DEMON`: `소악마` -> `하급악마`
- `FLOATER`: `부유구름` -> `부유체`

W7 참조보다 현재 W6 번역이 더 자연스러운 경우는 유지했다. 예: `SLING`은 W7의 `슬링` 대신 현재 `투석구` 유지.

## short_name 처리

기존 SCENARIO 패처는 명시 번역이 없으면 몬스터의 `name`을 plural/short 필드에 재사용한다. 이번 QA에서는 W7 참조와 원문 의미가 명확한 경우 `short_name`과 `short_name_plural`을 별도 행으로 추가했다.

예:

- 산/광부/섬/독 거인 -> short `거인`
- 해골 군주 -> short `해골`
- 밴시/스펙터 -> short `유령`
- 일부 악마 계열 -> short `악마형상`
- 부유체 -> short `구름`

## 검증

GitHub Actions `Korean Localization CI` run #10:

- pytest: 40 passed
- SCENARIO explicit translation rows: 692
- merged field coverage remains complete through fallback rules
- full translation rows audited: 5,412
- custom glyphs: 1,011 / 1,024
- glyph headroom: 13
- encoding failures: 0
- glyph limit exceeded: false

이전 1,017 glyph에서 1,011로 줄어 런타임 글리프 여유가 7에서 13으로 증가했다.
