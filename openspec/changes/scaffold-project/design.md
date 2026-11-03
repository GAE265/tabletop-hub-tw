# Design

## Context

repo 為空殼（見 proposal.md - Why）。本機已有 uv 0.13、Docker 29、Python 3.13（專案要求同為 3.13）；Flutter 輸出異常，由使用者先自行處理。現有 `README.md` 僅 2 行。分層規則以 AGENTS.md 第 4、5 節為準（已更新：UUID 主鍵、同步 DB、seed 不進 migration、`app/dev/` 為唯一例外區且任何地方不得 import 它、`GET /api/v1/dev/users`、`core/dev/` 身分切換器讀 API、`health` 由立倫代管、共用區擁有者表），本設計只記錄骨架的具體選擇。

## Goals / Non-Goals

**Goals:**
- 組員 clone 後依 README 跑起 DB、後端、前端，且 `ruff`／`pytest`／`flutter analyze`／`flutter test` 全綠。
- 把「容易各自發明」的東西一次定好：錯誤格式、目前使用者、測試身分 fixture、LLM 介面、斷點、參考畫面開關、換行符號。

**Non-Goals:**
- 不做 JWT、不做任何業務 domain、不做 MQTT 實際連線、不做 Azure 部署、不做 pgvector 資料表。

## 目錄與檔案用途

```
.gitignore                      排除 .env、各語言產物、系統檔（不排除 .env.example、uv.lock、pubspec.lock）
.gitattributes                  * text=auto eol=lf
.editorconfig                   縮排、LF、結尾換行
.env.example                    欄位名與說明（無值）
docker-compose.yml              postgres(pgvector) + mosquitto（匿名，僅本機）
README.md                       簡介、啟動步驟、Flutter 版本、分支與 commit 摘要
.github/pull_request_template.md  測試案例表格／是否動契約／needs-ui
.github/workflows/ci.yml        MR 到 dev/main 的檢查；MR1 建立並含 backend job，MR2 加 frontend job，MR3 加 device job
docs/handoff/_template.md       AGENTS.md 5.4 交接說明範本
backend/
  pyproject.toml, uv.lock       套件、ruff（行長100；E,F,I,B,UP）、pytest 設定
  alembic.ini, migrations/      env.py 讀 core 設定；versions/ 的 0001 migration
  app/main.py                   建立 app、掛 router、註冊錯誤處理器
  app/core/config.py            pydantic-settings 讀 .env（含 DEV_DEFAULT_USER_ID）
  app/core/db.py                同步 engine / session 依賴
  app/core/auth.py              CurrentUser、get_current_user、require_role
  app/core/errors.py            PermissionDenied、AppError、處理器
  app/integrations/llm/         base.py(LLMProvider)、fake.py、選擇函式
  app/domains/health/           router/schemas/service/repository
  app/domains/auth/models.py    AuthUser（僅 ORM 模型，不含 router）
  app/domains/booking/models.py BookingShop（僅 ORM 模型）
  app/dev/                      例外區，僅 AUTH_MODE=dev 啟用，立倫擁有
    accounts.py                 三個測試帳號與測試店家的 UUID（唯一定義處）
    seed.py                     seed 指令
    router.py                   GET /api/v1/dev/users
  tests/conftest.py, tests/health/, tests/core/, tests/migrations/, tests/dev/
frontend/lib/
  main.dart
  app/                          router、theme/
  core/api/                     dio client、錯誤處理、DevUser 攔截器
  core/dev/                     身分切換器（呼叫 /api/v1/dev/users，不存 UUID；僅開發環境）
  core/layout/                  斷點
  core/platform/                平台介面（骨架僅放空介面與說明）
  domains/health/{data,state,pages}
  prototypes/health/
device/
  README.md, pyproject.toml, uv.lock
  hardware/{camera,motor}.py    抽象介面
  hardware/mock_*.py            mock 實作
  tests/
```

## Decisions

**D1 `auth`、`booking` 只放 `models.py`。** `auth_users`／`booking_shops` 由 AGENTS.md 4.5 指定屬於這兩個 domain，故 ORM 模型放各自 domain，不建 router／service。替代方案：全放 `core/`——違反歸屬規則。

**D2 同步 psycopg 3 + SQLAlchemy 同步 session。** AGENTS.md 4.4 已規定，不再討論。

**D3 測試資料庫用真實 PostgreSQL。** health 與 migration 測試連本機／CI 的 pgvector 容器；service 單元測試用假 repository（7.4）。替代：SQLite——不支援 pgvector 與同款約束。

