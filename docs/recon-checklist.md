# Phase 1 Recon Checklist

此文件列出真正開始寫 `routes/hike_aspnet.py` 前，必須親自登入 hike.taiwan.gov.tw 一次、對目標路線跑完整流程後，要從 DevTools 與抓回的 HTML 中確認的細節。研究 agent 給的多是推測值，全部需要實地驗證。

## 前置準備

```bash
cp .env.example .env
# 填入 HIKE_USERNAME / HIKE_PASSWORD / LEADER_*

hut-bot login
# 開啟 Chromium → 手動登入（含 CAPTCHA / OTP）→ 自動匯出 storage/auth_state.json

hut-bot recon-batch
# 抓所有候選 URL 存到 storage/form_fixtures/

# 或單獨抓一個
hut-bot recon --url https://hike.taiwan.gov.tw/applySearch.aspx --name applySearch
```

## 必須確認的項目

對每條目標路線（從首頁 → 申請主頁 → 路線選擇 → 表單 → 提交）需確認：

### A. URL 鏈

- [ ] 首頁 → 「登山申請」menu 連結指向哪？
- [ ] 「登山線上申請」連結指向哪？
- [ ] 路線選擇頁 URL（含 query string）
- [ ] 路線詳情/表單頁 URL
- [ ] 床位查詢 endpoint（`bed_0.aspx` 系列）
- [ ] 提交 endpoint（POST 的 action 屬性指向哪）
- [ ] 是否有「再次確認」頁？是 GET 還是 POST？URL 為何？

### B. 表單欄位（用 `recon` 印出的 hidden inputs 對照）

- [ ] `__VIEWSTATE` / `__VIEWSTATEGENERATOR` / `__EVENTVALIDATION` 是否齊全
- [ ] 是否有 `__VIEWSTATEENCRYPTED`（加密 viewstate）
- [ ] `__EVENTTARGET` / `__EVENTARGUMENT` 對應的按鈕值（提交鈕 / 下一步鈕）
- [ ] 全部非 hidden 欄位的 name（路線、日期、人數、領隊、隊員、同意聲明）
- [ ] 隊員是動態 row（用 `__doPostBack` 加減）還是固定欄位數
- [ ] 同意聲明 checkbox 的 name 與 value

### C. 提交流程

- [ ] 從表單頁送出後 server 是 redirect 還是直接 200 + HTML 回應？
- [ ] 成功 vs 失敗的 HTML 差異（例：含「申請成功」、「已額滿」、「VIEWSTATE 已過期」等中文字串）
- [ ] 失敗時回的 HTML 還能否複用？或必須重 GET 表單頁？
- [ ] 是否有反爬蟲：Cloudflare（看 cookie 名稱有沒有 `cf_clearance`）、reCAPTCHA（看頁面有沒有 `recaptcha` script）、WAF（看 status 有沒有 5xx 或特殊 message）

### D. 開放規則（用瀏覽器在不同日期測試）

- [ ] 申請窗口：入山日前幾天開放？（先到先得 vs 抽籤的判定）
- [ ] 開放整點是 07:00:00 還是其他？
- [ ] server 時區：在 06:59:55 跟 07:00:05 各嘗試送一次，看 server reject 或 accept

### E. cookie 與 header

- [ ] 用 DevTools Network tab 看真實 POST 帶了哪些 header（Referer / Origin / User-Agent）
- [ ] 哪些 cookie 是必要的（ASP.NET_SessionId、`.ASPXAUTH` 等）
- [ ] cookie 過期時間（會多久就要重 login）

## 把驗證結果填回計劃

確認完後，更新 `/root/.claude/plans/repo-compiled-riddle.md` 或本 repo 的 `docs/recon-result.md`，記錄真實值。然後再開 Phase 2 開始寫 `hike_aspnet.py`。

## 已知 hike.taiwan.gov.tw URL（待 recon 驗證）

| 用途 | URL（推測） |
|---|---|
| 首頁 | https://hike.taiwan.gov.tw/ |
| 登山申請主頁 | https://hike.taiwan.gov.tw/apply_1.aspx?search=2 |
| 路線搜尋 | https://hike.taiwan.gov.tw/applySearch.aspx |
| 申請進度 | https://hike.taiwan.gov.tw/apply_3.aspx |
| 床位查詢 | https://hike.taiwan.gov.tw/bed_0.aspx |
| 抽籤結果 | https://hike.taiwan.gov.tw/bed_3_1.aspx |
| 登入 | https://hike.taiwan.gov.tw/login.aspx |

`recon-batch` 會自動把這幾個 URL 都抓回來分析。
