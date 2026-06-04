FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=secret,id=github_token \
    git config --global \
      url."https://x-access-token:$(cat /run/secrets/github_token)@github.com/".insteadOf \
      "https://github.com/" && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
