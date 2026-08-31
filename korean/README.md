# Korean localization workspace

이 디렉터리는 Wizardry VI DOS 한국어화 전용 작업 공간이다.

초기에는 다음 자산을 이 아래에 정리한다.

- `translation/`: 추출한 원문, 번역문, 용어집과 검증용 메타데이터
- `tools/`: 한국어 인코딩, 메시지 재압축, 패치 생성 도구
- `fonts/`: 게임에 직접 포함되지 않는 글리프 맵·생성 스크립트·폰트 변환 설정
- `patches/`: 원본 파일 자체가 아닌 재현 가능한 차분/패치 정의
- `tests/`: 메시지 round-trip, 제어코드, 인코딩 경계, 패치 바이트 검증

상용 게임 원본 파일과 원본에서 파생된 전체 바이너리는 커밋하지 않는다.

기술 진행 상황은 `docs/KOREAN_LOCALIZATION_PLAN.md`에 기록한다.
