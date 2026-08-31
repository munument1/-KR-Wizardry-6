# Wizardry VI DOS 한국어화

GOG DOS판 `Wizardry VI: Bane of the Cosmic Forge`의 메시지, 메뉴, 아이템명과 인트로 로고를 한국어로 표시하는 패치 빌드 도구다.

## 현재 범위

- 전체 MSG 원문 5,161개 검증, 번역 행 4,720개 적용
- `SCENARIO.DBS` 아이템 이름 452개 한글화
- 8x8 Galmuri7 기반 1,020자 compact 글리프 코드북
- 서술문 WFONT0과 메뉴 WFONT1..4의 원래 색상·배경·화면 버퍼 경로 보존
- `TITLEPAG.EGA` 한국어 인트로 로고 포함
- 메뉴 재진입, 구성원 추가, 저장 게임 불러오기, 던전 이동, 캐릭터/아이템 화면 DOSBox 실기 검증

## 빌드

상용 게임 원본과 Galmuri7 TTF/BDF는 저장소에 포함하지 않는다. 원본 GOG 게임 파일과 [Galmuri7](https://galmuri.quiple.dev/)을 준비한 뒤 다음 두 단계를 실행한다.

```powershell
python korean/tools/build_korean_messages.py `
  --gamedata "D:/GOG/Wizardry 6 - GOG" `
  --translations korean/translation/messages_ko.csv `
  --extra-translations korean/translation/scenario_items_ko.csv `
  --output-dir scratch/build_msg_release

python korean/tools/build_korean_patch.py `
  --game-dir "D:/GOG/Wizardry 6 - GOG" `
  --msg-build scratch/build_msg_release `
  --ttf "path/to/Galmuri7.ttf" `
  --bdf "path/to/Galmuri7.bdf" `
  --titlepag korean/assets/TITLEPAG.EGA `
  --scenario-translations korean/translation/scenario_items_ko.csv `
  --output-dir scratch/release `
  --zip Wizardry6-Korean.zip
```

도구는 알려진 GOG 원본 SHA-256, 메시지 ID/범위, 1KB 뱅크 경계, 16바이트 아이템명 필드, 글리프 수, TTF/BDF 픽셀 일치와 런타임 셀 인코딩을 검증한다.

## 설치

게임 폴더를 백업하고 릴리스 ZIP의 파일을 게임 폴더에 덮어쓴 뒤 평소처럼 실행한다. 기존 저장 파일은 ZIP에 포함되지 않는다.

Galmuri7은 SIL Open Font License 1.1로 제공된다. 폰트 저작권과 세부 사항은 `fonts/README.md`를 참고한다.
