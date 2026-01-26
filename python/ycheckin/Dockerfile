#see: https://docs.astral.sh/uv/guides/integration/docker/
FROM ghcr.io/astral-sh/uv:alpine3.22

COPY . /app

ENV UV_NO_DEV=1

WORKDIR /app
RUN uv tool install flask
RUN uv sync --locked

CMD ["uvx", "flask", "--app", "server", "run", "--host", "0.0.0.0", "--port", "8080"]
