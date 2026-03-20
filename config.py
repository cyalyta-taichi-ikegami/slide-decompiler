"""システム全体の設定・定数"""
import os


# --- Google Cloud ---
GCP_PROJECT_ID: str = os.environ["GCP_PROJECT_ID"]
GCP_LOCATION: str = os.environ.get("GCP_LOCATION", "us-central1")
GCS_BUCKET: str = os.environ.get("GCS_BUCKET", "")

# --- AI モデル ---
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# Imagen 3 inpainting 用モデル
IMAGEN_MODEL: str = os.environ.get("IMAGEN_MODEL", "imagen-3.0-capability-001")

# --- スライドサイズ（16:9 標準） ---
SLIDE_WIDTH_INCHES: float = 13.333
SLIDE_HEIGHT_INCHES: float = 7.5
SLIDE_WIDTH_EMU: int = int(SLIDE_WIDTH_INCHES * 914_400)   # ≈ 12,192,912
SLIDE_HEIGHT_EMU: int = int(SLIDE_HEIGHT_INCHES * 914_400)  #  = 6,858,000

# --- EMU 変換定数 ---
EMU_PER_INCH: int = 914_400
EMU_PER_PT: int = 12_700
PT_PER_INCH: int = 72

# --- タイポグラフィ調整係数 ---
# PowerPoint のバウンド高さ（≒フォントサイズの1.2倍）を吸収する係数
FONT_SIZE_TUNING_FACTOR: float = 0.83

# --- Imagen 3 インペインティング品質設定 ---
MASK_DILATION: float = 0.015    # 1.5%（画像幅比）。文字のアンチエイリアスを確実に除去
INPAINT_BASE_STEPS: int = 20    # 12〜75 推奨。品質↑ ⇔ レイテンシ↑

# --- API リトライ設定 ---
MAX_RETRY_ATTEMPTS: int = 5
RETRY_MIN_WAIT_SEC: int = 2
RETRY_MAX_WAIT_SEC: int = 60

# --- 並列処理設定 ---
# Vertex AI の TPM クォータを超えないよう同時スライド処理数を制限する
MAX_CONCURRENT_SLIDES: int = int(os.environ.get("MAX_CONCURRENT_SLIDES", "3"))
