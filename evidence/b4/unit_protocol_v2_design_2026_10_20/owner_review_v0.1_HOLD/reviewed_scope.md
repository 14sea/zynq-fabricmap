# B4-FF protocol revision：只讀範圍提案（2026-10-20）

**定位：只讀草案，等 owner 裁定。** 依 owner 2026-10-20 對 `d19cc2f` 的 PASS 與同日裁定（「下一單位定為 protocol revision 的只讀範圍提案，現在授權撰寫。先釐清 gate 未通過的原因，再決定後續投入；2c-obs 可列出哪些內容仍可獨立推進」）。本稿不是修訂、不是裁定、不是預註冊：不寫程式、不跑測試或模擬、不推導 seed、不建立新 gate 輸出、不 commit；不改 `docs/b4_architecture.md`、`b4/host/b4_thresholds.py`、任何 archive 或判決。檔案放 `build/wip/`（`.gitignore` 的 `build/` 擋住，只在本地）。起點 `b4-gate-1-execution@d19cc2f`（領先 main 2，未 push 未 merge；main = origin/main = `a243ee8`）。

**本稿引用的數字分兩類，逐處標明：**（i）**判決與報表原值** — `evidence/b4/gate/b4-gate-1_20261020T102526Z/gate_report.{json,md}`、`evidence/b4/sim/b4-gate-1_20261020T102526Z/sim_report.json`、owner 的 `independent_checks.json`；（ii）**只讀彙總值** — 由 200 個 pair 目錄已歸檔的 `curves.json`、`k9.json`、`k7.json`、`arm_O.result.json` 的記錄欄位加總或取中位數而得（附錄 A 列方法；讀取腳本放在 session scratchpad，不在 repo、不 commit；過程不呼叫 model、engine、landscape、seeds 任何一段 production 程式碼，不產生新觀測）。第二類數字是**事後描述**，它們驅動了本稿的候選選擇，§8 逐項揭露；它們不能驗證任何新版本。

---

## 0. 結論先行（owner 讀這一節就能裁定方向）

1. **本次 valid FAIL 保留為 protocol v0.1.16 的結果**（§1）。它由兩個互相獨立的失敗構成：**K9 的 `ff_srval` 覆蓋不足**（可觀測性度量的 applicability 定義問題）與 **budget rule 無 N → K5 不可評**（task estimand 問題）。修其中一個不會讓另一個通過。
2. **Budget rule 失敗的原因不在 cartographer，在 task-v0.1 的 landscape**：gate-1 的 200 場裡，**連特權的 oracle 分組 Ω 都在每個 budget 平均輸給 random-safe R**（只讀彙總：Ω − R 平均 −1.010 … −0.395，十個 budget 全負）；七臂在 B = 256 的中位數全部是 41／64，任一臂任一 seed 最高 51，沒有 seed 到 56；holdout 七臂平均都在 40／80 = 機率水準。task-v0.1 的 target 是逐 cell 隨機位元，**沒有可達性保證**（生成器 docstring 自述；B2 的 D2 規則有、B4 §7 把它改成「留待另一個 host audit」而該 audit 從未做）。在一個最佳解不可達、無結構可供 map 利用的 landscape 上，任何 map（含正確的）都不會贏；負的樣本效應是「此 task 下 map 無益」的證據，**不是**「FF class 不可 map」或「效應不存在」的證據（§2.1、§1.3）。
3. **K9 `ff_srval` 失敗的原因是比較集把「SR tied low」的背景算進分母**：這些背景下 SRVAL 在模型定義上不可能影響 trace（`sr_tied_low_when_not_driven`），覆蓋恆 0，給出 owner 2026-10-19 審核發現的結構上界 0.5；其餘差距來自 synchronous SR 只在三個 rising edge 生效（只讀彙總：driven + sync + FF 背景覆蓋 0.5750，解析預期 1 − (3/4)³ = 0.578）。**`sr_kind` 的 PASS 來自同一個結構上界，103／200 個 seed 恰好 0.5，險過**（§2.2）。
4. **建議的修訂包（§3.6）**：**R-T**（task-v0.2：planted-reachable target，B2 D2 的規則移植到 trace 空間）＋ **R-K9-A**（applicability：SR tied low 的背景對 `ff_srval`／`sr_kind` 為 not applicable，與既有的 latch 規則同類）＋ **K1 補可達性條件**，以 architecture **v0.2.0**、thresholds 表新 digest、新 label（`b4-sim-4`、`b4-gate-2`）獨立推進；**R0（不修訂、以 FAIL 結案 B4-FF）是對等的選項**，owner 可選。拒絕的候選：改門檻數字、改統計、擴大 S、換 operator（§3）。
5. **舊 archive 不改、不重判**：`b4-sim-3`、`b4-gate-1` 永遠以 v0.1.16 身分存在；重驗走「記錄 HEAD 的 worktree 跑該版 verifier」（計畫 §6 的方案 A）；版號耦合用「版號移出 THRESHOLDS 表＋ verifier 對不同表 digest 具名拒絕並指向方案 A」解（§4）。
6. **新版本在任何探索前固定**：修訂文件 → 工具實作（mechanics fixture 驗收）→ 凍結 → `b4-sim-4`（S = 32）→ 探索後門檻不得再動 → `b4-gate-2`（S = 200）；每一步有停止條件（§5）。
7. **2c-obs 可以現在推進的內容**（§6）：A2 的 positive-control 位址清單、A3 raw-observation schema、A8 初始化觀測設計、universe／holdout 選擇、A5／A6／A7 的形式——都不依賴 gate 判決或本修訂。

---

## 1. 本次 valid FAIL 的保留與分類

### 1.1 保留什麼（不改寫）

