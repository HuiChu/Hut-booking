# Phase 1 Recon Result — hike.taiwan.gov.tw 國家公園山屋申請

Source: `storage/recon/hike_taiwan_gov_tw.har`（2026-05-22 抓取，路線 cid=156 秀霸線）。
**所有欄位值都已 redact**，只記欄位名與結構。HAR 檔本身**不要 commit**（已 gitignore）。

## 申請流程（國家公園系列 apply_1 → 1_2 → 1_3）

```
1. GET  /                                                    （home）
2. GET  /login.aspx                                          （登入，含 CAPTCHA）
3. GET  /apply_1.aspx                                        （選路線）
4. POST /apply_1.aspx (__ASYNCPOST=true)                     （AJAX 顯示路線詳情）
5. GET  /apply_1_2.aspx?unit={UUID}&cid={N}&fid={N}&camp_id={N}
                                                             （顯示路線同意條款、選日期）
6. POST /apply_1_2.aspx?unit=...&cid=... → 302              （送出選擇）
                  Location: /apply_1_3.aspx?RandomStr={N}
7. GET  /apply_1_3.aspx?RandomStr=N                          （主表單頁）
8. POST /apply_1_3.aspx?RandomStr=N (__ASYNCPOST=true) × N   （每個欄位 AJAX postback）
9. POST /apply_1_3.aspx?RandomStr=N (btnsetp2upnext + vcode2)
                                                             （送出 step 2 → 跳 step 3 再次確認頁）
10. POST /apply_1_3.aspx?RandomStr=N (btnsave + vcode)
                                                             （最終送出，會真的訂位）★
```

**HAR 範圍**：cover 1–9，step 10（btnsave）user 在「再次確認頁」停手未按。

## URL pattern：路線 ↔ unit/cid/fid

每條路線在 catalog dropdown 的 `value="N"` 對應 unit UUID + cid + fid：

| 路線 | route_code (dropdown value) | unit UUID | cid | fid | camp_id |
|---|---|---|---|---|---|
| 秀霸線 | 156 | e6dd4652-2d37-4346-8f5d-6e538353e0c2 | 156 | 8 | 0 |

**待補**：其他 94 條路線的 unit/fid/camp_id。可以靠瀏覽器選每條路線後抓 URL（或 JS 內找 mapping），不需要全部 HAR。

## Step 7 (apply_1_3.aspx) 主表單 — 真實欄位名

所有欄位都用 ASP.NET WebForms 控件命名 `ctl00$con$<name>`，URL-encoded 後 `$` 變 `%24`。

### 申請人 (apply_*)
| 欄位 name | 用途 |
|---|---|
| `ctl00$con$apply_name` | 姓名 |
| `ctl00$con$apply_tel` | 電話（市話） |
| `ctl00$con$ddlapply_country` | 國別下拉 |
| `ctl00$con$ddlapply_city` | 城市下拉 |
| `ctl00$con$apply_addr` | 地址 |
| `ctl00$con$apply_mobile` | 手機（10碼） |
| `ctl00$con$apply_fax` | 傳真 |
| `ctl00$con$apply_email` | Email |
| `ctl00$con$apply_nation` | 國籍 UUID |
| `ctl00$con$apply_sid` | 身分證 |
| `ctl00$con$apply_sex` | 性別 |
| `ctl00$con$apply_birthday` | 生日 YYYY-MM-DD |
| `ctl00$con$apply_contactname` | 緊急聯絡人姓名 |
| `ctl00$con$apply_contacttel` | 緊急聯絡人電話 |
| `ctl00$con$copyapply` | 「同申請人」checkbox（複製到領隊） |

### 領隊 (leader_*) — 結構與申請人完全平行
`leader_name`, `leader_tel`, `ddlleader_country`, `ddlleader_city`, `leader_addr`, `leader_mobile`, `leader_fax`, `leader_email`, `leader_nation`, `leader_sid`, `leader_sex`, `leader_birthday`, `leader_contactname`, `leader_contacttel`

### 隊員 (lisMem repeater)
動態 row：`ctl00$con$lisMem$ctrl{N}$<field>`，N 從 1 開始。每位隊員 15 個欄位：

`num`, `m_id`, `member_name`, `member_tel`, `ddlmember_country`, `ddlmember_city`, `member_addr`, `member_mobile`, `member_email`, `member_nation`, `member_sid`, `member_sex`, `member_birthday`, `member_contactname`, `member_contacttel`

### 留守人 (stay_*)
`stay_name`, `stay_tel`, `stay_mobile`, `stay_fax`, `stay_email`, `stay_birthday`, `stay_nation`, `stay_sid`

### 床位 / 行程 (lisText repeater) — per 入山日
`ctl00$con$lisText$ctrl{day}$<field>`：`num`, `bedok`, `bakroomok`, `rooms`

### 其他
| 欄位 | 用途 |
|---|---|
| `ctl00$con$teams_name` | 隊伍名稱 |
| `ctl00$con$teams_count` | 人數 |
| `ctl00$con$climblinemain` | 主路線 |
| `ctl00$con$climbline` | 路線（值 = route code 如 "156"） |
| `ctl00$con$sumday` / `sumdays` | 行程總天數 |
| `ctl00$con$applystart` | 入山日 |
| `ctl00$con$setapply_date` / `setapply_outdate` | 入/出山日 |
| `ctl00$con$seminar` | 是否有研習證明 |
| `ctl00$con$satellitephone` | 衛星電話 |
| `ctl00$con$frequency` | 無線電頻率 |
| `ctl00$con$note_user` | 備註 |
| `ctl00$con$member_keytype` | 隊員資料輸入方式 |
| `ctl00$con$applycheck` | 同意聲明 checkbox |

