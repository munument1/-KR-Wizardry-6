# Korean localization workspace

이 디렉터리는 Wizardry VI DOS 한국어화 전용 작업 공간이다.

초기에는 다음 자산을 이 아래에 정리한다.

- `translation/`: 추출한 원문, 번역문, 용어집과 검증용 메타데이터
- `tools/`: 한국어 인코딩, 메시지 재압축, 패치 생성 및 정적 감사 도구
- `fonts/`: 게임에 직접 포함되지 않는 글리프 맵·생성 스크립트·폰트 변환 설정
- `patches/`: 원본 파일 자체가 아닌 재현 가능한 차분/패치 정의
- `tests/`: 메시지 round-trip, 제어코드, 인코딩 경계, 패치 바이트 검증

## 현재 추출 / 감사 도구

- `tools/extract_messages.py`: `MSG.HDR`/`MSG.DBS`/`MISC.HDR`에서 개별 message ID를 손실 없이 추출하고 구조를 검증한다.
- `tools/audit_scenario_strings.py`: `SCENARIO.DBS`의 아이템/몬스터/NPC 고정 문자열을 구조적으로 추출하고 나머지 ASCII를 감사한다.
- `tools/scan_binary_strings.py`: `WROOT.EXE`와 `W*.OVR`의 ASCII를 보수적으로 분류해 실제 사용자 노출 후보를 찾는다.
- `tools/xref_wroot_strings.py`: MZ/DGROUP 구조를 이용해 WROOT 평문 문자열의 실제 정적 참조를 확인한다. 현재 사용자 노출/진단 후보 12개가 참조됨을 검증한다.
- `tools/export_image_text_previews.py`: 32768-byte 전체화면 EGA 이미지와 `CREDITS.PIC` 프레임을 로컬 PNG로 디코드해 이미지 내 텍스트를 육안 감사한다.
- `tools/extract_system_tables.py`: `MSG.DBS` 안의 고정 ID 테이블(종족/직업/능력치/직업 랭크/상태이상/마법/스킬 등) 367개를 구조화 인덱스로 추출한다.
- `tools/roundtrip_messages.py`: 기존 `MISC.HDR` Huffman 트리로 5,161개 메시지를 decode→encode하여 원본 `MSG.DBS`와 비트/해시 단위 동일성을 검증한다.
- `tools/rebuild_message_files.py`: 번역 바이트를 받아 `MSG.DBS`/`MSG.HDR`/`MISC.HDR`를 함께 재생성한다. 무수정 identity 모드와 256바이트 새 Huffman 트리 모드를 지원한다.
- `tools/korean_codec.py`: 번역에 실제 사용된 비ASCII 글자만 고밀도 2바이트 코드북으로 인코딩/디코딩한다. 현재 런타임 예산은 2,048글자다.
- `tools/build_translation_codebook.py`: 번역 CSV를 읽어 코드북과 길이/글리프 수 감사 보고서를 생성한다.
- `tools/audit_text_renderer.py`: WROOT/EGA.DRV의 문자열 루프, 드라이버 호출, resident zero cave 원본 시그니처를 수정 없이 검증한다.
- `fonts/build_galmuri7_bitmap_table.py`: 로컬 `Galmuri7.kbitx`에서 코드북에 실제 필요한 글리프만 8바이트 셀 테이블로 생성한다.

## 폰트

한국어 기본 폰트는 **Galmuri7(갈무리7)** 로 정했다. 원본 WFONT는 8x8/128글자 구조이므로 전체 한글표를 싣지 않고, 번역에 실제 사용된 비ASCII 글자만 compact codebook 순서로 8바이트 글리프 셀에 변환한다. 문자열은 ASCII/control 1바이트 + custom glyph 2바이트 형식을 사용한다.

세부 구현 및 라이선스 주의사항은 `fonts/README.md`를 참고한다.

상용 게임 원본 파일과 원본에서 파생된 전체 바이너리는 커밋하지 않는다. 생성 CSV/PNG도 원본 텍스트·그래픽의 대량 재배포가 되지 않도록 기본적으로 로컬/작업 시트에서 관리한다.

기술 진행 상황은 `docs/KOREAN_LOCALIZATION_PLAN.md`, `docs/KOREAN_TEXT_EXTRACTION_AUDIT.md`, `docs/KOREAN_WROOT_XREF_AND_IMAGE_AUDIT.md`, `docs/KOREAN_MSG_ROUNDTRIP.md`, `docs/KOREAN_COMPACT_RENDERER_PLAN.md`에 기록한다.