- 判決：`b4-gate-1` verdict **FAIL**, `formal = true`，v0.1.16 的 §9 門檻；archive 與 gate 目錄在 `5070967`，執行紀錄在 `d19cc2f`；owner 覆核 PASS（`build/wip/owner_review_d19cc2f_2026_10_20/`，待歸檔）。
- label `b4-gate-1` 已消耗；其 401 個值已入 registry 與 pooled exclusion（現 2 625）。
- 它的範圍：此模型（hypothesis v0.3）、此 public task（task-v0.1）／panel（k9-panel-v1）、此 operator／control 設計、此 budget grid、此判定程序。不外推矽、carrier、整個 FF class。

### 1.2 兩個失敗，分開記

| 失敗 | 判決原文 | 性質 | 修了會怎樣 |
|---|---|---|---|
| **budget rule FAIL** → K1–K7 not assessable | 十個 budget 都 K1 eligible，N 全為 null（K5 scan 在 N = S 的 bootstrap power 0.0） | **estimand／task 設計問題**：Δ1 = O − R 在每個 budget 平均為負（報表原值 −0.485 … −0.94，d −0.23 … −0.39，單尾 sign test p ≥ 0.9999） | 需要 task 改版；K9 怎麼修都不影響 |
| **K9 FAIL** | (b) `ff_srval` 中位數覆蓋 0.40625 < 0.50；(a) 200／200 seed 七語意正控制全備 | **可觀測性度量的 applicability 定義問題**：分母含模型定義上不可能有差異的背景 | 需要 §9.3 條 4 改版；budget rule 不受影響 |

### 1.3 不把負的樣本效應讀成效應不存在

- K5 的檢定是單尾、H1 = P(Δ1 > 0 | Δ1 ≠ 0) > ½，為「map 有益」設計；它對「map 有害」沒有預註冊的檢定。gate-1 的 Δ1 在每個 budget 負多於正（例如 B = 48：103 負／39 正／58 平），**若事後做反向單尾檢定會顯著，但未預註冊，只作描述**。
- 所以能說的是：**在 task-v0.1 下、S = 200、B ≤ 256，online map 不優於 random-safe，且有害的方向一致。** 不能說的是：FF class 不可 map；不存在任何 task 使 map 有益；cartographer 學不到東西（K7 的學習曲線在 B = 128 時 198／200 seed 已 ≥ 11 個位址 not unknown，見 §2.1.4）。
- 更強的一句（只讀彙總支持）：**連 Ω 也輸給 R**。這把原因從「O 的 map 不夠好」移到「此 landscape 沒有 map 能利用的結構」。

---

## 2. 失敗原因的釐清（只讀歸檔值；每個數字標來源）

### 2.1 Budget rule／K5

#### 2.1.1 資料事實

| 事實 | 值 | 來源 |
|---|---|---|
| Δ1 = O − R 平均、d、sign p（十個 budget） | mean −0.485 … −0.940；d −0.231 … −0.386；p ≥ 0.9999 | 報表原值 `diagnostics.per_budget` |
| F − R 平均 | −0.945 … −0.535（十個全負） | 報表原值／只讀彙總一致 |
| X − R 平均 | −0.760 … −0.360（十個全負） | 報表原值 |
| **Ω − R 平均（正／負／平）** | B8 −1.010 (33/81/86)、B32 −0.770 (52/90/58)、B64 −0.490 (56/95/49)、B128 −0.525 (50/73/77)、**B256 −0.395 (38/53/109)**；十個全負 | **只讀彙總** `curves.json.best_at_grid` |
| D − R、A0 − R 平均 | D −0.550 … −0.220；A0 −0.765 … −0.135；全負 | 只讀彙總 |
| 七臂 best 中位數 | R：34, 35, 36, 37, 38, 39, 40, 40, 41, 41（B = 8 … 256）；**B = 256 時七臂全部 41** | 只讀彙總（R 的 B* 列與報表 `arm_medians` 一致） |
| base 分數 | 中位數 32（= 64 cells 的一半），平均 31.57，範圍 21 … 43 | 只讀彙總 `base_fit` |
| 任一臂在 B = 256 的最高分（逐 seed 取七臂最大） | 中位數 42、平均 42.5、**最高 51**；≥ 48 的 seed 7／200、≥ 56 的 0／200、≥ 64 的 0／200 | 只讀彙總 |
| R 相對 base 的增益（B = 256） | 平均 +9.99；Ω +9.60 | 只讀彙總 |
| holdout（K = 8，ceiling 80）七臂平均 | 39.8 … 40.5，**全部 ≈ 40／80 = 50 %**；O − R：69 正／72 負／59 平 | 只讀彙總 `curves.json.holdout`（§9 無門檻） |
| K7：O 的 map 在各 budget 的 not-unknown 位址數 | 中位數 2, 3, 4.5, 6, 8, 10, 14, 17, 19, 21；≥ 11 的 seed 數 B48 37、B64 87、**B96 173**、B128 198、B192 200 | 報表原值（中位數）＋只讀彙總 `k7.json`（計數） |
| O 的 group move 次數（256 次評估中） | 中位數 123.5（≈ 48 %；operator 規則是 view 有 group 時一半機率走 group move） | 只讀彙總 `arm_O.result.json.group_moves` |

#### 2.1.2 機制歸因（依證據強度排序）

**(a) task-v0.1 的 target 不保證可達，landscape 近似「隨機目標比對」。** 生成器自述：「Reachability of the ceiling, the base not being optimal, and interaction are NOT guaranteed by this generator: they are claims for a separate host audit」（`b4_landscape.py` docstring；architecture §7 同義）。該 audit 在 2b-1 … 2b-4a、sim-3、gate-1 之間沒有任何單位執行過。對照 **B2 的 D2 規則**（`docs/b2_architecture.md` §3）：target 由 seed 的 xorshift 流產生後**遮罩到 universe**，「The optimum is therefore reachable and unique」——這是 B2 的 F1／F2 landscape 上 F 能贏 R 的前提之一。B4 §7 把它降級成要求，沒有落實在生成器裡。資料與此一致：2²¹ 個配置對 64 個隨機 target 位元，觀察到的上限 51／64，中位數 42，base 32 = 純猜測的期望值；七臂在 B = 256 完全收斂到同一個中位數 41。**這不是「K1 非飽和」要抓的問題——K1 的 p95(best_Ω) < 64 在此 task 下恆成立，沒有鑑別力。**

