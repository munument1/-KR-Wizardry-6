# Wizardry VI DOS 한국어화

GOG DOS판 `Wizardry VI: Bane of the Cosmic Forge`의 메시지, 메뉴, 아이템명, 몬스터/NPC 이름과 인트로 로고를 한국어로 표시하는 패치 빌드 도구다.

## 현재 범위

- 전체 MSG 원문 5,161개 검증, 번역 행 4,720개 적용
- `SCENARIO.DBS` 아이템 이름 452개 한글화
- `SCENARIO.DBS` 몬스터 186개 레코드의 단수/복수/짧은 이름 필드 한글화
- `SCENARIO.DBS` NPC 이름 30개 한글화
- 8x8 Galmuri7 기반 compact 글리프 코드북, 런타임 한도 1,024자
- 서술문 WFONT0과 메뉴 WFONT1..4의 원래 색상·배경·화면 버퍼 경로 보존
- `TITLEPAG.EGA` 한국어 인트로 로고 포함
- 메뉴 재진입, 구성원 추가, 저장 게임 불러오기, 던전 이동, 캐릭터/아이템 화면 DOSBox 실기 검증은 `v0.1.0-alpha.1` 기준 완료

## 빌드

상용 게임 원본과 Galmuri7 TTF/BDF는 저장소에 포함하지 않는다. 원본 GOG 게임 파일과 [Galmuri7](https://galmuri.quiple.dev/)을 준비한 뒤 다음 세 단계를 실행한다.

먼저 아이템 및 몬스터/NPC 번역표를 하나의 빌드 입력으로 병합한다.

```powershell
python korean/tools/merge_scenario_translations.py `
  --items korean/translation/scenario_items_ko.csv `
  --actors korean/translation/scenario_monsters_ko.csv `
  --output scratch/scenario_all_ko.csv
```

메시지와 전체 SCENARIO 번역을 함께 사용해 통합 글리프 코드북을 만든다. 이 단계에서 1,024자 한도를 넘으면 빌드가 중단된다.

```powershell
python korean/tools/build_korean_messages.py `
  --gamedata "D:/GOG/Wizardry 6 - GOG" `
  --translations korean/translation/messages_ko.csv `
  --extra-translations scratch/scenario_all_ko.csv `
  --output-dir scratch/build_msg_release
```

마지막으로 런타임 검증이 끝난 기존 WFONT0/WFONT1..4 렌더러를 그대로 사용하면서 전체 SCENARIO 이름 필드를 패치한다.

```powershell
python korean/tools/build_korean_patch_release.py `
  --game-dir "D:/GOG/Wizardry 6 - GOG" `
  --msg-build scratch/build_msg_release `
  --ttf "path/to/Galmuri7.ttf" `
  --bdf "path/to/Galmuri7.bdf" `
  --titlepag korean/assets/TITLEPAG.EGA `
  --scenario-translations scratch/scenario_all_ko.csv `
  --output-dir scratch/release `
  --zip Wizardry6-Korean-v0.1.0-alpha.2.zip
```

도구는 알려진 GOG 원본 SHA-256, 메시지 ID/범위, 1KB 뱅크 경계, 16바이트 SCENARIO 이름 필드(NUL 포함 최대 15바이트 데이터), 글리프 1,024자 한도, TTF/BDF 픽셀 일치와 런타임 셀 인코딩을 검증한다. SCENARIO 패처는 452개 아이템 이름, 741개 몬스터 표시 이름 필드, 30개 NPC 이름 등 총 1,223개 노출 필드가 실제로 변경되었는지도 확인한다.

## 설치

게임 폴더를 백업하고 릴리스 ZIP의 파일을 게임 폴더에 덮어쓴 뒤 평소처럼 실행한다. 기존 저장 파일은 ZIP에 포함되지 않는다.

Galmuri7은 SIL Open Font License 1.1로 제공된다. 폰트 저작권과 세부 사항은 `fonts/README.md`를 참고한다.
