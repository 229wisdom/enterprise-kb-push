# 企业级分级知识库 —— 镜像构建配方
# 构建: docker build -t enterprise-kb:v1 .
# 运行: 见根目录 docker-compose.yml（推荐）或 docker run
FROM python:3.11-slim

# OCR（rapidocr 内的 opencv）需要的系统库
RUN apt-get update && apt-get install -y --no-install-recommends libxcb1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用镜像层缓存：依赖没变就不重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再 COPY 代码（代码常变，放最后）
COPY app/ app/
COPY scripts/ scripts/

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
