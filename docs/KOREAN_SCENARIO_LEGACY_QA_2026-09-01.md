# Wizardry VI SCENARIO 번역 QA 기록

Date: 2026-09-01

사용자가 제공한 `Wizardry 6 - Scenario` 워크북에는 Wizardry VII에서 이미 번역된 SCENARIO 대응 항목이 포함되어 있었다. 기존 Wizardry VI SCENARIO 데이터는 검증되지 않은 초벌번역이었으므로, 대응되는 기존 번역은 기존 번역 우선으로 전면 교체하고 나머지 미매칭 필드는 Wizardry VI 원문을 기준으로 별도 QA했다.

## 전체 데이터 범위

- SCENARIO 필드 전체: 1,223
- 아이템 이름: 452
- 몬스터 필드: 741
  - name: 186
  - name_plural: 185
  - short_name: 185
  - short_name_plural: 185
- NPC 이름: 30

최종 CSV에서는 1,223개 필드를 모두 명시적으로 관리한다. 더 이상 몬스터 plural/short 필드를 전체 이름 fallback에 의존하지 않는다.

## 기존 번역 277개 전면 반영

기존 번역이 연결된 필드는 다음과 같다.

- 아이템 name: 218
- 몬스터 name: 13
- 몬스터 name_plural: 11
- 몬스터 short_name: 19
- 몬스터 short_name_plural: 15
- NPC name: 1
- 합계: 277

대응되는 277개 필드는 전부 기존 번역으로 교체했다. Wizardry VII 데이터에서 줄바꿈/분리 표식으로 사용된 `/`만 제거했다. 정규화된 번역은 모두 Wizardry VI의 16-byte C-string 슬롯, 즉 최대 15 payload bytes 안에 들어간다.

원본 대응 매핑은 `korean/translation/scenario_legacy_reference.json`에 보존한다.

## 미매칭 946개 전수 QA

나머지 946개 필드는 Wizardry VI 원문 이름과 아이템/몬스터 원문 자료를 기준으로 검수했다.

주요 작업:

- 기계번역식 직역·음역 오류 아이템 이름 교정: 128개
- 몬스터 정식 이름 추가 교정: 65개
- NPC 이름 교정: 3개
- 몬스터 185종의 `name_plural`, `short_name`, `short_name_plural`을 모두 명시적으로 작성
- 한국어에서는 단수/복수 형태를 별도로 굴절하지 않으므로 plural 필드는 검수된 동일 한국어 명칭 사용
- short name은 원문의 generic identity를 기준으로 별도 작성

예시:

- `SWORD=LADING`: `적재의검` → `레이딩검`
- `HORN=PROMETHEUS`: `혼=프로메테우스` → `프로메테우스뿔`
- `LEAD BOOTS`: `리드장화` → `납장화`
- `ROBE=ENCHANT(U/L)`: `법의=인챈트상/하` → `마법로브상/하`
- `CHAIN=DESPAIR`: `사슬=절망` → `절망의사슬`
- `VASPESS`: `독개미` → `바스페스`
- `NIGHTGAUNT`: `밤악마` → `나이트건트`
- `GREMLIN`: `작은악마` → `그렘린`
- `D R A C U L A`: `흡혈왕` → `드라큘라`

상세 변경 이력은 `korean/translation/scenario_unmatched_review_2026-09-01.json`에 기록한다. 재현용 QA 스크립트는 `korean/tools/finalize_scenario_unmatched_qa.py`다.

## 최종 명시 행 수

- item/name: 452
- monster/name: 186
- monster/name_plural: 185
- monster/short_name: 185
- monster/short_name_plural: 185
- npc/name: 30
- 합계: 1,223

## 검증

`Finalize unmatched Scenario QA` 성공 실행 결과:

- pytest: 40 passed
- SCENARIO explicit translation rows: 1,223
- full translation rows audited: 5,943
- custom glyphs: 1,016 / 1,024
- glyph headroom: 8
- encoding failures: 0
- glyph limit exceeded: false
- 모든 SCENARIO 출력 문자열: 최대 15 payload bytes 이내

따라서 277개 기존 번역 전면 반영과 946개 미매칭 필드 QA 후에도 런타임 1,024 glyph 제한과 SCENARIO 필드 크기 제한을 모두 만족한다.
