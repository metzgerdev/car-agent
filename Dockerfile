# Build the Vite frontend into the FastAPI package's static-web directory.
FROM node:22-bookworm-slim AS frontend

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm --prefix frontend ci

COPY frontend ./frontend
COPY src/car_agent/web ./src/car_agent/web
RUN npm --prefix frontend run build


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Hugging Face runs Docker Spaces as UID 1000.
RUN useradd --create-home --uid 1000 user

WORKDIR /home/user/app

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY --from=frontend /build/src/car_agent/web ./src/car_agent/web

RUN pip install .

USER user

EXPOSE 7860

CMD ["uvicorn", "car_agent.app:app", "--host", "0.0.0.0", "--port", "7860"]
