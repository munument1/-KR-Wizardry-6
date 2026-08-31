# Korean localization workspace

이 디렉터리는 Wizardry VI DOS 한국어화 전용 작업 공간이다.

초기에는 다음 자산을 이 아래에 정리한다.

- `translation/`: 추출한 원문, 번역문, 용어집과 검증용 메타데이터
- `tools/`: 한국어 인코딩, 메시지 재압축, 패치 생성 및 정적 감사 도구
- `fonts/`: 게임에 직접 포함되지 않는 글리프 맵·생성 스크립트·폰트 변환 설정
- `patches/`: 원본 파일 자체가 아닌 재현 가능한 차분/패치 정의
- `tests/`: 메시지 round-trip, 제어코드, 인코딩 경계, 패치 바이트 검증

## 현재 추출 도구

- `tools/extract_messages.py`: `MSG.HDR`/`MSG.DBS`/`MISC.HDR`에서 개별 message ID를 손실 없이 추출하고 구조를 검증한다.
- `tools/audit_scenario_strings.py`: `SCENARIO.DBS`의 아이템/몬스터/NPC 고정 문자열을 구조적으로 추출하고 나머지 ASCII를 감사한다.
- `tools/scan_binary_strings.py`: `WROOT.EXE`와 `W*.OVR`의 ASCII를 보수적으로 분류해 실제 사용자 노출 후보를 찾는다.

상용 게임 원본 파일과 원본에서 파생된 전체 바이너리는 커밋하지 않는다. 생성 CSV도 원본 텍스트의 대량 재배포가 되지 않도록 기본적으로 로컬/작업 시트에서 관리한다.

기술 진행 상황은 `docs/KOREAN_LOCALIZATION_PLAN.md`와 `docs/KOREAN_TEXT_EXTRACTION_AUDIT.md`에 기록한다.
