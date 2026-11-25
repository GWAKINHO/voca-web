# 단어장 웹 앱 (voca-web)

영단어를 일차별로 외우고, 가중치 기반 시험으로 약점을 확인하며, 학습·시험 이력을 SQLite DB로 관리·통계화하는 서버 렌더링 웹 앱입니다.  
AI기반 프로그래밍 기말 과제(2026-2)로 제작되었으며, 학교 서버에서 `/2026/voca-<학번>/` 주소로 실행됩니다.

---

## 구현한 요구사항 목록

### 기능 요구사항 (기본 전체 완료)
| 영역 | ID | 내용 |
|---|---|---|
| 단어 관리 | `VOCA-FR-001` | 영단어와 뜻 직접 입력 등록 |
| 단어 관리 | `VOCA-FR-002` | 단어 목록 조회, 수정, 삭제 (배정·암기 이력 연쇄 삭제, 시험 문항 스냅샷 보존) |
| 단어 관리 | `VOCA-FR-003` | UTF-8 BOM CSV 일괄 가져오기 (중복 건너뛰기, 형식 오류 행 번호 안내) |
| 단어 관리 | `VOCA-FR-004` | 영단어·뜻 부분 일치 검색 (대소문자 무시) |
| 암기 | `VOCA-FR-011` | 하루 학습량(10개) 기준 일차별 진도 자동 배정 |
| 암기 | `VOCA-FR-012` | 오늘 일차 플래시카드 한 장씩 보기 (영단어 → 뜻 보기) |
| 암기 | `VOCA-FR-013` | 2일차부터 전날 단어(최대 5개) + 자주 틀린 단어(최대 3개) 복습 섞기 |
| 암기 | `VOCA-FR-014` | 카드 넘김 시 암기 이력(`study_log`) DB 저장 |
| 시험 | `VOCA-FR-021` | 문제 수(1~50) 지정 출제 (단어 부족 시 가능한 수만큼 출제·안내) |
| 시험 | `VOCA-FR-022` | 가중치 비례 중복 없는 출제 (기본 1 + 미시험 3 + 7일 경과 2 + 오답률 50% 이상 2) |
| 시험 | `VOCA-FR-023` | 출제 방향 선택 (영→한, 한→영, 섞기) |
| 시험 | `VOCA-FR-024` | 단답형·4지선다 2종 지원 및 혼합 출제 (보기 부족 시 단답형 자동 전환) |
| 시험 | `VOCA-FR-025` | 채점 결과(점수·정답률) 및 틀린 문항·정답 표시 (제출 후 재채점 방지) |
| 시험 | `VOCA-FR-026` | 시험 회차(`exam_attempt`) 및 문항 스냅샷(`exam_item`) DB 저장 |
| 통계 | `VOCA-FR-031` | 진도 현황 (현재 일차, 암기한 단어 수 / 전체 단어 수) |
| 통계 | `VOCA-FR-032` | 시험 성적 추이 (날짜별·회차별 정답률) |
| 통계 | `VOCA-FR-033` | 자주 틀리는 단어 상위 10개 목록 |
| 통계 | `VOCA-FR-034` | 모든 통계를 DB 이력 테이블에서 직접 집계 |
| 부가 기능 | 데이터 설계서 §6.1 | 단어장 전체 초기화 (`"전체삭제"` 서버 확인 + 단일 트랜잭션 초기화) |

### 비기능·제출 요구사항
- `VOCA-NFR-001 ~ 005`: 서버 렌더링 웹(Flask + Jinja2), SQLite(`DB_PATH`), 시작 시 테이블 자동 생성, 환경변수 `SECRET_KEY`, Dockerfile 배포 규칙 준수
- `VOCA-SUB-001 ~ 037`: 공개 리포, `README.md`, `CLAUDE.md`, `docs/` 산출물(개발방법론·기획서·요구사항명세서·아키텍처설계서·데이터설계서), `Dockerfile`(UID 10001, `0.0.0.0:8080`, 상대 경로), `.github/workflows/docker-check.yml`

---

## 고른 DB

**SQLite** (`DB_PATH` 환경변수, 컨테이너 기본값 `/data/voca.db`, 로컬 기본값 `data/voca.db`).  
앱 기동 시 `init_db()`가 테이블(`words`, `study_day`, `plan`, `study_log`, `exam_attempt`, `exam_item`)과 인덱스를 자동 생성합니다.

---

## 실행 방법

### 로컬 실행 (Windows / Python 3.12+)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 8080
```

브라우저에서 `http://127.0.0.1:8080/` 을 엽니다.

### 단위 테스트 실행

```powershell
$env:PYTHONIOENCODING = "utf-8"
py -3.12 -m unittest discover -s tests -p "test_*.py" -t .
```

### Docker 실행

```bash
docker build -t voca-web .
docker run --rm -p 8080:8080 -v voca-data:/data voca-web
```

---

## 폴더 구조

```text
voca-web/
├── app.py                         # Flask 앱 생성, DB 초기화, Blueprint 등록
├── config.py                      # 환경변수(DB_PATH, SECRET_KEY) 및 KST·상수
├── db.py                          # SQLite 연결, 스키마 자동 생성
├── routes/                        # Blueprint (words, study, exam, stats)
├── services/                      # 비즈니스 로직 (word_service, word_import, study_service, exam_service, stats_service)
├── templates/                     # Jinja2 서버 렌더링 템플릿
├── static/style.css               # 화이트·블루 기본 스타일
├── tests/                         # unittest 단위 테스트 (37개)
├── docs/                          # 개발방법론, 기획서, 요구사항명세서, 아키텍처설계서, 데이터설계서
├── Dockerfile                     # 배포용 이미지 (python:3.13-slim, UID 10001, gunicorn)
└── .github/workflows/docker-check.yml   # 학교 제공 점검 워크플로 (수정 금지)
```
