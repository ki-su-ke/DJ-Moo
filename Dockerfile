FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# appUser (UID: 1000) を作成
RUN useradd -m -u 1000 appUser

# 依存関係のインストール（root権限）
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 所有権を appUser に変更してコピー
COPY --chown=appUser:appUser . /app/

# 実行ユーザーを appUser に変更
USER appUser
