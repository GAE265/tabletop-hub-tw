# 手動測試：規則書入庫的資料表與 OCR 整合層

> 適用變更：`games-manual-table`（`games_manual` 資料表與覆蓋寫入）、`ocr-integrations`（版面分析與視覺模型介面）。
> 這兩個變更**還沒有 API 端點**，所以這份流程用後端的健康檢查、資料庫查詢與小段 Python 腳本驗證；之後有 `PUT /api/v1/games/{game_id}/manual-pages/{page}` 時再補。
> 本檔只寫欄位名與預期結果，**不要把金鑰、密碼貼進來**。

## 0. 前置條件

1. 已照 [README 的「本機啟動」](../README.md#本機啟動) 建好 `.env`、啟動資料庫並安裝後端套件（`uv sync`）。
2. `.env` 要多填 OCR 相關設定（欄位說明見 `.env.example` 的「OCR 與視覺模型」段落）：

   | 欄位 | 用途 | 案例 1–3 | 案例 4 |
   |---|---|---|---|
   | `DATABASE_URL`、`AUTH_MODE=dev` | 資料庫與開發模式 | 需要 | 不需要 |
   | `OCR_PROVIDER=cloud` | 使用真的 Azure | 不需要 | 需要 |
   | `OCR_DI_ENDPOINT`、`OCR_DI_API_KEY` | Azure Document Intelligence | 不需要 | 需要 |
   | `LLM_ENDPOINT`、`LLM_API_KEY`、`LLM_MODEL` | Azure OpenAI 視覺模型（`OCR_VISION_MODEL` 有填就優先用它） | 不需要 | 需要 |

3. 升級資料庫到最新版（`0003` 會建立 `games_manual`）：

   ```bash
   cd backend
   uv run alembic upgrade head
   ```

> 案例 4 會真的呼叫 Azure，產生費用（每次約 4 次呼叫，不到 NTD 1）。圖片都是腳本用 Pillow 現場畫的英文字，不含任何規則書內容。
> Pillow 是開發用套件，`uv sync` 預設會一起安裝。

---

## 案例 1：後端啟動與健康檢查

```bash
cd backend
uv run uvicorn app.main:create_app --factory --reload
```

另開終端機：

```bash
curl -i http://localhost:8000/api/v1/health
```

| 預期 | 說明 |
|---|---|
| `HTTP/1.1 200 OK` | 後端起來了 |
| 回應內容 `{"status":"ok","database":"up"}` | 資料庫連得上 |
| 瀏覽器開 <http://localhost:8000/docs> 看得到 OpenAPI 頁面 | 正常 |

看完用 `Ctrl+C` 停掉 uvicorn，後面的案例不需要它。

## 案例 2：`games_manual` 資料表與約束

把下面的腳本存成 `backend/manual_case_schema.py`（已列入 `.gitignore`，不會被提交），執行：

```bash
cd backend
uv run python manual_case_schema.py
```

```python
from sqlalchemy import create_engine, text

from app.core.config import get_settings

with create_engine(get_settings().database_url).connect() as conn:
    print(conn.execute(text("select version_num from alembic_version")).scalar())
    rows = conn.execute(
        text(
            "select conname, pg_get_constraintdef(oid) from pg_constraint "
            "where conrelid = 'games_manual'::regclass order by 1"
        )
    )
    for name, definition in rows:
        print(name, "|", definition)
```

預期輸出：

```text
0003
ck_games_manual_page_positive | CHECK ((page >= 1))
games_manual_games_id_fkey | FOREIGN KEY (games_id) REFERENCES games(id)
games_manual_pkey | PRIMARY KEY (games_id, page)
```

重點：外鍵後面**沒有** `ON DELETE CASCADE`（ADR 0003），並且有頁碼至少為 1 的檢查。

## 案例 3：依 `(games_id, page)` 覆蓋寫入

把下面的腳本存成 `backend/manual_case_upsert.py`（同樣已列入 `.gitignore`），執行：

```bash
cd backend
uv run python manual_case_upsert.py
```

腳本會新增一款編號 900001 的假桌遊，測完自動刪除，不會留下資料。

```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domains.rules_ingest.repository import GameNotFoundError, ManualPageRepository

GAME_ID = 900001  # 手動測試專用的假桌遊，結束時會刪掉
engine = create_engine(get_settings().database_url)


def pages(session: Session) -> dict[int, str]:
    rows = session.execute(
        text("SELECT page, content FROM games_manual WHERE games_id = :g ORDER BY page"),
        {"g": GAME_ID},
    )
    return {page: content for page, content in rows}


with Session(engine) as session:
    session.execute(
        text(
            "INSERT INTO games (id, bgg_id, name, english_name, min_players, max_players, "
            "min_playtime, max_playtime, min_age, weight, categories, mechanics) VALUES "
            "(:g, 990001, '手動測試桌遊', 'Manual Test Game', 2, 4, 30, 45, 10, 2.0, "
            "ARRAY['Card Game'], ARRAY['Hand Management'])"
        ),
        {"g": GAME_ID},
    )
    repo = ManualPageRepository(session)
    try:
        repo.upsert_page(GAME_ID, 9, "# 標題\n\n第一版內容")
        print("3-1 新增第 9 頁      ", pages(session))
        repo.upsert_page(GAME_ID, 9, "# 標題\n\n第二版內容")
        print("3-2 覆蓋第 9 頁      ", pages(session))
        repo.upsert_page(GAME_ID, 3, "")
        print("3-3 第 3 頁是空字串  ", pages(session))
        try:
            repo.upsert_page(999999, 1, "x")
        except GameNotFoundError as error:
            print("3-4 桌遊不存在       ", type(error).__name__, error)
    finally:
        session.rollback()
        with session.begin():
            session.execute(text("DELETE FROM games_manual WHERE games_id = :g"), {"g": GAME_ID})
            session.execute(text("DELETE FROM games WHERE id = :g"), {"g": GAME_ID})
        print("已清掉測試資料")
```

預期輸出：

```text
3-1 新增第 9 頁       {9: '# 標題\n\n第一版內容'}
3-2 覆蓋第 9 頁       {9: '# 標題\n\n第二版內容'}
3-3 第 3 頁是空字串   {3: '', 9: '# 標題\n\n第二版內容'}
3-4 桌遊不存在        GameNotFoundError 找不到桌遊 999999
已清掉測試資料
```

| 步驟 | 驗證的行為 |
|---|---|
| 3-1 | 沒有的頁會新增 |
| 3-2 | 同一頁再寫會取代內容，仍只有一列 |
| 3-3 | 空字串是合法內容（代表整頁沒文字），缺號的頁碼（第 3、9 頁）不影響 |
| 3-4 | 桌遊不存在時拋出 `GameNotFoundError`，不寫入 |

## 案例 4：Azure 版面分析、文字角度與視覺模型

需要 `.env` 填好案例 4 的欄位。把下面的腳本存成 `backend/manual_case_ocr.py`（同樣已列入 `.gitignore`），執行：

```bash
cd backend
uv run python manual_case_ocr.py
```

```python
import io

from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings
from app.integrations.llm.types import JsonSchema
from app.integrations.ocr import get_ocr_provider, get_vision_provider


def draw(lines: list[str], rotate: int = 0) -> bytes:
    image = Image.new("RGB", (1400, 700), "white")
    pen = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=72)
    for index, line in enumerate(lines):
        pen.text((60, 60 + index * 140), line, fill="black", font=font)
    if rotate:
        image = image.rotate(rotate, expand=True)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


settings = get_settings()
ocr = get_ocr_provider("cloud", settings)
vision = get_vision_provider("cloud", settings)

layout = ocr.analyze_layout(draw(["HELLO RULEBOOK", "SECOND LINE 2026"]))
print("4-1 版面分析  ", layout.width, layout.height, layout.unit, round(layout.angle, 1))
for line in layout.lines:
    print("   ", repr(line.text), "polygon 座標數", len(line.polygon))

print(
    "4-2 文字角度  正放",
    ocr.read_text_angle(draw(["UPRIGHT TEXT"])),
    "| 逆時針轉 90 度",
    ocr.read_text_angle(draw(["SIDEWAYS TEXT"], rotate=90)),
    "| 空白圖",
    ocr.read_text_angle(draw([])),
)

schema = JsonSchema(
    name="read_texts",
    schema={
        "type": "object",
        "properties": {"texts": {"type": "array", "items": {"type": "string"}}},
        "required": ["texts"],
        "additionalProperties": False,
    },
)
reply = vision.generate_json(
    instructions="你是逐字轉錄器。依圖片順序，各輸出一個字串，只含圖上的文字。",
    input="共有兩張圖，請依序轉錄。",
    images=[draw(["ALPHA ONE"]), draw(["BRAVO TWO"])],
    schema=schema,
)
print("4-3 視覺模型  ", reply)
```

預期輸出（角度與座標的小數可能略有不同）：

```text
4-1 版面分析   1400.0 700.0 pixel 0.1
    'HELLO RULEBOOK' polygon 座標數 8
    'SECOND LINE 2026' polygon 座標數 8
4-2 文字角度  正放 0.23385900259017944 | 逆時針轉 90 度 -90.0 | 空白圖 None
4-3 視覺模型   {'texts': ['ALPHA ONE', 'BRAVO TWO']}
```

| 步驟 | 驗證的行為 |
|---|---|
| 4-1 | `analyze_layout` 回傳頁面寬高 1400×700、單位 `pixel`、傾斜角接近 0，每行有文字與 8 個座標的 polygon |
| 4-2 | `read_text_angle`：正放約 0 度、側躺約 ±90 度、沒有文字回傳 `None`（之後的轉正流程靠它判斷） |
| 4-3 | `VisionProvider.generate_json` 帶兩張圖，依傳入順序回傳符合 schema 的 JSON |

## 案例 5：自動測試

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

預期全部通過。**注意：** 現有測試假設資料表在 `public` schema，若 `DATABASE_URL` 帶了 `options=-csearch_path=...`，要先在 shell 換成不帶 `options` 的連線字串再跑 `pytest`，否則測試資料庫建表會失敗。測試會在同一台資料庫伺服器建立 `<原資料庫名>_*` 的暫時資料庫。

直連 Azure 的外部服務測試（需要案例 4 的欄位，預設不執行）：

```bash
uv run pytest tests/integrations/test_ocr_external.py -m external
```

預期 `12 passed`。缺少任何一個必要欄位時會**直接失敗**並說明缺哪個設定，不會自動跳過。

## 常見問題

| 現象 | 原因與處理 |
|---|---|
| 案例 2 出現 `relation "games_manual" does not exist` | 還沒升級資料庫，執行 `uv run alembic upgrade head` |
| 案例 3 出現 `UniqueViolation` | 上次中斷時 900001 號假桌遊沒清掉，手動刪除 `games_manual` 與 `games` 中 `id = 900001` 的列 |
| 案例 4 出現 `OCRNotConfigured` | `.env` 缺欄位，錯誤訊息會列出缺哪些；`OCR_PROVIDER` 要填 `cloud` |
| 案例 4 出現 `OCRUnavailable` | Azure 連不上或逾時；確認網路與端點，或稍後重試 |
| 案例 4 出現 `OCRError`（401） | 金鑰錯誤；錯誤訊息不會包含金鑰本身 |
