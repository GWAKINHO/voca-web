# 단어장 웹 앱 (voca-web)

영단어를 일차별로 외우고, 시험으로 확인하며, 학습 이력을 DB에 저장하는 웹 앱입니다. AI기반 프로그래밍 기말 과제로 만들며, 학교 서버에서 `/2026/voca-<학번>/` 주소로 실행합니다.

> 현재 상태: 1차 제출 준비 단계입니다. 첫 화면만 구현되어 있습니다.

---

## 구현한 요구사항

| ID | 내용 | 상태 |
|---|---|---|
| VOCA-SUB-031 | 루트 `Dockerfile` 로 `docker build .` 가능 | 작성 완료, 점검 워크플로로 확인 예정 |
| VOCA-SUB-032 | 컨테이너가 `0.0.0.0:8080` 에서 응답 | 작성 완료, 점검 워크플로로 확인 예정 |

기능 요구사항(VOCA-FR-001~034)은 다음 단계에서 구현합니다. 기획서는 `docs/261125_기획서_v0.1.md` 를 봅니다.

## 고른 DB

**SQLite** (`DB_PATH` 환경변수, 기본값 `/data/voca.db`). 처음 실행할 때 테이블을 자동으로 만듭니다 (구현 예정).

## 실행 방법

### 로컬 (Python 3.13)

```powershell
py -3.12 -m pip install -r requirements.txt
py -3.12 -m gunicorn --bind 127.0.0.1:8080 app:app
```

> 참고: Windows에서 gunicorn 은 동작하지 않을 수 있습니다. 그때는 `py -3.12 -m flask --app app run --port 8080` 으로 확인하고, 최종 확인은 Docker 점검 워크플로로 합니다.

브라우저에서 `http://127.0.0.1:8080/` 을 엽니다.

### Docker

```bash
docker build -t voca-web .
docker run --rm -p 8080:8080 -v voca-data:/data voca-web
```

## 배포 점검

`.github/workflows/docker-check.yml` 은 push 할 때마다 학교 서버와 같은 조건으로 앱을 띄워 봅니다. Actions 탭에서 초록 체크를 확인합니다.

## 폴더 구조

```text
voca-web/
├── app.py                         # Flask 앱 (첫 화면)
├── templates/index.html           # 첫 화면 템플릿
├── requirements.txt               # 의존성 (버전 고정)
├── Dockerfile                     # 서버 배포용 이미지
├── docs/                          # 확정 산출물 (기획서 등)
└── .github/workflows/docker-check.yml   # 학교 제공 점검 워크플로 (수정 금지)
```