**D4 `get_current_user` 依 `AUTH_MODE` 分派。** `dev` 讀 `X-Dev-User`（`<user_uuid>:<role>[:<shop_uuid>]`，shop_staff 必帶店家、其他角色不得帶，違反回 400；`CurrentUser` 完全由請求資訊建立，core 不查任何資料表）；`jwt` 在骨架回 401（尚未實作）。`as_*` fixture 用 `app.dependency_overrides[get_current_user]` 覆寫，使用固定 UUID 的記憶體物件，不依賴資料庫或 seed。`CurrentUser` 為純 dataclass，`id` 型別為 `uuid.UUID`。

**D5 錯誤處理集中在 `core/errors.py`。** `AppError(status, code, message, details)` 為基底，`PermissionDenied` 為其子類（403）；另註冊 `HTTPException`、`RequestValidationError`、未預期 `Exception` 的處理器。

**D6 UUID 主鍵：伺服器預設 + 客戶端可指定。** 欄位 `UUID` 型別，`server_default=gen_random_uuid()`（PG13+ 內建，不需額外擴充），ORM 端 `default=uuid.uuid4`。這樣發牌機與 App 離線時可自產 ID（AGENTS.md 4.4）。role 約束用 `CHECK (role IN (...))` 而非 PG enum，方便日後增減。

**D7 測試帳號 UUID 只定義在 `backend/app/dev/accounts.py`。** 前端不存 UUID，身分切換器執行時呼叫 `GET /api/v1/dev/users` 取得（AGENTS.md 4.2、4.5）。唯一例外：dev 模式下「沒帶 `X-Dev-User`」的預設玩家需由 `core/auth.py` 判斷，而 `core` 不能 import `app/dev/`，所以預設玩家的 UUID 放在 `core/config.py` 的設定 `DEV_DEFAULT_USER_ID`，`app/dev/accounts.py` 的 player 帳號取用這個值。其餘兩個帳號與測試店家的 UUID 只在 `accounts.py`。替代：預設玩家改為資料庫查詢「第一個 player」——讓 core 依賴 `auth` 資料表且結果不穩定，不採用；見 Open Questions。

**D8 `app/dev/` 內容與規則。** `seed.py` 以 `uv run python -m app.dev.seed` 執行，用 `ON CONFLICT DO NOTHING` 確保可重複執行，`AUTH_MODE=jwt` 時拒絕執行；`router.py` 提供 `GET /api/v1/dev/users`，只回傳 `accounts.py` 列出的帳號（以 id 篩選，不是整張 `auth_users`）。依 AGENTS.md 4.2：`app/dev/` 可使用任何 domain，但任何地方（含測試）都不得 import 它。

**D9 條件掛載與不 import。** `main.py` 以 `create_app(settings)` 建立應用；只有 `settings.auth_mode == "dev"` 時才用 `importlib.import_module("app.dev.router")` 動態載入並掛載，`main.py` 沒有靜態 `import app.dev`。這樣 jwt 模式下 `app.dev` 模組根本不會被載入。測試分兩種：以 `create_app(dev 設定)` 與 `create_app(jwt 設定)` 驗證掛載與 404；seed 因為不能 import，測試以 subprocess 執行 `python -m app.dev.seed`，再透過 API 或資料庫驗證結果。靜態檢查（搜尋 `app.dev` import）以一個測試用 `ast` 掃描 `backend/` 完成。替代：`main.py` 直接 import 並以 if 掛載——違反「任何地方都不得 import」。

**D10 前端 API client 用 dio 攔截器加標頭。** 攔截器僅在開發環境（`kReleaseMode == false` 且 `--dart-define=DEV_USER_ENABLED` 未設為 false）加 `X-Dev-User`；目前身分以 Riverpod provider 保存。切換器 widget 與 provider 放 `frontend/lib/core/dev/`（AGENTS.md 4.5），在 `app/` 的頁面框架中以開發旗標條件掛載。

**D11 `/proto/...` 在 router 建構時依旗標決定是否加入。** 用 `bool.fromEnvironment('SHOW_PROTOTYPES')`。

**D12 CI 分三次加入，每個 MR 都有 CI 把關。** 同一個 `ci.yml`，三個獨立 job（互不 `needs`，一個失敗不擋其他）：MR 1 建立檔案與 backend job（`astral-sh/setup-uv` + `pgvector/pgvector:pg16` service container）；MR 2 加 frontend job（`subosito/flutter-action`，版本與 README 載明的同一個 stable 版本）；MR 3 加 device job（`uv sync`、`ruff check`、`ruff format --check`、`pytest`）。device 檢查已列入 AGENTS.md 8.3。Flutter 鎖定 stable 3.41.4（README 與 CI 相同）。

**D13 `device/` 自有 `pyproject.toml` 與 uv。** 跑在樹莓派，相依與後端不同。介面用 `typing.Protocol`／ABC，mock 與介面同套件。README 說明：`picamera2` 以 apt 安裝，虛擬環境以 `--system-site-packages` 建立（`uv venv --system-site-packages`）才讀得到。骨架不把 `picamera2` 列入相依。

