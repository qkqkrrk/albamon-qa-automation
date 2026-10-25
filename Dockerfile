FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 타임존 설정 (KST) 및 필수 시스템 패키지 설치
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 출력 버퍼링 비활성화 (실시간 로그 확인용) 및 바이트코드 생성 방지
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 프로젝트 소스 코드 복사
COPY . .

# 리포트 및 스크린샷 저장 디렉토리 생성
RUN mkdir -p reports/screenshots

# 기본 실행 명령어 (pytest 실행 및 HTML 리포트 생성)
CMD ["pytest"]
