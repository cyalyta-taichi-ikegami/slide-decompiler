# slide-decompiler

> フラット化されたスライド画像（PNG/JPEG）を解析し、  
> 背景画像 ＋ 編集可能テキストボックスに分解して `.pptx` として再構成する  
> AI 駆動のリバースエンジニアリング・パイプライン。

---

## 概要

「画像として書き出されてしまった複雑なスライド」を  
**元のレイアウトを維持したまま編集可能な PowerPoint ファイルに自動変換**するシステム。

既存の AI スライド生成ツール（Microsoft Copilot / Gemini for Slides など）が  
「ゼロから生成」に特化しているのに対し、本プロジェクトは  
ラスター画像→構造化ドキュメントへの **逆コンパイル（Decompilation）** を行う。

---

## 処理フロー

```
入力: .pptx（スライドが画像化されたもの）
  │
  ▼
[0] PPTX → PNG 変換（LibreOffice headless）
  │
  ▼（各スライドを asyncio で並列処理）
  │
  ├─[1] Gemini 解析  ─────────────────────────────────────────
  │      スライド画像内の全要素（テキスト/図形/背景）を検出
  │      → 正規化座標 (0-1000)・色・テキスト内容を JSON 出力
  │
  ├─[2] バイナリマスク生成（Pillow / CPU 処理）
  │      除去対象要素の領域を白、背景を黒で描いた PNG マスクを動的生成
  │
  ├─[3] Imagen 3 インペインティング ─── ┐ ← この2つは並列実行
  │      テキスト・図形を除去し        │
  │      背景のみの画像を AI で補完     │
  │                                    │
  ├─[4] Gemini 翻訳（日→英一括）  ─── ┘
  │      全テキストを 1 API コールで翻訳
  │
  ▼
[5] python-pptx 組み立て
     修復済み背景画像をスライド全面に敷き
     翻訳済みテキストボックスを EMU 座標で重ねる
  │
  ▼
出力: 編集可能な .pptx
```

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| AI 解析 / 翻訳 | Gemini 3.1 Pro (`gemini-3.1-pro-preview`) |
| インペインティング | Vertex AI Imagen 3 (`imagen-3.0-capability-001`) |
| スライド生成 | `python-pptx` |
| 画像処理 | `Pillow` |
| データモデル | `Pydantic v2`（Gemini 構造化出力のスキーマ） |
| リトライ制御 | `tenacity`（指数的バックオフ） |
| 実行基盤 | **Cloud Run Jobs**（タイムアウトなし・最大 24 時間） |
| PNG 変換 | LibreOffice headless |
| クラウド | Google Cloud / Vertex AI |

---

## タイムアウト対策

本システムは 1 スライドあたり数十秒〜数分の API 処理が発生する。  
以下の設計でタイムアウトを回避する。

| 対策 | 詳細 |
|---|---|
| **Cloud Run Jobs** | HTTP リクエストタイムアウトなし。最大 24 時間実行可能 |
| **asyncio 並列処理** | `asyncio.gather` で全スライドを並列投入 |
| **Semaphore** | `MAX_CONCURRENT_SLIDES`（デフォルト 3）で同時実行数を制限し TPM クォータを保護 |
| **インペイント & 翻訳の並列化** | スライド内でもこの 2 ステップは独立なので同時実行 |
| **tenacity リトライ** | 429 / 503 エラーで指数的バックオフ。最大 5 回リトライ |
| **翻訳の一括化** | スライド内の全テキストを 1 回の API コールで処理 |

---

## 座標変換の数学

Gemini は **正規化座標（0〜1000）** で出力する。  
これを PowerPoint の内部座標系 **EMU（English Metric Units）** へ変換する。

```
1 inch = 914,400 EMU
1 pt   = 12,700  EMU
スライドサイズ（16:9）: 13.333 inch × 7.5 inch

PPTX_Left  = (x_min / 1000) × Slide_Width_EMU
PPTX_Top   = (y_min / 1000) × Slide_Height_EMU
PPTX_Width = ((x_max - x_min) / 1000) × Slide_Width_EMU
```

**フォントサイズ推定式：**

```
H_inches  = (y_max - y_min) / 1000 × 7.5
H_points  = H_inches × 72
font_pt   = H_points × 0.83   ← PowerPoint バウンド高さ補正係数
```

翻訳で文字列が長くなった場合は `TextFrame.fit_text()` で動的縮小。

---

## インペインティングの品質チューニング