### 隱藏 / 內部狀態
`hidapplystart`, `hidnowday`, `hidnowdaycount`, `hidarrayid`, `hidtype`, `Hidfinish`, `hidchange`, `hidclickmember`, `hidfinalid`, `Guid_Id`（apply session UUID）, `hA_id`, `Literal1`（server 渲染的 HTML）

### Step 2 送出鈕
`ctl00$con$btnsetp2upnext` (value=「下一步」34 chars URL-encoded)，必須帶 `ctl00$con$vcode2` (CAPTCHA)。

## Step 10 (apply_1_3 再次確認頁) — 第二個 CAPTCHA + 最終送出

按下「下一步」後，**同一個 URL** 回不同頁面（再次確認）。欄位：
- `ctl00$con$vcode` （**注意：不是 vcode2，是 vcode**，第二次 CAPTCHA）
- `ctl00$con$btnbak` （儲存草稿，__doPostBack）
- `ctl00$con$btnstep3uppre` （上一步）
- **`ctl00$con$btnsave` value=「確認送出」← 真正提交按這個** ★

## ASP.NET 基礎欄位（所有 POST 必帶）

```
__VIEWSTATE             ~34KB（apply_1_3 page）
__VIEWSTATEGENERATOR    D6CEF12D（apply_1_3）/ 7C795BA3（apply_1_2）
__VIEWSTATEENCRYPTED    (空字串，但仍須在 payload)
__EVENTVALIDATION       ~158 chars (apply_1_2) / 更長 (apply_1_3)
__EVENTTARGET           空字串=直接 form submit；填值=__doPostBack
__EVENTARGUMENT         (空)
__LASTFOCUS             (空)
__ASYNCPOST             true（AJAX UpdatePanel postback）/ 不帶（最終 form submit）
ctl00$ScriptManager1    AJAX manager（AJAX postback 才帶）
ctl00$googletxt         全站搜尋（空字串）
```

## CAPTCHA — 重要

**兩道 CAPTCHA**：
- `CheckImageCode.aspx` 回 GIF（~4KB）
- `vcode2` 在 step 2（送出表單）
- `vcode` 在 step 3（再次確認）

兩道都必須通過。沒有 JS 變動 — 純後端比對。後端 session 記憶碼，前端只負責顯示。

**對搶票的影響**：
- 07:00:00 開放後，**人手動填 CAPTCHA 至少 3–5 秒**，搶票速度優勢 100% 消失
- 唯一可行方案：
  1. **半自動**：07:00:00 前由 user 手動完成 apply_1 / apply_1_2 / 進入 apply_1_3 表單頁、填好欄位、解掉 vcode2 → bot 在 07:00:00.000 自動按 btnsetp2upnext → 跳 step 3 → user 再解 vcode → 按 btnsave。整段需要 user 在線。
  2. **OCR**：CheckImageCode.aspx 看起來不複雜，扭曲程度若不高 OCR 可能 work（80–95% 正確率）。失敗就 changevcode 換一張重試。
  3. **付費 anti-captcha 服務**：2captcha / Anti-Captcha 約 0.001 USD/張，幾秒解決。
  4. **放棄**：手動跑完整流程。

## 反爬 / 安全機制觀察

- ✅ 沒有 Cloudflare（cookie 沒 `cf_clearance`）
- ✅ 沒有 reCAPTCHA（自家 CAPTCHA）
- ✅ HTTPS + ASP.NET session（cookie）
- ⚠️ 兩道圖形 CAPTCHA
- ⚠️ `__VIEWSTATE` 巨大（34KB），每個 AJAX postback 都重傳
- ⚠️ `RandomStr` 在 URL query — 似乎是 session token，每次進 apply_1_3 不同

## 對現在 code 的影響

`src/hut_bot/routes/hike_aspnet.py` 與 `src/hut_bot/routes/catalog.py` 的欄位名 **幾乎全部要重寫**：

| 現況（猜的） | 真實 | 對 / 錯 |
|---|---|---|
| `ddlRoute` | `ctl00$con$climbline` | ❌ |
| `txtStartDate` | `ctl00$con$applystart` | ❌ |
| `txtNights` | `ctl00$con$sumday` | ❌ |
| `txtPeople` | `ctl00$con$teams_count` | ❌ |
| `txtLeaderName` | `ctl00$con$leader_name` | ❌ |
| `txtLeaderID` | `ctl00$con$leader_sid` | ❌ |
| `txtLeaderPhone` | `ctl00$con$leader_mobile` | ❌ |
| `txtLeaderBirthday` | `ctl00$con$leader_birthday` | ❌ |
| `txtMember{N}Name` | `ctl00$con$lisMem$ctrl{N}$member_name` | ❌ |
| `chkAgree` | `ctl00$con$applycheck` | ❌ |
| `submit_event_target=btnSubmit` | empty string（form submit）+ `btnsetp2upnext` & `btnsave` | ❌ |
| 1 個 submit URL | 2 個 step 連發 + 2 個 CAPTCHA | ❌ |

而且**現在 form_url 假設是單一 URL**，真實是「apply_1_2 → 302 → apply_1_3」chain，要重寫 fetch_form_state。

## 下一步該決定

1. 是否要實作 CAPTCHA OCR（影響搶票可行性）
2. 是否要支援 step 10（最終送出），這會真的訂位
3. 要不要把現在的 `HikeAspnetHandler` 完全 scrap 重寫成 2-step 流程
