# Owner review — 8361068 (2026-10-20)

**PASS，protocol v0.2.0 純文件單位結案。** 本 PASS 只驗收設計文件與來源歸檔，不是工具驗收、探索或 gate 結果，不構成矽上證據，也不重開 gate-1 的 valid FAIL。

審查 commit 8361068ce974ccfe3de4a88c01cd17be052696af，parent d19cc2faf5c42208ac020663ac81edf4bfafdf30；分支 b4-protocol-v2，工作樹乾淨；main/origin/main 仍 a243ee8。33 個 changed files 均在授權的 docs 與文件歸檔範圍，含原有只讀分析腳本的副本，沒有 production code 修改。

## 獨立核對

- docs/b4_architecture.md 全部新段落與七項裁定核對：T-i 的 FF-only target／單次抽取／base 不排除；H 的有限 API 契約與不能主張資訊隱藏；target digest、兩次 setup、觀測前持久化、逐次保存與 partial；target 與 map/population/champion/operator RNG 隔離；成本為待驗設計；R-base 非平凡性與兩種 holdout；K9 雙報告；S=32/B=64/p≤0.20 的工程政策；protocol identity；A2 的資料知情選法。無需重開範圍選擇。
- 歷史重驗文件將 code HEAD 與 archive commit 分開；registry 正確分為起跑前 snapshot 與加本次 batch 後的 archive tree；源碼、repo inputs、外部依賴與原 blob 核對分開，保留停止點與 authenticity limit。
- git diff d19cc2f..8361068：b4/、B3 歷史路徑、所有既有 B4 sim/gate archives、receipt、gate-1 execution plan、2c skeleton 零變更。git diff --check 通過。
- 四份來源目錄副本：5+4+8+6=23 個來源檔逐 byte 相等；另兩個 scope draft 副本逐 byte 相等；三份 SHA256SUMS 共12筆全部符合；設計 evidence README 的22個逐檔 digest 全部符合。
- 以 AST 讀取 PINS 常量並做靜態文字交叉核對，未 import production modules、未執行測試：36筆仍在對應 rows，零缺漏。首行現為 v0.2.0，因此 test_the_document_version_is_the_table_s 的舊 v0.1.16 斷言會不成立。這是已揭露、接受的 documents-only 過渡狀態；本審查不聲稱測試已執行或全套綠色。工具單位日後須實作並驗收新 identity/pin 契約，不能跳過該檢查掩蓋。
- gate-1 README 已正確分寫31.7分鐘（batch+judgement）及49.6分鐘（至兩次外部驗證結束）；owner review 歸檔與來源記載符合原件。兩個文件待辦結清。

## 按既有裁定解讀的文字精確化

以下不新增數字、研究選擇或方法；是上一裁定已固定的意思。併入下一筆適當提交即可，不需本單位 follow-up commit、重跑或新一輪審查。

1. §9 K9 (b′)／§9.3 clause6：對 ff_srval/sr_kind，明寫 `applicable_conditional = applicable_all_panel AND sr_mode_driven_at_both_endpoints`；舊 latch/x5FF 排除仍然有效。其他五語意的 conditional applicability 等於舊 applicability，不能讓新 flag 覆寫掉舊排除。
2. clause6 的「every pair of the fixed set is still observed」收斂為「每一對都有紀錄，維持舊 applicability 要求的觀測集合」。不是要求舊版不適用的對也新增兩次觀測。兩份 coverage 都由實際保留的、舊 applicability 適用的 grids 計算，不以模型填零代替觀測；不改 comparison set、分母定義或 query 契約。
3. 增一句版本優先關係：v0.2.0 的 §7.1、K9 (b′)、§9.4–9.5 在已改項目上取代舊描述；保留的舊 §7 要求（例如每 seed 的 base 一定非最優、generator 不讀 certificate）不可反過來禁止已批准的 T-i／base包含規則。保留歷史文字或 PINS 字串不代表同時有兩套現行方法；task-v0.1 的 stimulus 引用只保留已裁定不變的刺激規則。

## 邊界

現在不再要求額外結案 commit。下一個可能單位是 v0.2.0 工具實作與 mechanics-fixture 驗收，但此 PASS **不授權該單位**；也不授權任何 production preflight/seed derivation、探索、gate、push/merge、RTL、佈建、routing 或板上工作。現行程式與 thresholds 表仍是 v0.1.16；新版本只是已驗收的設計契約，尚未實作。