| パラメータ | デフォルト値 | 意味 |
|---|---|---|
| `MASK_DILATION` | `0.015`（1.5%） | マスクを膨張させてアンチエイリアスのハロー現象を防ぐ |
| `INPAINT_BASE_STEPS` | `20` | 反復回数。品質↑ ⇔ レイテンシ↑（12〜75 推奨） |

これらは `config.py` または環境変数で変更可能。

---

## ファイル構成

```
slide-decompiler/
├── config.py                       # 全定数・環境変数
├── main.py                         # エントリーポイント・オーケストレーター
├── Dockerfile                      # Cloud Run Jobs 用コンテナ
├── requirements.txt
├── models/
│   └── slide_elements.py           # Pydantic スキーマ（Gemini 構造化出力用）
├── pipeline/
│   ├── analyzer.py                 # Gemini 解析レイヤー
│   ├── inpainter.py                # Imagen 3 インペインティングレイヤー
│   ├── translator.py               # Gemini 翻訳レイヤー
│   ├── assembler.py                # python-pptx 組み立てレイヤー
│   └── slide_processor.py          # 1 スライド分のパイプライン（非同期）
└── utils/
    ├── coordinate_mapper.py        # 正規化座標 → EMU / フォントサイズ推定
    ├── mask_generator.py           # バイナリマスク画像生成
    └── pptx_to_images.py           # PPTX → PNG 変換（LibreOffice）
```

---

## セットアップ

### 環境変数の設定

`.env.example` を `.env` にコピーして値を入力してください。  
`.env` は `.gitignore` に含まれており、Git に追跡されません。

```bash
cp .env.example .env
# .env を編集して GCP_PROJECT_ID などを設定
```

> **注意：** `service_account*.json` などの認証情報ファイルは絶対にコミットしないでください。  
> Cloud Run Jobs では Workload Identity を使用し、サービスアカウントキーファイルを使わない認証を推奨します。

### 必須環境変数

| 変数名 | 説明 |
|---|---|
| `GCP_PROJECT_ID` | Google Cloud プロジェクト ID |

### 任意環境変数

| 変数名 | デフォルト | 説明 |
|---|---|---|
| `GCP_LOCATION` | `us-central1` | Vertex AI リージョン |
| `GEMINI_MODEL` | `gemini-3.1-pro-preview` | 使用する Gemini モデル名 |
| `IMAGEN_MODEL` | `imagen-3.0-capability-001` | 使用する Imagen モデル名 |
| `MAX_CONCURRENT_SLIDES` | `3` | 同時処理スライド数 |
| `INPUT_PATH` | — | 入力 PPTX パス（`--input` の代替） |
| `OUTPUT_PATH` | — | 出力 PPTX パス（`--output` の代替） |

---

## ローカル実行

```bash
# 依存インストール（要 LibreOffice）
pip install -r requirements.txt

# 実行
export GCP_PROJECT_ID=your-project-id
python main.py --input deck.pptx --output deck_en.pptx --lang en
```

---

## Cloud Run Jobs へのデプロイ

```bash
# コンテナのビルドとプッシュ
gcloud builds submit --tag gcr.io/$GCP_PROJECT_ID/slide-decompiler

# ジョブ作成（タイムアウト 24 時間）
gcloud run jobs create slide-decompiler \
  --image gcr.io/$GCP_PROJECT_ID/slide-decompiler \
  --set-env-vars GCP_PROJECT_ID=$GCP_PROJECT_ID \
  --set-env-vars INPUT_PATH=/gcs/input.pptx \
  --set-env-vars OUTPUT_PATH=/gcs/output.pptx \
  --task-timeout 86400 \
  --region us-central1

# ジョブ実行
gcloud run jobs execute slide-decompiler --region us-central1
```

> **GCS との連携について**  
> Cloud Run Jobs では `/gcs/` にバケットをマウントする方法（Cloud Storage FUSE）が使える。  
> 大きな PPTX ファイルは HTTP 転送を避けて GCS 経由でやり取りするのが推奨。

---

## 既知の課題・今後の改善点

- [ ] LibreOffice 依存を排除（`pdf2image` + `pypdfium2` への移行検討）
- [ ] GCS 入出力ヘルパーの追加（`google-cloud-storage` は `requirements.txt` に含み済み）
- [ ] スライドごとの中間結果（マスク画像・背景画像）を GCS に保存してデバッグを容易に
- [ ] Imagen 3 の出力解像度が入力と異なる場合のリサイズ処理
- [ ] 複数言語ペアへの対応（現在は日→英のみ）
- [ ] Power Point フォントファミリーの自動推定

---

## ライセンス

MIT
