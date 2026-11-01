# InternFit

이력서와 채용공고를 비교해 지원 우선순위를 검토하는 웹서비스입니다. DOCX/PDF 이력서와 공고 URL 또는 본문을 입력하면 적합도 점수, 필수요건 경고, 경험 근거와 보완 방향을 보여줍니다.

## 프로젝트와 코드 읽기

- **[한국어 코드 설명 및 AI 활용 기록](docs/CODE_EXPLANATION_KR.md)** — 서비스 목적, 입력부터 결과까지의 흐름, 주요 파일, LLM과 Python 평가의 역할, DB 구성, 개발 과정의 AI 활용과 현재 확인 범위.
- [LLM 동작](docs/llm.md)
- [분석 기록 및 Supabase 저장](docs/telemetry.md)
- [설계 결정](docs/decisions.md)
- [변경 이력](CHANGELOG.md)

## 구성

웹 화면은 `internfit_web/index.html`, 요청 처리는 `internfit_web/server.py`, 파싱·평가·LLM·기록 기능은 `internfit/core/`에 있습니다. Docker와 Render 실행 설정도 저장소에 포함돼 있습니다.

LLM은 경험과 공고의 의미 해석 및 설명을 보조합니다. 최종 점수와 필수요건, 감점·상한은 Python에서 계산합니다. 유효한 LLM 결과가 없으면 규칙 기반으로 동작합니다.

## 로컬 실행

저장소 루트에서 실행합니다.

```bash
python -m pip install -r internfit_web/requirements.txt
python internfit_web/server.py 8000
```

`http://127.0.0.1:8000`에서 확인할 수 있습니다. API 키 없이 규칙 기반으로 실행할 수 있습니다. LLM·Supabase 및 OCR 설정은 위 설명 문서를 참고하세요.

이 점수는 내부 기준에 따른 지원 우선순위 참고값이며 채용 결과 예측값이 아닙니다.