**(b) 在這樣的 landscape 上，group move 沒有優勢。** engine 是 B2 的 derived copy，operator 與 B2 相同（random-safe：任意 1 … 4 位；group move：同一 group 內 1 … 4 位；map 臂各半）。Ω 的 group 是每個元件的 (INIT, SRVAL) 對加上五個 mode 位元一組；A0 是 frame 分組。當 target 對每個 cell 獨立隨機時，同 group 內的位元沒有協同利益可言，group move 只是把 random-safe 的搜尋範圍縮小——與觀察到的「所有 map 臂都略輸 R、彼此差不多、A0 輸最少」一致。這點**不證明** operator 本身有缺陷：同一 operator 在 B2／B3 的 LUT task 上贏過 R（B3 pooled primary 8／0／0）。

**(c) 動態範圍小。** base 32 → best ≈ 41，各臂差的 population variance ≈ 4 … 7（報表原值），一兩個 cell 的差距就決定正負；sign test 的 ties 多（每 budget 55 … 149 個）。這放大 (a)(b) 的效應，不是獨立原因。

**(d) O 的 map 學得慢，但這是次要原因。** 中位數在 B = 96 才過 11；但 Ω 一開始就有完整分組仍然輸，所以學習速度不是決定因素。

**(e) holdout 在機率水準** 與 (a) 一致：holdout 刺激（K = 8）的 target 是另一組隨機位元，champion 對它沒有可轉移的東西。B2 已經明說 holdout 對 lookup-table 表型是「neutrality／known-answer control，不是 generalisation measure」；B4 的 task 若改成 planted target，holdout 才會有 generalisation 的意義（§3.3）。

#### 2.1.3 什麼不能從這裡說

不能說 FF class 的位元在矽上不可觀測、不可 map；不能說 cartographer 的 relation 不正確（K7 (a) 零 mismatch、K8 replay 乾淨）；不能說 S 更大或 N 更大會翻轉（Δ1 的方向在 S = 32 與 S = 200 一致為負）；也不能說 task-v0.2 一定讓 Ω − R 轉正——那是 `b4-sim-4` 要先看的，而且探索結果不能回頭改門檻。

### 2.2 K9 `ff_srval`

#### 2.2.1 資料事實（只讀彙總 `k9.json`，200 seed × 1 184 對；背景的 SR 模式、SR 類型、storage 類型由記錄中的端點 genome 與記錄自己標的語意位元位置解碼：`sr_mode` 位元 3、`sr_kind` 位元 0、`storage_kind` 位元 10；decode 依 hypothesis v0.3：bit 1 = driven／synchronous／latch）

| 語意 | 背景 | applicable 對 | covered | 覆蓋率 |
|---|---|---|---|---|
| ff_srval | **SR tied low**（async／sync × FF／latch 四類） | 38 400 | **0** | **0.0000** |
| ff_srval | SR driven, async, FF | 12 800 | 11 480 | 0.8969 |
| ff_srval | SR driven, async, latch（AFF … DFF） | 6 400 | 5 688 | 0.8888 |
| ff_srval | **SR driven, sync, FF** | 12 800 | 7 360 | **0.5750** |
| ff_srval | SR driven, sync, latch（latch 的 SR 永遠 async） | 6 400 | 5 688 | 0.8888 |
| sr_kind | SR tied low | 1 600 | 0 | 0.0000 |
| sr_kind | SR driven | 1 600 | 1 460 | 0.9125 |
| sr_mode | FF, sync 背景 | 1 600 | 1 462 | 0.9137（tied_low→driven 的差要有一次 rising-edge SR 且結果異於 capture 值） |
| sr_mode | FF, async 背景 | 1 600 | 1 586 | 0.9912 |
| sr_mode | latch 背景（SR 恆 async，不分 sr_kind） | 3 200 | 3 122 | 0.9756 |

逐 seed（報表原值與只讀彙總一致）：`ff_srval` 中位數 0.40625、平均 0.393、範圍 0.208 … 0.490，**0／200 ≥ 0.5**；`sr_kind` 中位數 0.5、平均 0.456、**103／200 恰好 0.5**（其餘 97 個在 0.25 … < 0.5；最大值 0.5 由上界決定）；`sr_mode` 中位數 0.96875。

**若只算 SR-driven 背景**（只讀彙總，事後）：`ff_srval` 逐 seed 中位數 **0.8125**（平均 0.787，範圍 0.417 … 0.979，198／200 ≥ 0.5）；`sr_kind` 中位數 **1.0**（200／200 ≥ 0.5）。

#### 2.2.2 機制歸因

