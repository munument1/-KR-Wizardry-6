# Wizardry VI SCENARIO 기존 번역 반영 기록

Date: 2026-09-01

사용자가 제공한 `Wizardry 6 - Scenario` 워크북에는 Wizardry VII에서 이미 번역된 SCENARIO 대응 항목이 포함되어 있었다. 현재 Wizardry VI SCENARIO 번역은 검증되지 않은 초벌번역이므로, 대응되는 기존 번역은 품질 비교 없이 기존 번역을 우선하는 방침으로 변경했다.

## 참조 데이터 범위

- SCENARIO 필드 전체: 1,223
- 아이템 이름: 452
- 몬스터 필드: 741
  - name: 186
  - name_plural: 185
  - short_name: 185
  - short_name_plural: 185
- NPC 이름: 30
- 기존 번역이 연결된 필드: 277
  - 아이템 name: 218
  - 몬스터 name: 13
  - 몬스터 name_plural: 11
  - 몬스터 short_name: 19
  - 몬스터 short_name_plural: 15
  - NPC name: 1

## 적용 방침

대응되는 277개 필드는 전부 기존 번역으로 교체했다.

유일한 정규화는 Wizardry VII 데이터에서 줄바꿈/분리 표식으로 사용된 `/` 문자를 제거한 것이다. 예를 들어 `바스타드/소드`는 `바스타드소드`, `전투/도끼`는 `전투도끼`로 저장한다.

정규화 후 277개 항목 모두 Wizardry VI SCENARIO의 16-byte C-string 슬롯, 즉 최대 15 payload bytes 안에 들어가므로 추가 축약은 하지 않았다.

이전 Batch 1에서 선별적으로 적용했던 번역 및 임의 short-name 보정은 폐기했다. 몬스터의 명시 plural/short 변형도 업로드된 기존 번역에 실제 대응값이 있는 필드만 남겼다.

원본 대응 매핑은 재현 및 추적을 위해 `korean/translation/scenario_legacy_reference.json`에 보존한다.

## 적용 결과

- 아이템 기존 번역 적용: 218
- 몬스터 name: 13
- 몬스터 name_plural: 11
- 몬스터 short_name: 19
- 몬스터 short_name_plural: 15
- NPC name: 1
- 합계: 277

SCENARIO 번역 CSV의 명시 행 수는 713개다.

- item/name: 452
- monster/name: 186
- monster/name_plural: 11
- monster/short_name: 19
- monster/short_name_plural: 15
- npc/name: 30

명시 번역이 없는 SCENARIO 필드는 기존 fallback 규칙으로 전체 1,223개 필드를 계속 커버한다.

## 검증

GitHub Actions `Korean Localization CI` run #13:

- pytest: 40 passed
- SCENARIO explicit translation rows: 713
- full translation rows audited: 5,433
- custom glyphs: 1,011 / 1,024
- glyph headroom: 13
- encoding failures: 0
- glyph limit exceeded: false

따라서 전체 기존 번역 치환 후에도 런타임 1,024 glyph 제한과 SCENARIO 필드 크기 제한을 모두 만족한다.