**D14 Mosquitto 不另建設定目錄。** 使用映像檔內建的 `mosquitto-no-auth.conf`（`command: mosquitto -c /mosquitto-no-auth.conf`），避免新增頂層 `mosquitto/` 資料夾（規則 4）。

**D15 換行與編輯器。** `.gitattributes` 為 `* text=auto eol=lf`；`.editorconfig` 設 `end_of_line = lf`、`insert_final_newline = true`，Python 4 空白、Dart 2 空白、YAML 2 空白。屬使用者明確同意的規則 4 例外。

## 套件與版本（apply 時以實際解析結果鎖定並回填此表）

| 位置 | 套件 | 目標版本 | 理由 |
|---|---|---|---|
| backend | Python | 3.13 | AGENTS.md 1 |
| backend | fastapi, uvicorn[standard] | 最新穩定 | Web 框架與伺服器 |
| backend | sqlalchemy | 2.x | AGENTS.md 1 |
| backend | alembic | 最新穩定 | AGENTS.md 1 |
| backend | psycopg[binary] | 3.x | 同步 PG 驅動 |
| backend | pydantic-settings | 2.x | 讀 .env |
| backend | pgvector | 最新穩定 | 之後的向量欄位型別 |
| backend dev | pytest, httpx, ruff | 最新穩定 | 測試、TestClient、lint/format |
| frontend | Flutter SDK | 單一 stable 版本（apply 時以 `flutter --version` 鎖定，寫入 README 與 CI） | 不用 fvm |
| frontend | flutter_riverpod, go_router, dio, freezed_annotation, json_annotation | 最新穩定 | 5.1 預設套件 |
| frontend dev | freezed, json_serializable, build_runner | 與上列相容 | 產碼 |
| device | pytest（dev） | 最新穩定 | 測試 |
| infra | pgvector/pgvector:pg16, eclipse-mosquitto:2 | tag 固定，不用 latest | 可重現 |

我無法在規劃階段離線確認各套件當下最新版號，apply 第一步以 `uv add`／`flutter pub add` 解析後回填。`uv.lock` 與 `pubspec.lock` 一併提交。

## 本機啟動指令順序

```
cp .env.example .env                       # 填入本機值
docker compose up -d                       # postgres + mosquitto
cd backend && uv sync
uv run alembic upgrade head
uv run python -m app.dev.seed              # 建立三個固定 UUID 測試帳號
uv run uvicorn app.main:app --reload       # http://localhost:8000/docs
# 另開終端
cd frontend && flutter pub get
dart run build_runner build --delete-conflicting-outputs
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000 --dart-define=SHOW_PROTOTYPES=true
```

## Risks / Trade-offs

- [三個 MR 皆超過 400 行（規則 6）] → 骨架本質；MR 說明寫明，並讓審核者依檔案群組分段看。
- [CI 分次加入，MR 1 時 workflow 只有 backend job] → 合併順序固定為 MR 1 → MR 2 → MR 3；每個 MR 的 job 在該 MR 上實跑通過才合併。
- [一次動到多位組員的共用區] → MR 說明 @ 對應擁有者（MR 1：立倫、瑋鋐；MR 2：永傑；MR 3：新善）。
- [migration 合併後不可改] → 欄位只放 4.5 規定的最少欄位；UUID 型別與預設值在合併前由瑋鋐確認。
- [Mosquitto 本機匿名連線] → 部署到雲端時 MUST 啟用帳密（及 TLS），且 `.env.example` 預留 MQTT username／password 欄位，不得把匿名設定帶上雲端。
- [`/api/v1/dev/users` 洩漏帳號清單] → 只在 `AUTH_MODE=dev` 掛載，jwt 模式不存在（404、不在 OpenAPI）；`.env.example` 預設值註明正式環境必須為 jwt。
- [任何人誤 import `app/dev/`] → 以 `ast` 掃描測試擋下；`main.py` 用動態載入。
- [預設玩家 UUID 在 `core/config.py`，由 `app/dev/accounts.py` 讀取，並非嚴格單一處] → 已獲確認（D7）。
- [seed 誤在正式環境執行] → 指令在 `AUTH_MODE=jwt` 時拒絕執行（有測試）。
- [`FakeLLMProvider` 與 `LLM_PROVIDER=cloud` 未實作] → 明確報錯，不靜默退回 fake。
- [Flutter 本機環境目前異常] → 使用者先處理並通知後才 apply；MR 2 前以 `flutter doctor` 確認。
- [`.gitattributes` 的 `eol=lf` 對 Windows 本機工具] → 現代編輯器皆支援 LF；`.editorconfig` 同步設定。

## Open Questions

無。預設玩家 UUID 已確認採 D7 做法（`DEV_DEFAULT_USER_ID` 在 `core/config.py`，`accounts.py` 讀取）。