1. **結構上界 0.5（owner 2026-10-19 審核已指出，gate-1 資料證實是恆等式而非趨勢）**：panel 的 32 種 mode 組合有一半 `sr_mode = tied_low`；模型 `sr_tied_low_when_not_driven = true`，SR 永不斷言，SRVAL 在定義上對 trace 無影響；§9.3 條 4 的 applicability 只排除 latch 下的 x5FF 與 latch 下的 `sr_kind`，沒有排除「SR tied low 下的 `ff_srval`／`sr_kind`」。這和 applicability 的既有原則（「APPLICABILITY IS A PROPERTY OF THE CONFIGURATION, read from the host decode of the two endpoints」，`b4_k9.py`）不一致：一個在配置上就不可能觀測的對，被當成「可觀測但沒看到」計入分母。
2. **synchronous SR 只在 rising edge 生效**：task-v0.1 的刺激是 init ＋ 6 個 clock 步（clock 交替，rising edge 在第 1、3、5 步）＋ 2 個 level 步；每步每元件 SR 斷言機率 1/4。async：元件八步內至少一次 SR 的機率 1 − (3/4)⁸ = 0.900（觀察 0.897）；sync：只有三個 rising edge 算數，1 − (3/4)³ = 0.578（觀察 0.575）。這是 task 刺激與模型 `sync_sr_acts_on_edge_only` 的交互，不是缺陷，但 K9 若要度量「語意可觀測性」而非「此刺激恰好觸發的頻率」，就是估計量混淆。
3. **`sr_kind` 的 PASS 與 `ff_srval` 的 FAIL 同源**：上界一樣是 0.5；`sr_kind` 在 driven 背景的覆蓋 0.9125 高到讓 103 個 seed 恰好頂到 0.5，中位數「≥ 0.50（等號允許）」險過。換一組 seed 可能就不過。這不是本版本的錯（規則寫在前面、照規則判），但它顯示 (b) 準則在這兩個語意上量的是上界附近的抖動，不是可觀測性。

#### 2.2.3 什麼不能從這裡說

不能說 SRVAL 在矽上不可觀測；不能說 0.8125 是「真實」覆蓋（它是同一批資料在另一個分母定義下的事後重算，只用來說明候選修訂的方向，不是它的驗證）；不能用它判 K9 PASS。

### 2.3 兩個失敗的關係

獨立。K9 量的是 task 刺激下七個語意在 panel 上能否被分辨（host 診斷，不進 search）；budget rule 量的是 search 臂的差。修 K9 的 applicability 不改任何 arm 的分數；修 task 會同時改 K9 的刺激（新 task 的刺激若保留 `_sparse` 規則，sync SR 的 0.575 不變）。**要 PASS 必須兩個都修；只修一個，gate-2 必 FAIL。**

---

## 3. 候選修訂（每條：改什麼、理由、代價、資料影響、事前可預測性）

編號：R0 不修訂；R-K9-* 針對 K9；R-T 針對 task；R-S／R-O／R-N 是被拒絕的方向，列出來是為了記錄為什麼不選。

### 3.0 R0 — 不修訂，以 valid FAIL 結案 B4-FF 的 gate 線

- **改什麼**：什麼都不改。B4-FF 在 v0.1.16 下的結論是「此 task／panel／設計下，map 無益且 ff_srval 不可觀測」；線停在 gate，像 round 1′（`docs/claimb_round1prime_package.md` §9）。
- **理由**：§9 自己寫「if it does not, B4-FF stops at the gate like round 1′ did, and that is a result」。
- **代價**：B4 §0 的問題（map 能否處理「意義不是 truth table」的位元類）沒有得到答案——得到的是「task-v0.1 不是能問這個問題的 task」。2c-rest、carrier v2、B4-R 的 FF 前置全部失去上游。
- **資料影響**：無。
- **可預測性**：不適用。

### 3.1 R-K9-A — applicability：SR tied low 的背景對 `ff_srval`、`sr_kind` 為 not applicable（**建議**）

