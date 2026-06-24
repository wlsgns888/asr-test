# 프로젝트 개요: 사내 회의록 자동화 로컬 앱 개발

## 1. 목표

녹음 파일을 업로드하면 로컬 ASR 모델로 음성을 텍스트로 변환하고, LLM API를 호출하여 사용자가 원하는 형식의 회의록을 생성하는 시스템을 개발한다.

초기 개발환경과 실제 사용환경이 다르므로, 환경 차이를 고려한 구조로 설계한다.

## 2. 핵심 요구사항

### 기능 요구사항

1. 사용자가 녹음 파일을 업로드할 수 있어야 한다.
2. 업로드된 오디오 파일을 로컬에서 ASR 처리하여 전사문을 생성한다.
3. 초기 개발 단계에서는 ASR 모델로 Qwen3-ASR 계열 중 가장 작은 모델을 사용한다.
4. 전사 결과를 LLM API에 전달하여 회의록을 생성한다.
5. 사용자가 원하는 회의록 포맷을 적용할 수 있어야 한다.
6. 향후 화자구분이 가능하면 추가한다.
7. 모델은 회의록 변환 작업 시에만 로드하고, 작업 종료 후 자원을 회수하는 구조를 지향한다.
8. 결과물은 Markdown과 JSON 중심으로 저장한다.

### 비기능 요구사항

1. 실제 운영환경에서는 외부 AI API를 사용할 수 없다.
2. 실제 운영환경에서는 회사에서 제공하는 OpenAI 호환 규격의 사내 LLM API를 호출할 예정이다.
3. 초기 개발 단계에서는 z.ai API를 호출하여 LLM 기능을 대체한다.
4. ASR은 맥북 로컬에서 실행 가능해야 한다.
5. 개발환경과 실제 사용환경이 다르므로 환경별 설정을 분리해야 한다.

## 3. 환경 구분

### 개발환경

* 장비: 개인 Mac mini
* 용도: 초기 개발 및 PoC
* ASR: Qwen3-ASR 가장 작은 모델 사용
* LLM: z.ai API 호출
* API Key: `.env` 파일의 `ZAI_API_KEY`로 관리
* 외부 API 사용 가능

### 실제 사용환경

* 장비: 회사에서 사용하는 MacBook
* 용도: 실제 사내 사용
* ASR: MacBook 로컬 실행
* LLM: 회사 내부 OpenAI 호환 API 호출
* 외부 AI API 사용 불가
* API endpoint, model name, api key는 환경변수로 분리

## 4. 초기 기술 선택

### ASR

초기 개발 단계에서는 Qwen3-ASR의 가장 작은 MLX 모델을 사용한다.

우선 후보:

```text
mlx-community/Qwen3-ASR-0.6B-4bit
```

설치 및 실행은 `mlx-audio` 기반으로 검토한다.

ASR 처리 방식:

```text
오디오 파일 업로드
→ ffmpeg로 wav 변환
→ Qwen3-ASR MLX 모델로 전사
→ 전사 결과 저장
```

### LLM

초기 개발 단계에서는 z.ai API를 사용한다.

다만 코드 구조는 실제 운영환경에서 사내 OpenAI 호환 API로 쉽게 교체할 수 있도록 작성한다.

LLM 클라이언트는 다음 환경변수를 사용하도록 설계한다.

```env
LLM_PROVIDER=zai
LLM_BASE_URL=https://api.z.ai/api/paas/v4
LLM_API_KEY=${ZAI_API_KEY}
LLM_MODEL=사용할_모델명
```

운영환경에서는 다음처럼 교체 가능해야 한다.

```env
LLM_PROVIDER=internal
LLM_BASE_URL=https://internal-llm.company.local/v1
LLM_API_KEY=${INTERNAL_LLM_API_KEY}
LLM_MODEL=internal-model-name
```

API는 OpenAI 호환 규격을 기준으로 구현한다.

## 5. 보안 주의사항

1. API Key는 코드에 직접 작성하지 않는다.
2. API Key는 `.env` 파일 또는 OS 환경변수로 관리한다.
3. `.env` 파일은 Git에 커밋하지 않는다.
4. `.gitignore`에 `.env`, 업로드 파일, 전사 결과, 회의록 결과물을 포함한다.
5. 로그에는 API Key, 회의 전문, 민감정보를 남기지 않는다.
6. 실제 운영환경에서는 외부 API 호출이 발생하지 않도록 설정을 분리한다.

