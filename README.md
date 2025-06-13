# PoscoZerothon

# 상품 뉴스 분석 및 요약 시스템

이 프로젝트는 상품 관련 뉴스를 자동으로 분석하고 일일 요약을 생성하는 시스템입니다.

## 주요 기능

### 1. 뉴스 분석 (analyze_news.py)
- 상품 관련 뉴스 기사를 자동으로 수집하고 분석
- GPT 모델을 활용하여 뉴스의 감성 점수(0-100) 산출
- 주요 키워드 추출 및 분석 결과 저장
- 지원 상품: 옥수수, 밀, WTI 원유, 금, 구리

### 2. 일일 요약 생성 (create_daily_summary.py)
- 분석된 뉴스 데이터를 기반으로 일일 시장 요약 생성
- 주요 이슈 및 트렌드 정리
- 시장 동향 분석 결과 제공

### 3. API 서버 (app.py)
- Flask 기반의 웹 API 서버
- `/run-all` 엔드포인트를 통해 전체 분석 프로세스 실행
- 분석 및 요약 결과를 JSON 형식으로 반환

### 4. n8n 워크플로우 (zerothon_n8n_최종)
- n8n을 활용한 자동화 워크플로우 구성
- 정기적인 뉴스 분석 및 요약 생성 자동화
- 결과 데이터 처리 및 저장 자동화

## 시스템 요구사항
- Python 3.x
- PostgreSQL 데이터베이스
- OpenAI API 키
- n8n 서버

## 환경 설정
1. `.env` 파일에 다음 환경 변수 설정:
   - OPENAI_API_KEY
   - DB_HOST
   - DB_NAME
   - DB_USER
   - DB_PASSWORD

## 실행 방법
1. API 서버 실행:
```bash
python app.py
```

2. 수동 분석 실행:
```bash
python analyze_news.py
python create_daily_summary.py
```

3. n8n 워크플로우 설정:
- n8n 대시보드에서 `zerothon_n8n_최종` 워크플로우 가져오기
- 필요한 환경 변수 설정
- 워크플로우 활성화 
