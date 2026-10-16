FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.lock ./
RUN pip install -r requirements.lock
COPY pyproject.toml ./
COPY knowgraph ./knowgraph
COPY data ./data
RUN pip install --no-deps . && useradd --create-home app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "knowgraph.api:app", "--host", "0.0.0.0", "--port", "8000"]
