# Taiwan Hut Booking Bot

自動化在台灣登山申請一站式服務網（[hike.taiwan.gov.tw](https://hike.taiwan.gov.tw/)）每天 07:00:00 整點搶先到先得制山屋床位。

## 重要

- MVP 範圍：**hike.taiwan.gov.tw（ASP.NET WebForms）上的先到先得制路線**
- **不**支援抽籤制路線（嘉明湖避難山屋、玉山排雲、雪山主峰等）— 抽籤無時間優勢
- **不**支援林業署 PHP 子站（`*.forest.gov.tw`）— 待 ASP.NET 流程穩定後再擴充
- 本機執行，不做通知，只寫結構化 log

## 架構

```
07:00:00 前 (T-10s 預熱)             07:00:00.000 觸發             07:00:00.x 結果
──────────────────────              ───────────────              ────────────
Playwright 互動登入             →   APScheduler + NTP 校時   →   解析回應 HTML
匯出 storage_state.json             + 自旋鎖整點命中             寫入 logs/
                               →   httpx (HTTP/2) GET 表單 →   失敗則重試
                                    取最新 __VIEWSTATE           直到 07:01:00
                               →   POST 送出
```

## 安裝（使用 uv）

需先安裝 [uv](https://docs.astral.sh/uv/)（`winget install astral-sh.uv` 或 `pip install uv`）。

```powershell
uv sync --extra dev               # 依 pyproject.toml + uv.lock 建 .venv 並裝 deps（含 dev）
uv run playwright install chromium # 下載 Chromium
Copy-Item .env.example .env       # 填入帳密與領隊資料
```

`.python-version` 已固定為 3.11；uv 會自動找到對應的解譯器（沒裝會自動下載）。

## 使用

所有指令都用 `uv run` 前綴（或先 `.\.venv\Scripts\Activate.ps1` 啟動 venv 再直接 `hut-bot ...`）。

```powershell
# 1. 互動登入（會開瀏覽器，手動完成 CAPTCHA / OTP）
uv run hut-bot login

# 2. Phase 1 必經：抓 apply_1 / applySearch / apply_3 / bed_0 等候選頁
uv run hut-bot recon-batch
# 或單抓一頁
uv run hut-bot recon --url https://hike.taiwan.gov.tw/apply_1.aspx --name apply_1

# 3. Dry-run：完整跑 GET → 組 payload → 印出但不送
uv run hut-bot dry-run --route <route_id> --start-date 2026-06-01 --nights 1 --people 4

# 4. 立即搶（debug 用，不等 07:00）
uv run hut-bot grab --route <route_id> --start-date 2026-06-01 --nights 1 --people 4

# 5. 排程：常駐進程，每天 06:59:50 預熱 → 07:00:00.000 觸發 → 重試到 07:01:00
uv run hut-bot schedule --route <route_id> --start-date 2026-06-01 --nights 1 --people 4
```

## 開發狀態

| Phase | 內容 | 狀態 |
|---|---|---|
| 0 | 骨架（基礎模組、CLI skeleton、login + recon 可跑）| 完成 |
| 1 | Recon 工具（checklist + recon-batch + 合成 fixture） | 工具完成；實地執行待 user |
| 2 | `hike_aspnet.py` RouteHandler（基於合成 fixture，欄位名標 `RECON_TODO`） | 完成（待 recon 後校正欄位名） |
| 3 | `dry-run` / `grab` CLI 串接 poster | 完成 |
| 4 | `schedule` 整合 APScheduler + precise_wait | 完成 |

## Phase 1 Recon 待 user 執行

我（Claude）無法操作瀏覽器互動登入，且 hike.taiwan.gov.tw 真實欄位名是 agent 推測值。請執行：

```powershell
uv run hut-bot login         # 開瀏覽器手動登入，匯出 storage/auth_state.json
uv run hut-bot recon-batch   # 抓所有候選 URL 存到 storage/form_fixtures/
```

然後依 `docs/recon-checklist.md` 核對 `src/hut_bot/routes/hike_aspnet.py` 與 `routes/catalog.py` 中所有標 `# RECON_TODO:` 的位置，覆蓋為真實欄位名／URL／按鈕值。

## 結構

```
src/hut_bot/
├── cli.py                   Typer CLI entry
├── config.py                Pydantic Settings（讀 .env）
├── logging_setup.py         structlog 設定
├── auth/playwright_login.py 互動登入、匯出 storage_state.json
├── routes/
│   ├── base.py              RouteHandler 抽象 + dataclass
│   ├── catalog.py           路線目錄
│   └── hike_aspnet.py       hike.taiwan.gov.tw ASP.NET handler
├── grabber/
│   ├── client.py            httpx Client factory（HTTP/2、預熱）
│   ├── viewstate.py         __VIEWSTATE 等 hidden inputs parser
│   └── poster.py            主搶票迴圈（重試到 07:01:00）
└── scheduling/
    ├── cron.py              APScheduler 排程
    └── precise_wait.py      NTP 校時 + 自旋鎖
```

## 注意事項

- `storage/auth_state.json` 含登入 cookie，**已 gitignore**，請勿提交
- `.env` 含帳密，**已 gitignore**
- 此工具僅供個人使用，請遵守 hike.taiwan.gov.tw 服務條款與保育法規
