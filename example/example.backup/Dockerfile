# docker build -t storyboard-serve . --no-cache
# docker run -p 3021:3000 storyboard-serve

FROM ghcr.io/astral-sh/uv:python3.11-alpine

WORKDIR /app

COPY . /app

RUN uv tool install --force storyboard-cli

EXPOSE 3000

CMD ["storyboard", "serve", "--port", "3000"]