- **改什麼**：architecture §9.3 條 4 增一句：「Under `sr_mode = tied_low` the elements' `ff_srval` and the slice's `sr_kind` are not applicable (SR is never asserted; SRVAL and the SR kind cannot reach the trace under the model's `sr_tied_low_when_not_driven`): those pairs are named and removed from their denominators, exactly as the latch rule removes the x5FF elements' INIT / SRVAL and `sr_kind`.」`b4_k9.py` 的 applicability 判定同步；手算的 applicable 對數由 `ff_srval` 384、`sr_kind` 16 變 192、8；panel 不變（64 背景、1 184 對）；其他五個語意不變。
- **理由**：與既有 applicability 原則一致（配置屬性，不看 trace）；latch 規則已是先例；移除的是「定義上不可能」而非「沒看到」的對。
- **代價**：§9.3 的新版本＋完整重報（§9.3 末段的規則）；`b4_k9.py`、其測試、IMPORT、thresholds 表 `K9.panel` 字串（表 digest 變）；gate-1 的 K9 紀錄不重算（它以 v0.1.16 身分存在）。
- **資料影響（揭露）**：這條完全由 sim-3（owner 的 0.5 上界審核）與 gate-1（tied-low 覆蓋恆 0、driven-only 中位數 0.8125）驅動。事後重算顯示在 gate-1 的 seed 上它會讓 `ff_srval` 中位數 0.8125、`sr_kind` 1.0；**這個數字不是 v0.2.0 的驗證**，gate-2 用新 seed 重量。
- **可預測性**：在探索前可以寫下預測「`ff_srval` 中位數 ≥ 0.5」並說明依據是解析（driven+async ≈ 0.90、driven+sync ≈ 0.58 的加權），不是 gate-1 的重算。

### 3.2 R-K9-B — 把 panel 縮成只有 SR-driven 的背景（32 個）

- **改什麼**：§9.3 條 2 的 panel 去掉 `sr_mode = tied_low` 的 16 種 mode 組合。
- **理由**：效果對 `ff_srval`／`sr_kind` 等於 R-K9-A。
- **代價**：改了**所有七個語意**的分母（`sr_mode` 自己的對會剩一半方向、`ce_mode`／`clock_mode`／`storage_kind` 失去 tied-low 背景下的觀測），把一個 applicability 問題變成 panel 設計問題。
- **不建議**：R-K9-A 達成同一目的且改動最小。

### 3.3 R-K9-C — K9 專用刺激（每元件在 rising edge 至少一次 SR）

- **改什麼**：§9.3 條 1「The stimulus is the task's own」改為 K9 用一個固定的、與 task 無關的診斷刺激。
- **理由**：消除 sync SR 的 0.578 效應，K9 變成純可觀測性度量。
- **代價**：K9 與 search 的刺激脫鉤後，K9 不再說「search 看得到這個語意」而只說「有刺激能看到」；A2（carrier 的 positive control）的對應關係要改；§9.3 條 1 的理由（「K9 measures observational distinguishability, not coverage of the fitness mask」）本來就偏向這個方向，但 owner 2026-10-18 裁定用 task 自己的刺激。
- **資料影響**：由 gate-1 的 sync／async 分層驅動。
- **不建議單獨做**；若 R-T 的 task-v0.2 改了刺激規則（§3.5 的開放點 3），一併在那裡決定。

### 3.4 R-K9-D — 把 (b) 門檻從 0.50 降到 0.40（**拒絕**）

- 只為讓 0.40625 過；沒有估計量理由；違反 owner 2026-10-19 §1「Do not revise the panel or lower a threshold to make the exploratory result pass」。列出來是為了明寫拒絕。

### 3.5 R-T — task-v0.2：planted-reachable target（**建議**；本修訂的主體）

- **改什麼**（規則層，數字留給修訂單位）：
  1. target 不再是逐 cell 隨機位元，而是**一個由 landscape seed 用公開規則抽出的 planted 配置 g\* 在同一 execution port 下、同一 search 刺激下觀測到的 trace**（`q_after` 逐 cell），mask M 與 weights 同 v0.1；holdout 的 target 是 g\* 在 holdout 刺激下的 trace。
  2. g\* 的抽法：21 位元均勻（`Rng(landscape_seed ^ salt_T).uniform(1 << 21)`，自己的 salt、自己的 generator，與 task 刺激、operator、control、K10 背景的 generator 都分開），**排除 base（全零）**，若抽到 base 則記錄並取下一個值（記錄，不重抽 seed）。
  3. 生成器**仍不 import mapping、hypothesis、decode**：它只產生 g\* 與刺激；target trace 是 engine 在 base 觀測之後、search 之前，經同一個 `observe` boundary 做的一次額外觀測（phase `target`），入 ledger、入 replay、算 1 次觀測成本（R／O 完整 run 變 B + 3，F 變 B + 24）。這保留 §7「landscape generation rule must not consult the certificate, the map or the operator」，但**新增一個明寫的依賴：task 的 target 依賴 formal model（在模擬）或板（在 2c）對 g\* 的觀測**。
  4. 結果：ceiling 64 **可達**（g\* 本身）；最佳解**不一定唯一**（不同配置可產生同一 trace；這與 B2 的 LUT 情形不同，要寫明）；base 不是最佳（g\* ≠ base，且刺激下 base 與 g\* 的 trace 至少一 cell 不同——這不保證，要在探索報表列「base 分數分布」）；interaction 由 K10 重量。
- **理由**：這是 B2 D2「fitness over the reachable space」規則在 trace 空間的對應；B2／B3 的 F > R 都是在這種 landscape 上得到的；§2.1.2(a) 的證據指向可達性是 v0.1 landscape 缺的東西。它同時讓 holdout 有 generalisation 的意義（champion 對 g\* 的 holdout trace）。
- **代價**：
  - 文件：architecture §7（task-v0.2 規則、新依賴的明寫、ceiling 可達但不唯一）、§9 K1（見 3.7）、§5.1／§5.3 若 2c 要在板上觀測 g\*（一個 seed 一次額外觀測，known-answer 性質；2c-obs 的 A2／A3 不受影響）。
  - 程式：`b4_landscape.py` task-v0.2（新 TASK_VERSION、g\* 規則、score 不變）、`b4_engine.py` 的 target 觀測 phase 與 ledger／replay 契約、`b4_sim.py`／`b4_sim_schema.py`／`b4_sim_verify.py` 的 task 版本綁定與完整 run 的呼叫數（`B + 3`／`B + 24`）、K7 prefix 的「O 的前 B\* + 1 筆」定義要改成「排除 target 觀測後的前 B\* + 1 筆」、tests、mutants、IMPORT。規模與 2b-4a 的一個 commit 相當，預期有 HOLD 輪。
  - 統計：所有臂的分數分布改變；K5 的 d ≥ 0.5 在新 landscape 下是否合理**不知道**（不能用 gate-1 推）；cap 4 000 不變。
  - 探索：`b4-sim-4`（S = 32，約 5 分鐘 batch、190 MB）；gate：`b4-gate-2`（S = 200，約 50 分鐘、1.2 GB、`.git` 再 +0.5 … 1 GB）。
- **資料影響（揭露）**：這條由 gate-1 的「Ω − R 全負、上限 51、holdout 機率水準」與 B2 D2 的對照驅動。**gate-1 的資料不能預測 task-v0.2 下 Ω − R 或 Δ1 的符號**；R-T 能否讓 map 有益是 `b4-sim-4` 要回答的經驗問題，答案是否定時 §5.3 的停止條件生效。
- **可預測性**：探索前可寫下的預測：「Ω − R 的中位數 > 0」（map 有結構可用的必要條件，不是 gate 準則）與「K1 (a) 不再恆成立」。
- **開放點**（修訂單位要決定、不在本稿）：(1) g\* 要不要排除 latch 配置或任何 DOMAIN 外配置（v0.3 下全部在 domain 內，所以目前不需要）；(2) target 觀測的 ledger phase 與 replay；(3) 刺激規則是否保留 `_sparse`（SR 1/4）與 K = 6——若保留，K9 的 sync SR 0.578 不變，R-K9-A 之後 `ff_srval` 預期 ≈ 0.74 … 0.8，仍 ≥ 0.5；(4) 在板上（2c）g\* 的 trace 是觀測一次後固定、還是每個 session 重觀測——known-answer 的穩定性是 A5 的一部分。

### 3.6 建議的修訂包與替代

| 包 | 內容 | 版本 | 適用 |
|---|---|---|---|
| **P1（建議）** | R-T ＋ R-K9-A ＋ K1 補可達性條件（3.7） | architecture **v0.2.0**（數字與方法都變）；thresholds 表新 digest；`b4-sim-4`、`b4-gate-2` | owner 認為 B4 §0 的問題值得再問一次 |
| **P0** | R0 | 無 | owner 認為 v0.1.16 的 FAIL 已回答這條線能回答的問題 |
| 不建議 | 只做 R-K9-A（gate-2 必因 budget rule FAIL）；只做 R-T（gate-2 必因 K9 FAIL，除非 task-v0.2 的刺激恰好拉高 sync SR 覆蓋——不該賭） | — | — |

### 3.7 K1 的補充（隨 R-T）

v0.1.16 的 K1 (a) `p95(best_Ω(B*)) < 64` 在 v0.1 的 landscape 下恆成立（§2.1.2(a)）。task-v0.2 下 ceiling 可達，K1 (a) 才有「不飽和」的意義。建議同時補一個**可達性記錄**（無門檻或 owner 定門檻）：每 seed 記 g\* 的分數 = 64（由構造）與 base 的分數；若 owner 要門檻，形式是「median_r(base_r) ≤ 0.9 × 64」之類的非平凡性條件。不建議把 K1 變成「某臂必須到 64」——那是 search 能力的問題，不是 landscape 的。

### 3.8 被拒絕的方向（記錄理由）

- **R-S 改統計**：改 d 門檻、power、α、S、N 上限——Δ1 的方向是負的，沒有任何統計參數能在不改 estimand 的情況下讓它過；「擴大 S」被 owner 2026-10-19 §2 明文排除。
- **R-O 換 operator**：engine 是 B2 的 derived copy，同一 operator 在 LUT task 上贏過；在 task-v0.1 上所有 map 臂（含 Ω）都略輸 R，是 landscape 無結構的表現，不是 operator 的；要在 task-v0.2 的探索之後、若 Ω − R > 0 但 O − R ≤ 0，才輪到 operator／cartographer 的問題。
- **R-N 只換 label 重跑同一版本**：owner 2026-10-19 §1「label consumption alone is not a reason to change the method」的反面也成立：同一方法重跑只是重抽，valid FAIL 不是抽樣意外（S = 32 與 S = 200 方向一致）。

---

## 4. 舊 archive 的重驗，與架構版號／thresholds 表耦合的解法

### 4.1 不變量（owner 2026-10-20 計畫 §6 的裁定，照抄）

舊 archive 永遠在它產生時的表下被判；表的變更是具名修訂＋理由＋新 commit＋重跑重報，從不悄悄；不改寫舊證據、不重判舊判決、不寫相容性遷移。

### 4.2 舊 archive 的重驗方式（方案 A，文件化）

- `b4-sim-3`（HEAD `933545a`，工具 bytes = `00336d0` 基線之前的版本）與 `b4-gate-1`（HEAD `a243ee8`，工具 bytes = `00336d0` 基線）：重驗 = `git worktree add <dir> <記錄的 HEAD>`，在該 worktree 跑該版的 `b4_sim_verify.py`／`b4_gate_verify.py`，三行標頭（HEAD、命令、UTC）存檔。
- 修訂單位要交付：(a) `docs/` 的一頁重驗程序；(b) 一個測試：對每個已歸檔 manifest，記錄的 HEAD 的 tree 重現記錄的 `tool_files` digests（`git cat-file` 讀，不 checkout 整棵樹也可）——這把「記錄的 HEAD 是可信的重驗基線」變成機器檢查。
- 現行 verifier 對舊 archive 的行為：見 4.3，具名拒絕並指向這個程序；**不是**跳過、不是用新表重判。

### 4.3 耦合的解法（方案 C ＋ 方案 A 的拒絕路徑；方案 B 留作後續）

現況：`THRESHOLDS["source"]` 含 "section 9 (v0.1.16)"，整張表入 manifest／report，verifier 以 canonical JSON 比對整張表（`b4_sim_verify.py:230`）；文件版號一動，舊 archive 就不再通過現行 verifier。

建議：
1. **版號移出表**：`THRESHOLDS["source"]` 改成不含版號的固定句；版號由 manifest 新欄位 `protocol` = `{architecture_revision, thresholds_sha256, task_version, k9_panel_version, hypothesis_sha256}` 記錄（manifest schema 1.2.0，舊 archive 讀舊 schema，不改寫）。數字一改表 digest 就變；純文字修訂不變。
2. **verifier 的具名拒絕**：讀到的 manifest 其 `thresholds` 的 digest ≠ 現行模組表的 digest → finding `thresholds_version_mismatch: archived <d1>, current <d2>; re-verify at the recorded HEAD <h> (docs/<程序>)`，exit 非 0；**不**重判、**不**比對逐欄。這對 `b4-sim-3`／`b4-gate-1` 的 archive 在 v0.2.0 的 verifier 下就是預期行為，寫進該單位的 README。
3. **judgement 的版本選擇（方案 B）不在本修訂做**：它要改 `summarise_batch`、K 列判定、report validator 的每一段讀表的地方，成本高且目前只有一個舊版本；留作 v0.2.0 之後若再有版本時的獨立設計單位。
4. **pin test**（`b4/tests/test_b4_thresholds.py`）：PINS 的 `K9.panel` 與新增的 applicability 句、K1 的補充句同步；版號不再是 pin 的一部分。

### 4.4 label 與 seed 的版本關係

gate master = sha256(`label|HYPOTHESIS_SHA256`)[:4]：hypothesis 不變、label 不變 → 同一組 seed。task 改版不在 anchor 裡，所以**新版本必須用新 label**（`b4-sim-4`、`b4-gate-2`），`anchor.gate_label`／`exploration_label` 隨表改（表 digest 本來就變）；`b4-gate-1`、`b4-sim-3` 進 `RETIRED_LABELS` 或等價的「已消耗」清單，harness 拒絕再推導。exclusion 自動含 gate-1 的 401 值（pooled 2 625），不需人工動作。是否把 `task_version` 併入 anchor 字串，owner 決定；本稿建議**不**併（anchor 綁模型，label 綁一次執行，task 版本在 manifest），理由是 anchor 公式的穩定性本身是審計資產。

---

## 5. 新版本如何在探索前固定方法、門檻與 seed 政策；停止條件

### 5.1 順序（每一步一個單位、一次 owner 裁定；任何一步 HOLD 不進下一步）

| # | 單位 | 交付 | 凍結點 |
|---|---|---|---|
| 1 | **修訂文件**（documents only） | architecture v0.2.0：§7 task-v0.2 規則、§9 K1 補充、§9.3 條 4 的 applicability 句、§9.2 新 label 與退役清單、§6（版號／表耦合）新節；`docs/b4_gate_execution_plan.md` 不動（它是 gate-1 的）；本稿的 §8 揭露表併入 architecture 的修訂註記 | owner PASS 後，§9 的數字與方法對 v0.2.0 固定 |
| 2 | **工具單位** | `b4_landscape` task-v0.2、engine 的 target 觀測、K9 applicability、thresholds 表（新 digest、無版號）、manifest `protocol` 欄位、verifier 的 mismatch 拒絕、重驗程序與 HEAD→digest 測試、`RETIRED_LABELS`、tests／mutants／IMPORT、e2e 用 `b4-mech-*` fixture；**不推導任何 production seed、不碰舊 archive** | owner 工程 PASS = 工具基線（v0.2.0 的 `00336d0` 對應物） |
| 3 | **探索 `b4-sim-4`**（S = 32） | 一次 batch；報表列值、無判決；README 照 sim-3 的格式（完整 per-budget／per-semantic 列印，不從截斷輸出推廣——sim-3 §3 的教訓） | 探索後 **§9 的任何數字、panel、applicability、task 規則都不得再動**；若要動 = v0.3.0，再一輪 1–3 |
| 4 | **執行計畫 `b4-gate-2`**（documents only） | 照 v0.2.1 計畫的格式，更新成本（run 多 1 次觀測）、HEAD、基線 | owner PASS |
| 5 | **production `b4-gate-2`**（S = 200） | 一次執行；結果照 §3 分流 | — |

### 5.2 事前固定的清單（在 #3 之前全部定案、全部有 digest）

方法：task-v0.2 規則與 salt、target 觀測 phase、K9 applicability、七臂與 operator（不變）、K10（不變）、統計複本（不變）。門檻：K1（含補充）、K2–K10 的數字（**建議全部沿用 v0.1.16，只有 K1 的補充是新的**；理由：沒有 v0.2 的資料可以用來調，而用 v0.1 的資料調就是本稿要避免的事）。seed 政策：anchor 公式不變；label `b4-sim-4`／`b4-gate-2`；exclusion = 38 來源＋receipt＋registry（含 sim-3、gate-1）＋B4 exposed；freezing order 不變（seeds.json → manifest → 第一次觀測）；gate seed 只在 #5 的 batch init 推導一次。

### 5.3 停止條件（每條寫在 #1 的文件裡，不是事後加的）

| 時點 | 條件 | 動作 |
|---|---|---|
| #3 探索後 | Ω − R 的逐 seed 中位數 ≤ 0（map 的結構在 task-v0.2 下仍無益） | **停**，不進 #4；B4-FF 在 v0.2.0 以「task 改版後 oracle 仍無益」結案，不再提 v0.3 除非 owner 另有估計量論證 |
| #3 探索後 | 新 applicability 下 `ff_srval` 或 `sr_kind` 中位數 < 0.5 | **停**；回到 §3.3 的刺激問題，另立單位 |
| #3 探索後 | base 分數中位數 ≥ 0.9 × 64（task 平凡） | **停** |
| #5 | valid FAIL | 本線在 v0.2.0 結案；**不提 v0.3**（兩版皆 FAIL 之後，再修訂就是對資料擬合） |
| #5 | invalid／incomplete／init_failed | 照 gate-1 計畫 §3 分流；label 消耗；owner 裁 |
| 任何時點 | 要改 #2 之後的數字、panel、規則 | 版本號升、回到 #1 |

### 5.4 預註冊的預測（#1 寫下、#3 檢查；它們不是 gate 準則）

- task-v0.2 下 Ω − R 中位數 > 0（map 的結構有用的必要條件）。
- R-K9-A 下 `ff_srval` 逐 seed 中位數 ≥ 0.5，依據是解析（§2.2.2 第 2 點的加權），不是 gate-1 重算。
- K1 (a) 不再恆成立（有 seed 的 best_Ω 到 64）。

---

## 6. 2c-obs 可以獨立推進的內容（不依賴 gate 判決或本修訂）

依計畫 §7 的依賴圖，`2c-obs` 不依賴 G。對照 2c 骨架 v0.0.2 §0 表：

| 骨架欄位 | 現在能填的 | 依賴 | 注意 |
|---|---|---|---|
| §6 A2 positive-control 位址 | 七個語意各至少一個可分辨的 (位址, 背景) 對——gate-1 的 K9 紀錄在 200／200 seed 都有；可以從 k9 紀錄挑「在最多 seed 上可分辨」的位址與背景當 A2 清單 | hypothesis v0.3、k9-panel-v1 | R-K9-A 不改這份清單（它只改分母）；若 R-T 改刺激，A2 的「在 task 刺激下」要重算，但 A2 本來就允許用專用背景 |
| §5／A3 raw-observation schema | 可寫：禁止 expected value 的 schema 形式 | §5.1–5.3 | 若 R-T 加 target 觀測 phase，schema 多一個 phase 值；先留 enum 擴充位 |
| §6 A8 初始化觀測設計 | 可寫：INIT restore 與 SRVAL restore 的兩個示範怎麼做、少一個時 claim 失去什麼 | §5.1 step 2 | 與 K9 的 `ff_init` conditional-on-A8 對應 |
| §3 universe／holdout 選擇 | 可決定：address-only universe vs whole-site-instance holdout；哪個 site instance 是 holdout | §4.1–4.3 | 不依賴 gate |
| §6 A5 isolation 負測試的形式、A6 bench 清單、A7 standing check | 可寫 | §5.5 | 不依賴 gate |
| §8 falsifiers 的種類 | 可寫（invalid／incomplete 的種類；carrier 層的 falsifier 等 CV2） | §9.1 | — |

**不能推進的**：§7 的 N、B\*、prediction（來自 gate-2 或沒有）；§9 sessions、rates；§2 的 pins（lifecycle 未決）；carrier v2 RTL（2c-obs 之後、另有裁定）。

**本稿建議的順序**：若 owner 選 P1，2c-obs 可與 §5.1 的 #1／#2 **並行**（host-only、docs-only，互不讀取）；若選 P0，2c-obs 沒有上游，不該寫。

---

## 7. 本稿不做的事

不改任何 tracked 檔案；不跑 verifier、測試、模擬；不推導或列印任何 seed（只讀彙總讀的是已歸檔的 `curves.json`／`k9.json`／`k7.json`／`arm_O.result.json` 的記錄欄位，不觸及 `seeds.json` 的值）；不建立 `b4-sim-4`／`b4-gate-2`；不 commit、不 push、不 merge；不授權任何單位。`d19cc2f` 覆核的兩件文件收尾（README 時間 P3 分寫、owner 覆核紀錄歸檔）仍留待下一筆適當文件 commit，與本稿無關。

---

## 8. 資料影響揭露表（哪個觀察驅動了哪個選擇）

| 觀察 | 來源 | 驅動的選擇 | 事後程度 |
|---|---|---|---|
| `ff_srval` 中位數 0.427（S = 32）→ 0.406（S = 200）；owner 的 0.5 結構上界審核 | sim-3 報表、owner 2026-10-19 §2、gate-1 報表 | R-K9-A 的方向 | 完全事後 |
| tied-low 背景覆蓋恆 0；driven+sync+FF 0.575 ≈ 1 − (3/4)³ | gate-1 只讀彙總 | R-K9-A 的措辭（applicability 而非門檻）；R-K9-C 列為備選 | 完全事後；解析預期是獨立依據 |
| driven-only 中位數 0.8125／1.0 | gate-1 只讀彙總 | 只用來說明方向；**不是 v0.2.0 的依據或驗證** | 完全事後 |
| `sr_kind` 103／200 恰 0.5 | gate-1 只讀彙總 | 把 `sr_kind` 一併納入 R-K9-A | 完全事後 |
| Δ1、F − R、X − R 全負（S = 32、S = 200 方向一致） | sim-3、gate-1 報表 | 拒絕 R-S、R-N | 事後 |
| **Ω − R 十個 budget 全負；七臂 B = 256 中位數同為 41；最高 51／64；holdout ≈ 40／80** | gate-1 只讀彙總 | R-T 的方向；拒絕 R-O | 完全事後 |
| 生成器 docstring「reachability NOT guaranteed」；B2 D2 的遮罩規則 | 程式碼與 B2 文件（事前存在） | R-T 的形式（planted target） | 事前依據 |
| K7 學習曲線（B96 173／200 ≥ 11） | gate-1 報表＋只讀彙總 | 把「學得慢」列為次要原因，不列為修訂對象 | 事後 |

v0.2.0 的任何結果不得被描述為「由 sim-3／gate-1 的資料驗證」；此表併入 architecture v0.2.0 的修訂註記。

---

## 附錄 A：只讀彙總的方法

- 讀取對象：`evidence/b4/sim/b4-gate-1_20261020T102526Z/pair_{000..199}/{curves.json, k9.json, k7.json, arm_O.result.json}`（commit `5070967` 的 bytes，blob digest 已核對 4 005／4 005）。
- 做的事：`curves.json`：逐 seed、逐 budget 取 `best_at_grid[arm] − best_at_grid['R']`，算平均與正／負／平計數；逐臂取 `best_at_grid` 的中位數；逐 seed 取七臂在 B = 256 的最大值；`holdout` 逐臂平均。`k9.json`：對 `pairs[]` 中 `applicable = true` 且語意為 `ff_srval`／`sr_kind`／`sr_mode` 的對，用 `g0` 的位元 3（`sr_mode`）、0（`sr_kind`）、10（`storage_kind`）分層——這三個位元位置取自同一紀錄中 slice-wide 語意對的 `bit` 欄位——加總 `covered`；逐 seed 由 `summary.per_address` 算語意覆蓋率。`k7.json`：`prefixes[B].not_unknown` 逐 budget 的中位數與 ≥ 11 計數。`arm_O.result.json`：`result.group_moves`。
- 沒做的事：沒有呼叫 `b4_*` 任何模組；沒有重放、沒有重算 fitness、沒有生成任務或刺激、沒有讀 `seeds.json`。
- 腳本：session scratchpad（`read_curves.py`、`read_k9.py` 與一段 inline 讀取），不在 repo；需要時可由修訂單位以「唯讀診斷」身分重寫入 evidence，但本稿不要求。
- 與 owner 覆核的交叉：owner `independent_checks.json` 的 per-budget Δ1 mean／d／sign p／K7 中位數、K9 七個中位數、K10 計數與本稿引用的報表原值逐值相同。