## 6. 권장 프로젝트 구조

```text
meeting-minutes-asr/
  app/
    main.py
    config.py

    routes/
      upload.py
      transcribe.py
      minutes.py

    services/
      audio_service.py
      asr_service.py
      llm_service.py
      minutes_service.py

    workers/
      qwen3_asr_worker.py

    schemas/
      transcript.py
      minutes.py

  data/
    uploads/
    wav/
    transcripts/
    minutes/

  scripts/
    test_asr.py
    test_llm.py

  .env.example
  .gitignore
  requirements.txt
  README.md
```

## 7. 처리 플로우

### 1단계: 파일 업로드

사용자가 `mp3`, `m4a`, `wav` 등의 녹음 파일을 업로드한다.

업로드 파일은 임시 디렉토리에 저장한다.

```text
data/uploads/
```

### 2단계: 오디오 전처리

`ffmpeg`를 사용하여 ASR에 적합한 형식으로 변환한다.

권장 포맷:

```text
wav
16kHz
mono
```

예시:

```bash
ffmpeg -i input.m4a -ar 16000 -ac 1 output.wav
```

### 3단계: ASR 전사

초기 개발에서는 Qwen3-ASR 0.6B 4bit 모델을 사용한다.

ASR은 가능하면 별도 subprocess 또는 worker 프로세스로 실행한다.

이유:

```text
- 모델 로드/언로드를 명확히 하기 위해
- 작업 종료 후 메모리 회수를 쉽게 하기 위해
- FastAPI 메인 서버가 모델을 계속 들고 있지 않도록 하기 위해
```

출력은 최소한 아래 구조로 저장한다.

```json
{
  "model": "mlx-community/Qwen3-ASR-0.6B-4bit",
  "language": "ko",
  "text": "전사된 전체 텍스트",
  "segments": []
}
```

초기에는 segment timestamp가 없어도 된다.
나중에 ForcedAligner 또는 chunk 기반 timestamp를 추가한다.

### 4단계: 회의록 생성

전사 결과를 LLM API에 전달하여 회의록을 생성한다.

LLM 호출은 OpenAI 호환 Chat Completions 형식으로 작성한다.

초기 개발에서는 z.ai API를 사용하지만, 실제 운영환경에서는 사내 OpenAI 호환 API로 교체할 수 있어야 한다.

회의록 생성 프롬프트는 다음 구조를 사용한다.

```text
너는 사내 회의록 작성 전문가다.
아래 전사문을 기반으로 회의록을 작성한다.
내용을 과장하거나 없는 내용을 추가하지 않는다.
불명확한 내용은 "확인 필요"로 표시한다.

[출력 형식]
- 회의 개요
- 주요 논의사항
- 결정사항
- 액션아이템
- 후속 확인사항

[전사문]
...
```

### 5단계: 결과 저장

생성된 회의록은 다음 형식으로 저장한다.

```text
Markdown
JSON
```

docx와 PDF export는 고려하지 않는다.

## 8. 환경변수 설계

`.env.example` 파일을 만든다.

```env
APP_ENV=development

# ASR
ASR_ENGINE=qwen3_asr_mlx
ASR_MODEL=mlx-community/Qwen3-ASR-0.6B-4bit
ASR_LANGUAGE=ko

# LLM
LLM_PROVIDER=zai
LLM_BASE_URL=https://api.z.ai/api/paas/v4
LLM_API_KEY=
LLM_MODEL=

# Storage
DATA_DIR=./data
UPLOAD_DIR=./data/uploads
TRANSCRIPT_DIR=./data/transcripts
MINUTES_DIR=./data/minutes
```

실제 `.env` 파일에는 개발자가 별도로 API Key를 입력한다.

## 9. LLM 클라이언트 구현 요구사항

OpenAI SDK 또는 HTTP client를 사용한다.

중요한 점은 provider가 바뀌어도 서비스 코드가 바뀌지 않도록 추상화하는 것이다.

예상 인터페이스:

```python
class LLMClient:
    def generate_minutes(self, transcript: str, template: str) -> str:
        ...
```

내부에서는 환경변수에 따라 base_url, api_key, model을 설정한다.

예시 구조:

```python
from openai import OpenAI

client = OpenAI(
    base_url=settings.LLM_BASE_URL,
    api_key=settings.LLM_API_KEY,
)
```

## 10. ASR 서비스 구현 요구사항

ASR 서비스도 모델 교체가 가능하도록 추상화한다.

예상 인터페이스:

```python
class ASREngine:
    def transcribe(self, audio_path: str) -> dict:
        ...
```

초기 구현:

```text
Qwen3ASRMlxEngine
```

향후 fallback 후보:

```text
WhisperCppEngine
MlxWhisperEngine
```

초기에는 Qwen3-ASR만 구현해도 된다.
다만 인터페이스는 모델 교체를 고려해서 작성한다.

## 11. 1차 개발 범위

우선 아래 범위까지만 구현한다.

```text
1. FastAPI 서버 생성
2. 파일 업로드 API
3. ffmpeg 오디오 변환
4. Qwen3-ASR 0.6B 4bit 전사 실행
5. 전사 결과 JSON 저장
6. z.ai LLM API 호출
7. 회의록 Markdown 생성
8. 회의록 JSON 생성
9. 결과 조회 API
```

UI는 초기에는 필수 아님.
API와 CLI 테스트가 가능하면 된다.

## 12. 제외 범위

초기 개발에서는 아래 기능은 제외한다.

```text
- 화자구분
- 정확한 word-level timestamp
- docx export
- PDF export
- 사용자별 로그인
- 회의록 템플릿 관리 UI
- 사내 LLM API 연동
```

단, 구조상 나중에 일부 기능을 추가할 수 있도록 한다.
다만 docx/PDF export는 현재 프로젝트 범위에서 고려하지 않는다.

## 13. 추후 확장 계획

### 2차

```text
- Qwen3-ASR 1.7B 4bit 테스트
- Whisper large-v3-turbo fallback 추가
- chunk 기반 timestamp 추가
- 회의록 템플릿 선택 기능
```

### 3차

```text
- Qwen3-ForcedAligner 테스트
- 화자구분 모델 연동
- 실제 회사 MacBook 환경 테스트
- 사내 OpenAI 호환 LLM API로 교체
```

## 14. 개발 시 주의사항

1. 개발환경은 개인 Mac mini이고 실제 사용환경은 회사 MacBook이다.
2. 하드웨어 성능 차이가 있을 수 있으므로 모델 크기와 메모리 사용량을 측정해야 한다.
3. ASR 모델은 작업 단위로 로드/해제 가능한 구조를 우선한다.
4. LLM API는 개발환경과 운영환경이 다르므로 반드시 설정으로 분리한다.
5. API Key와 민감정보는 코드에 넣지 않는다.
6. 실제 회의 녹음은 민감정보일 수 있으므로 로그와 저장 정책을 주의한다.
7. 초기에는 정확도보다 전체 파이프라인 완성을 우선한다.
8. 이후 사내 회의 녹음 샘플로 Qwen3-ASR 0.6B, Qwen3-ASR 1.7B, Whisper fallback을 비교한다.
9. 결과물은 Markdown과 JSON으로 한정한다.

## 15. 우선 구현 순서

1. 프로젝트 skeleton 생성
2. `.env.example`, config loader 작성
3. 파일 업로드 API 작성
4. ffmpeg 변환 함수 작성
5. Qwen3-ASR worker 작성
6. 전사 결과 저장 구조 작성
7. LLM client 작성
8. 회의록 생성 service 작성
9. Markdown/JSON 결과 저장 작성
10. API 테스트용 script 작성
11. README에 실행 방법 정리

## 16. 최종 목표 아키텍처

```text
사용자
→ 로컬 웹앱 또는 API
→ 오디오 업로드
→ ffmpeg 전처리
→ Qwen3-ASR MLX 로컬 전사
→ 전사 JSON 저장
→ LLM API 호출
    - 개발: z.ai
    - 운영: 사내 OpenAI-compatible API
→ 회의록 Markdown/JSON 생성
→ 사용자 검수
```
