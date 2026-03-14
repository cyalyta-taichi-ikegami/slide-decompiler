# ベースイメージ（Python 3.11 slim）
FROM python:3.11-slim

# システムパッケージ（LibreOffice + フォント）のインストール
# LibreOffice Impress で PPTX → PNG 変換に使用する
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-impress \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存ライブラリを先にインストール（キャッシュを活かすため COPY . . より前）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# Cloud Run Jobs はコマンド実行後に終了する
ENTRYPOINT ["python", "main.py"]
