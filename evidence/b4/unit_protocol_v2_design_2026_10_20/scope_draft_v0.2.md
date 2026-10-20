# B4-FF protocol revision：只讀設計修訂稿 v0.2（2026-10-20）

**定位：只讀設計草案，等 owner 覆核。** 依 owner 2026-10-20 對 v0.1 草案（`build/wip/b4_protocol_revision_scope_draft_2026_10_20.md`，**保留不動**）的 HOLD 與同日授權（「一個完整的只讀設計修訂單位：保留前稿，在 ignored 草案中一次處理 R1–R6、D1–D3，完成後整批交審；可用純讀既有 JSON 的彙總腳本並保留紀錄；不授權 production 模組執行、新觀測、seed 推導、tracked 修改、commit、push／merge 或板上工作」）。覆核全文：`build/wip/owner_review_b4_protocol_revision_scope_2026_10_20/README.md`。本稿不是修訂、不是裁定、不是預註冊；v0.2.0、`b4-sim-4`、`b4-gate-2` 只是提案名稱，無任何執行授權。起點 `b4-gate-1-execution@d19cc2f`，tracked 樹乾淨。

**本稿做的只讀動作：** 讀原始碼（`b4_execution.py` 的 `PublicTask`／`observe_candidate`、`b4_engine.py` 的 run 時序、`b4_landscape.py` 的 scorer、兩個 verifier 對 HEAD 的比對）、讀 manifest 的外部輸入並核對其 sha256、`git log`／`git diff --stat`／`git ls-tree`／`git cat-file` 核對兩個 archive commit 與各自 code HEAD 的關係。沒有新的彙總腳本；v0.1 的腳本、完整輸出與來源已依 D3 存入 `build/wip/b4_protocol_revision_readonly_2026_10_20/`（README 列出每個檔案），本稿引用的描述值全部來自那裡或判決原值，owner 的 `readonly_aggregate.json` 逐值相符。

## 對照表：owner 的每一項在哪裡處理

| owner | 內容 | 本稿 |
|---|---|---|
| R1 | 歸因強度超出證據；R0 措辭；「只修一項必 FAIL」不成立 | §1 全部重寫；§2 改為「構件分析」而非因果歸因；§3.0 R0 重述；§3.5 R-O 重述；§6 停止規則重寫 |
| R2 | 公開 g\* = 公開已知解；須先決定研究接受哪種契約 | §3.1：兩種契約 K／H 的定義、主張、成本與誠實邊界；承認 fabric-dependent target 是 public-task 契約的實質變更，待 owner 裁研究範圍 |
| R3 | 植入不保證 ceiling 64；None；g\* ≠ base 不保證 trace 不同 | §3.2：target 型別、mask／ceiling、latch 的三個選項與各自先驗；非平凡性只以觀測記錄，不以 genotype 推論；不篩選不重抽 |
| R4 | 成本、時序、隔離、七臂共用、失敗處理、holdout | §3.3：每 pair 的建構順序、綁定、隔離機制、成本會計表（待工具單位以 fixture 核實，不先抄常數）、DOMAIN／SourceRefusal／漂移／中斷／replay、holdout 的兩個軸 |
| R5 | 重驗缺 archive 取得步驟；thresholds digest 不代表方法版本 | §5：已核實的事實、分 code HEAD／archive commit／歷史輸入／外部依賴的程序、protocol identity 的組成與拒絕路徑；不做通用版本選擇器 |
| R6 | 停止規則：代理量不是必要條件、未指定 budget | §6：工程 go／no-go 政策，事前固定統計量、budget、ties、缺值、全部 planned seeds；明標非科學不可能性；K1 措辭修正；「兩版 FAIL」改為 owner 政策 |
| D1 | R-K9-A 是新 estimand，不是舊判決錯 | §4：命名為 SR-driven 條件 coverage；全 panel 分母與排除紀錄並列；解析預期的前提與 physical capture edge 措辭 |
| D2 | 2c-obs 與 routing 邊界 | §7：A2 選法與 tie-break 預先固定、揭露 tuning；target phase 對 A3／A5 的影響；universe／holdout 兩軸；R0 不影響 B4-R |
| D3 | 保留腳本與輸出 | `build/wip/b4_protocol_revision_readonly_2026_10_20/`；§8 |

---

## 0. 結論（修正後）

1. **b4-gate-1 的 valid FAIL 保留為 protocol v0.1.16 的結果。** 正確的陳述是：**本次樣本（S = 200）與指定設計（hypothesis v0.3、task-v0.1、k9-panel-v1 的 applicability、固定的七臂與 operator、grid 8 … 256、§9 的判定程序）未達預設的正向收益條件（budget rule：無 budget 同時有 K1 eligibility 與 N）與覆蓋條件（K9 (b)：`ff_srval` 中位數 0.40625 < 0.50）。** 不寫成「map 無益」、「ff_srval 不可觀測」或「task 是原因」。
2. **描述性事實（owner 已核實）**：Ω − R 十個 budget 均值全負；七臂 B = 256 中位數同為 41；全體最高 51；holdout 七臂均值 39.83 … 40.49（ceiling 80）；K9 tied-low 背景下 `ff_srval`／`sr_kind` covered 皆 0；driven + sync + FF 覆蓋 7 360 / 12 800 = 0.575；`sr_kind` 恰 0.5 的 seed 103 個。這些是本稿候選設計的**動機**，不是任何因果結論的證明，也不是新版本的驗證。
3. **兩個判定構件分開處理，但不宣稱互相獨立的因果缺陷**：budget rule 與 K9 是不同的判定構件；一個 gate-2 要 PASS 必須兩個都滿足；刺激的改變可能同時影響兩者；新 seed 的結果不是舊樣本的延伸。
4. **候選設計**：(a) **R-T′**（task-v0.2，planted target）——先決問題是 **R2 的契約選擇**（已知解 benchmark K，或對 executing side 不可取得的任務 H）與 **R3 的 target 型別**；兩者都是研究範圍的實質變更，**本稿只列出選項與代價，不選定**；(b) **R-K9-A′**（SR-driven 條件 coverage，新 estimand，與全 panel 數並列）；(c) **R0** 保留為停止本研究版本的可選方案，不自動選定。
5. **歷史重驗**：archive commit（sim-3 `5c08536`、gate-1 `5070967`）的樹 = 各自 code HEAD 的樹 + archive，其他零變更（已 `git diff --stat` 核實）；重驗程序以 archive commit 建 worktree、核對 tool digests／inputs／外部依賴後跑該版 verifier；verifier 只比對 manifest 與 report 記錄的 head，不讀 live HEAD，所以可行。protocol identity 以多組件的 canonical 文件及其 digest 綁定，不以 thresholds digest 單獨代表。
6. **停止規則**改為事前固定的工程 go／no-go 政策（統計量、budget、ties、缺值、全部 planned seeds 皆指定），明標不是科學不可能性。

---

## 1. 本版本結果的正確陳述（R1）

### 1.1 能說的

- 在 v0.1.16 的設計下、S = 200 的 planned sample 上，Δ1 = O − R 的單尾 sign test 在十個 budget 都沒有達到 K5 的 power 條件，budget rule 的候選不存在，K1–K7 不可評；K9 (b) 的 `ff_srval` 中位數低於 0.50。
- 描述上，Δ1 的均值在十個 budget 為負（−0.485 … −0.940），F − R、X − R、D − R、A0 − R、Ω − R 的均值亦為負。這些差距的絕對值小（≤ 1 cell），ties 多（Δ1 每 budget 55 … 149 個）。
- 200／200 seed 七個語意各有正控制（K9 (a) = 1.0）：**可觀測性在正控制層面是成立的**；K9 (b) 量的是 panel 上的覆蓋比例。

### 1.2 不能說的（v0.1 草案寫錯或寫過頭的）

| v0.1 的句子 | 為什麼不成立 | 改寫 |
|---|---|---|
| 「原因不在 cartographer，在 task」 | Ω 是 certificate 導出的**固定分組**（每元件一組、slice-wide 一組）配既定 group move；它不是所有 map／operator 的上界。Ω 輸給 R 不能排除分組形狀、operator、task 與 budget 的交互，也不能排除 cartographer 是因素之一 | 「在此 task、此分組形狀、此 operator 與此 grid 下，固定的 certificate 分組沒有帶來正向收益；哪一個因素或哪一種交互造成，本資料不能分辨」 |
| 「landscape 無結構可用」「ceiling 不可達」 | 最高觀測 51、各臂中位數相同、生成器「不保證可達」都不證明不可達或無結構；K10 已測到 interaction（200／200），但 interaction 存在也不等於 map 必有或必無收益 | 「可達性未被保證也未被證明；本資料觀測到的上限是 51」 |
| 「負的樣本效應是『此 task 下 map 無益』的證據」 | 單尾檢定為「有益」設計；反向檢定未預註冊；「無益」是比「未達判準」強的主張 | 「未達預設正向收益條件；方向上 Δ1 的均值為負，只作描述」 |
| 「ff_srval 不可觀測」 | 與 200／200 seed 有正控制不相容 | 「在 k9-panel-v1 的 applicability 下，`ff_srval` 的 panel 覆蓋中位數未達 0.50」 |
| 「兩個獨立失敗；只修一個，gate-2 必 FAIL」 | 兩者是不同判定構件，不是已證的兩個獨立因果缺陷；改刺激可能同時影響兩者；新 seed 不是舊樣本的延伸 | 「gate-2 要 PASS 必須兩個構件都滿足；設計必須同時處理；對任一構件的結果不做預測」 |
| 「K1 (a) 在此 task 下恆成立、無鑑別力」 | 「恆」是推論；資料只顯示本次 p95 遠低於 64 | 「本次 K1 (a) 的 margin 大（Ω p95 39 … 46 對 64）；是否有鑑別力取決於 task 的可達性，本版本未保證」 |

### 1.3 R0 的正確表述

R0 = **停止本研究版本**：B4-FF 在 v0.1.16 下的結論是「未達預設收益與覆蓋判準」；線停在 gate（§9 自己的規定）。它不說 map 無益、不說 FF class 不可 map、不說 task 有錯。選 R0 的代價是 B4 §0 的問題在這一版沒有答案，**但 B4-R 不因此失去上游**：B4-R 有自己的 preregistration、R1–R7 與共用的佈建／電源前置，依自己的裁定（owner D2）。R0 不自動選定。

---

## 2. 兩個判定構件的分析（描述與機制，不是因果歸因）

### 2.1 Budget rule／K5

**資料（來源：判決原值與 `read_curves.out.txt`；owner 已核實）**：見 v0.1 §2.1.1 的表，數字不變。關鍵：Ω − R 均值 −1.010（B8）… −0.395（B256），B256 正／負／平 38／53／109；七臂 B = 256 中位數 41；best-of-seven 中位數 42、最高 51；holdout 七臂 ≈ 40／80；K7 的 O 在 B = 96 時 173／200 seed ≥ 11 個位址 not unknown；O 的 group move 約 123／256。

**可能的因素（列出，不排序為因果；本資料不能分辨它們的交互）**：

1. **task-v0.1 的 target**：逐 cell 由 seed 的 PRNG 產生 0／1，與任何配置無關；生成器自述可達性、非平凡性、interaction 皆不保證、留給未執行的 host audit。對照 B2 D2：target 遮罩到 universe，「the optimum is therefore reachable and unique」。**這是一個設計差異，不是已證的原因。**
2. **分組形狀**：Ω 的 group = 每元件的 (INIT, SRVAL) 對 + 五個 mode 位元一組；A0 = frame 分組；學到的 map 近似 Ω。group move 從一組內取 1 … 4 位；在逐 cell 隨機的 target 下，同組位元是否有協同利益**不知道**。
3. **operator**：random-safe 與 group move 各半（view 有 group 時）。同一 operator（B2 derived copy）在 B2／B3 的 LUT task 上贏過 R（B3 pooled primary 8／0／0）；這說明 operator 不是唯一變數，不說明它與 task-v0.1 無交互。
4. **budget grid 與動態範圍**：base 32 → best ≈ 41，差一兩個 cell 就翻正負；B ≤ 256 對 2²¹ 的空間很小。
5. **cartographer 的學習速度**（K7）：O 的 map 在 B ≤ 64 多半未達 11；但 Ω 從頭有完整分組仍無正向收益，所以**學習速度不是唯一因素**，不是「次要原因」的證明。

**holdout ≈ 機率水準**：與 1 一致（holdout 刺激有自己的隨機 target），但 B2 已說 holdout 對 lookup-table 表型是 neutrality／known-answer control；B4 的 holdout 在 v0.1 下的意義本來就只有這麼多。

### 2.2 K9 `ff_srval`

**資料（`read_k9.out.txt`）**：tied-low 背景（四類共 38 400 對）covered 0；driven + async + FF 0.8969、driven + async + latch 0.8888、driven + sync + FF 0.5750、driven + sync + latch 0.8888；逐 seed `ff_srval` 中位數 0.40625；`sr_kind` tied-low 0、driven 0.9125，逐 seed 恰 0.5 者 103。

**機制（分兩層，強度不同）**：

- **模型定義層（演繹，不是事後解釋）**：hypothesis v0.3 `sr_tied_low_when_not_driven = true`：`sr_mode = tied_low` 時 SR 永不斷言；SRVAL 是 SR 斷言時載入的值、`sr_kind` 是 SR 作用的方式——兩者在 SR 永不斷言的配置下**在此模型內**沒有可到達 trace 的路徑。所以 tied-low 背景的 `ff_srval`／`sr_kind` 對在此模型下必然 covered = 0。owner D1：「足以支持討論 SR-driven 條件下的 coverage」。這**不證明舊分母錯**：k9-panel-v1 的 estimand 是「全配置背景上的覆蓋比例」，它照自己的定義算出 0.406，判決正確。
- **事後機制解釋（不是獨立驗證）**：driven + sync + FF 的 0.575 與「元件在三個 physical capture edge 中至少一次被斷言 SR」的近似 1 − (3/4)³ = 0.578 相近。前提：task-v0.1 的 `_sparse` 對每元件每步獨立以 1/4 斷言 SR（PRNG 的近似為 Bernoulli、步間與元件間獨立）；synchronous SR 只在 physical capture edge 生效（`sync_sr_acts_on_edge_only`；**capture edge 在非反相時是 slice clock 的 rising edge，反相時是 falling edge**——六個 clock 步裡各有三個，不能一律寫成第 1／3／5 步）；SR 載入的值與 capture 值不同時才可見（SRVAL 0 對 1 必不同，所以這裡恆可見）；兩個 level 步無 edge。async 的 0.897 對應八步至少一次 1 − (3/4)⁸ = 0.900。這段只用來說明 R-K9-A′ 之外還有「刺激的 SR 稀疏與 sync 的 edge 門檻」在壓覆蓋率，**不是**新 estimand 的依據。

### 2.3 兩個構件的關係（修正）

不同的判定構件：K9 是 host-only 的可觀測性診斷（不進 search），budget rule 是搜尋臂的比較。**不宣稱**它們是兩個獨立的因果缺陷，也**不宣稱**修一個另一個必 FAIL。能說的只有：gate-2 要 PASS 兩者都要滿足；若 task-v0.2 改了刺激規則（例如 SR 的密度或 edge 結構），K9 的數字也會變；新 seed 的結果不可由 gate-1 推。

---

## 3. R-T′：planted-target task 的設計問題（R2、R3、R4）

### 3.1 先決：已知解 benchmark，還是對 executing side 不可取得的任務（R2）

**事實（讀碼核實）**：`PublicTask` 帶 `seed`、`addresses`、`base_genome`、兩組 stimulus／mask／target／weights；engine 讀 `task.seed`（寫進 `ctx()` → `observe_candidate` 的 context → DOMAIN 時進 `TerminalEvent`）、`task.addresses`、`task.stimulus`、`task.holdout_stimulus`、`task.base_genome`；`task.digest()` 含 `seed`。若 g\* 由 `Rng(seed ^ salt)` 公開規則產生，任何拿到 `PublicTask` 的程式都能重建 g\* 並直接評估它——這不等價於 B2 的公開 phenotype target（B2 的 phenotype → genome 對應不是免費給的）。v0.1 草案「生成器不 import mapping」沒有解決這點。

**兩種契約（owner 要先裁哪一種是這條線要做的研究）**：

| | **K：已知解 benchmark** | **H：解對 executing side 不可取得** |
|---|---|---|
| 定義 | target 是 g\* 的觀測；g\* 可由公開 seed 重建；主張限定在「固定的 closed-book operators（R／F／O／X 與控制）在不使用 seed 的前提下」的比較 | executing side（engine、cartographer、port 呼叫端）**不接收** landscape seed、g\*、或任何能重建 g\* 的量；只接收 stimulus、mask、weights、target（0／1 或 §3.2 的型別）、addresses、base_genome、task digest |
| 主張的形式 | 「在此 benchmark 上，map 引導的 operator 比 random-safe 更快逼近已知解」——與 OneMax 類 benchmark 同性質 | 「executing side 在不知道解的情況下，map 引導是否更快」——與 B1–B3「board builds its map from its own probes」的精神一致 |
| 執行上的保證 | 由 code review 與 replay 保證：replay 從 operator_seed 與記錄的觀測重新執行每個臂，任何不可由臂的程序推出的觀測是 replay finding | 同上，**加上** API 邊界：`PublicTask` 拆成 `PublicTask`（無 seed）與 harness 持有的 `PrivateTask`（seed、g\*、建構 salt）；`ctx()` 的 `landscape_seed` 改為 `task.digest`；`TerminalEvent.landscape_seed` 由 harness 在記錄時補上；replay 從 pair 紀錄取 seed，不從臂 |
| 誠實的邊界 | — | 在 host 模擬裡，「不可取得」是**程式邊界**而非資訊論的隱藏：host 同一程序持有一切；stimulus 由 `Rng(seed)` 產生，原則上可從 stimulus 暴力反推 32-bit seed 再得 g\*。我們的臂是固定程式且 replay 可重現，所以實務上不會；但契約文字必須寫成「executing side 的輸入不含 seed 與 g\*，closed-book 由 replay 審計」，不能寫成「隱藏」。**在板上（2c）**，host 持有 g\*、板只收到刺激與 target，邊界是物理的 |
| 成本 | 文件：§7 的 public-task 契約改為「target 來自一個配置的觀測」（**實質變更**，見下）；程式：`b4_landscape` v0.2、harness 的 target 觀測（§3.3） | K 的全部 + `PublicTask` 拆分、`ctx()`／`TerminalEvent`／replay／`b4_sim_schema` 的欄位變更、engine 的 `task.seed` 用法移除、tests 與 mutants（「臂拿到 seed」要成為被殺的 mutant） |
| 2c 的差異 | 板上也可直接評估 g\*（若板拿到 seed） | 板不拿 seed 與 g\*；target 的觀測由 host 側在 session 前以板觀測一次（known-answer 性質；見 §3.3 holdout 段） |

**承認：** 不論 K 或 H，「target 是某配置在 fabric（模型或板）下的觀測」是對 §7「landscape generation rule must not consult the certificate, the map or the operator」之外新增的依賴——**task 依賴 fabric**（模擬時依賴 hypothesis，板上依賴矽）。這是 mapping-independent public task 契約的實質變更，需 owner 重新裁研究範圍；目前未批准。替代方案「不依賴 fabric 但保證可達」在不知道模型的情況下做不到（可達集合由模型定義）。

**本稿的建議**：若 owner 接受契約變更，**H**；理由是它與 B1–B3 的主張形式一致，而且它的額外成本（API 拆分）本來就是審計上的好事（臂的輸入清單變短、可被 mutant 檢驗）。但 K 是合法的研究選項——若 owner 認為這條線問的是 operator 的效率而不是 closed-book 的發現，K 更便宜。

### 3.2 target 的型別、mask／ceiling 與 None；非平凡性（R3）

**事實（讀碼核實）**：`PublicTask.target` 是 0／1 per mask cell；`_score`：`q is None → nones += 1`，不給分；mask 是 init 步之後每步每元件（8 × 8 = 64）；hypothesis v0.3 下 `storage_kind = latch` 時 A5FF … D5FF 不是 storage element，其 `q_after` 為 None（`x5ff_not_storage_when_latch`）；v0.3 下 21 位元每個 assignment 都在 domain 內（所以這不是 DOMAIN 問題）。21-bit 均勻的 g\* 有一半是 latch 配置：其 search trace 有 4 元件 × 8 步 = 32 個 None cell，**g\* 自身在現行 scorer 下至多 32／64**；holdout 同理 40／80。

**三個選項（每個都是新研究設計，先驗與影響具名；都不得依當次 None 或分數篩選、變 ceiling 或重抽）**：

| 選項 | 內容 | 先驗（揭露） | 影響 |
|---|---|---|---|
| **T-i** | g\* 從 **flip-flop 配置**抽（`storage_kind` 位固定 0，其餘 20 位均勻）；target 仍 0／1；mask／ceiling 不變（64／80） | target 的行為空間排除 latch；search 空間不變（latch 配置仍可被搜尋，其 x5FF cell 永遠不得分 → latch 區是低分區，這是 landscape 的一個特徵，被揭露） | §9 的 64、57.6 等數字不動；K1 (a) 的「< 64」保留意義 |
| **T-ii** | g\* 全 21 位均勻；**mask 排除 target 為 None 的 cell**；ceiling = 該 task 的 mask 大小（64 或 32；holdout 80 或 40），在 task 建構時固定、寫進 task digest | 允許 latch 行為當 target；但一個 latch target 的 task 只量四個主元件，FF 配置也可能完全匹配（x5FF 被忽略） | §9 的 K1／K4 的絕對數改為 ceiling 的比例（64 → `ceiling`、57.6 → 0.9 × `ceiling`）；thresholds 表與 pin test 改動較大；per-task ceiling 進 manifest |
| **T-iii** | g\* 全 21 位均勻；target 三值（0／1／None）；scorer 改為 None = None 得分 | 獎勵「成為 latch」本身；改變「None == None is not a hit」的既定規則 | 與 §7「a None cell scores nothing」衝突；不建議 |

**建議 T-i**（改動最小、§9 數字不動），**T-ii 為替代**（若 owner 要 latch 行為在 target 空間內）。**選哪一個不能用 gate-1 資料決定**；兩者都是先驗。

**非平凡性**：g\* ≠ base（genotype）**不是** phenotype 非平凡的證明。設計：per seed 記錄 `target_search_equals_base_trace`、`target_holdout_equals_base_trace`（observed，由兩次 target 觀測與 base 的 trace 比對；base trace 在臂內觀測，所以這個比對由 harness 在第一個臂完成 base 後做，或由 harness 自己多觀測一次 base——後者多一次呼叫，見 §3.3 成本表）、`base_score_under_task`；**政策：記錄、不重抽、seed 留在 planned list**（它對 Δ 貢獻 ties）；聚合層由 K1 的 `median_r(best_R) > median_r(base_r)` 守住；若 owner 要單獨的非平凡性門檻，形式是「`median_r(base_r) ≤ 0.9 × ceiling`」且在探索前定。「可達」也不保證有限次 search 命中 ceiling；K1 (a) 的措辭改為「p95(best_Ω) < ceiling」仍是非飽和條件，**不預測**本次會有 seed 的 best_Ω = ceiling。

### 3.3 建構、綁定、隔離、成本與失敗處理（R4）

**每 pair 的順序（harness，在任何臂之前）**：

1. 由 landscape seed 的公開規則產生 search stimulus、holdout stimulus、mask、weights（task-v0.1 的 `_stimulus`／`_mask_target` 的 stimulus 部分；target 不再由 PRNG 產生）。
2. 由 harness 的 `PrivateTask` 規則產生 g\*（T-i／T-ii 的抽法；自己的 salt、自己的 generator；抽到 base 時記錄並取該 generator 的下一個值——**記錄，不換 seed**）。
3. harness 經**同一個 execution port** 觀測 g\* 於 search stimulus（phase `target`），再於 holdout stimulus（phase `target_holdout`）——**兩次 logical observation，兩次 physical call**（`observe(config, stimulus)` 一次只接一個 stimulus，所以 holdout 的 target 不能從 search 的觀測得到；v0.1 的「+1」錯）。兩次觀測的 provenance header 記錄並要求相等。
4. 形成 `PublicTask`（H：無 seed、無 g\*）與 task digest = sha256(label, version, addresses, base_genome, stimulus, mask, weights, target, holdout_stimulus, holdout_mask, holdout_target, holdout_weights, **target_source_sha256**)；寫 pair 層的 `task.json`（public 部分）與 `task_private.json`（seed、g\*、salt、兩次 target 觀測的完整 trace 與 provenance；**臂不讀此檔**）。
5. **七個臂收到同一個 `PublicTask` 物件**（同 digest）；每個臂照現行順序：base 觀測 → （F：21 probes）→ search → holdout。base 在 task 綁定之後評。臂的 provenance 必須與 target 觀測的 provenance 相等（harness 比對；不等 = `input_drift` 類的 invalid）。
6. K7／K9／K10 照舊（K9 用 task 的 search stimulus；K10 的背景規則不變）。

**隔離（by construction，並由測試固定）**：target 觀測發生在 harness，不經 engine 的 `observe()`／`entry()`，因此**不進任何臂的 ledger、不經 `learn()`、不進 population／parent／champion／best-so-far、不消耗 operator RNG**（現行 `entry()` 對非 holdout 皆 learn——這正是 target **不能**走 engine 路徑的理由）。臂拿到的 target 是 0／1 向量（T-i）或 0／1 加 mask（T-ii），與 v0.1 的隨機 target 同型別。mutant：「harness 把 g\* 塞進 PublicTask」「engine 的 ctx 帶 seed」「target 觀測進 ledger」各一個，必須被殺。

**失敗處理（不作 target redraw）**：步驟 3 的任一觀測 DOMAIN（v0.3 下不應發生）或 SourceRefusal → **pair invalid → batch invalid（§9.1 的契約破壞）**，紀錄保留，不重抽、不換 seed；中斷（deadline）落在步驟 3 → 該 pair 未開始，照 §3 的 incomplete 處理，`task_private.json` 若已寫則保留；provenance 漂移（target 與臂之間或臂與臂之間）→ invalid。**replay／deep verify**：verifier 從 `task_private.json` 的 g\* 經 replay port 重執行兩次 target 觀測、比對記錄的 trace，重算 task digest，再照現行方式重放每個臂；所有臂的 `task_digest` 必須等於 pair 的。

**成本會計（設計的宣稱；數字由工具單位以呼叫數 fixture 核實，不先入常數）**：

| 項目 | logical observations | physical port calls | 共享 |
|---|---|---|---|
| harness：target（search）＋ target（holdout） | 2 | 2 | 七臂共用 |
| harness：base 的非平凡性比對（若採「harness 自觀測 base」） | 1 | 1 | 七臂共用（亦可改為讀第一個臂的 base trace：0 次） |
| 每臂 R／O／X／D／Ω／A0 | B + 2（不變） | B + 2 | — |
| 每臂 F | B + 23（不變） | B + 23 | — |
| K9／K10 | 不變（memo 的 hit 不算 physical call） | 不變 | — |

cache hit：現行 K9 memo 是 per seed，target 的配置 g\* 是否落在 panel 的 1 184 端點內屬偶然，不設計成依賴。總增量每 pair **+2（或 +3）physical call**，臂內不變；**這些數字要由工具單位的 fixture（固定小 budget、固定 fixture seeds、核對 `port.calls` 與 `cost`）確認後才寫進文件**。

**holdout 的兩個軸**：(a) **held-out-stimulus 行為一致性**：champion 在 holdout 刺激下與 g\* 的 holdout trace 的匹配——這是一個研究量，不自動證明識別到唯一配置或一般化（多個配置可產生同一 search trace）；(b) **whole-site engineering holdout**（2c 的 site instance）——另一個軸，與 (a) 不互斥。holdout target 在步驟 3 固定、在任何 search 之前；holdout trace／score 不進選擇、map 或任何調參；train 可達不代表 holdout 的 ceiling 可達（T-ii 下 holdout 的 mask 由 holdout target 的 None 決定；T-i 下 g\* 為 FF 配置，holdout 的 None 不出現，但「可達」仍只是 g\* 自己達到）。

### 3.4 其餘被拒絕的方向（措辭修正）

- **R-S 改統計**：不選。理由不是「Δ1 為負所以無解」（那是過度解讀），而是：沒有 v0.2 的資料可用來訂統計參數，用 v0.1 的資料訂就是對資料擬合；owner 2026-10-19 §2 已排除擴大 S。
- **R-O 換 operator**：不在本修訂做。**不因為**「operator 已被排除」——本資料不能分辨 operator 與 task 的交互——而是因為一次只改一個主要變數才能把 v0.2 的結果歸到 task 契約的變更；若 v0.2 探索後 Ω − R 的 go 條件（§6）仍不成立，operator／分組形狀是下一個候選變數，另立單位。
- **R-N 同版換 label 重跑**：不選（owner 2026-10-19 §1）。
- **R-K9-D 降門檻**：不選。

---

## 4. R-K9-A′：SR-driven 條件 coverage（新 estimand；D1）

- **命名**：`K9 (b′) — conditional coverage under SR-driven backgrounds`，與 k9-panel-v1 的 `K9 (b) — coverage over all panel backgrounds` **並列**；兩者都報告，各自有 median；新版本的判定讀 (b′)，(b) 保留為描述。
- **定義**：對 `ff_srval`、`sr_kind`：applicable 的額外條件「g0 與 g1 兩端點的 `sr_mode = driven`」（兩端點在這個 slice-wide 位上相同，所以等價於 g0 的位 3 = 1）；其餘五個語意不變。排除的對**全部列出**：address、backgrounds、兩端點 genome、排除理由 `sr_tied_low`（與現行 `latch` 理由並列），在 `k9.json` 的 `pairs[]` 以 `applicable = false, reason = "sr_tied_low"` 記錄，`summary.per_address` 同時給 `applicable_all_panel`／`applicable_sr_driven` 兩組計數與比例。
- **不宣稱**舊分母或舊判決錯；v0.1.16 的 (b) 正確地算了它定義的量。
- **host applicability 不進 closed-book 搜尋**：K9 本來就是 host-only 診斷，新條件也只在 `b4_k9.py`；engine／carto 不讀。
- **解析預期（若在 v0.2.0 的探索前寫成預測）**：寫明前提——`_sparse` 的 Bernoulli(1/4) 近似、步間與元件間獨立、sync SR 只在 physical capture edge（三個，極性由 clock_mode 決定）生效、async 八步皆可、SRVAL 0 對 1 恆可見——得到 driven + async ≈ 0.90、driven + sync ≈ 0.58，加權（async／sync 各半、latch 恆 async）≈ 0.8；**這是一個模型下的近似，不是獨立驗證**；若 task-v0.2 改了 `_sparse` 或 K，數字重算。事後重算的 0.8125 只是 gate-1 樣本在新定義下的描述值，**不是** v0.2.0 的依據。

---

## 5. 歷史重驗程序與 protocol identity（R5）

### 5.1 已核實的事實（`r5_git_readonly_checks.txt`）

- sim-3 的 archive commit `5c08536` 的 parent = 記錄的 execution HEAD `933545a`；gate-1 的 `5070967` 的 parent = `a243ee8`。兩者的樹 = code HEAD 的樹 + archive，**其他零變更**（`git diff --stat` 排除 archive 目錄後為空）。
- `933545a` 的樹不含 `evidence/b4/sim/`；`a243ee8` 的樹含 sim-3 archive、不含 gate-1 的 batch 與 gate 目錄（owner 的核對一致）。
- sim-3 manifest 的 23 個 tool digests 全部由 `933545a` 樹的 blob 重現；gate-1 的 25 個 = `00336d0` 基線（b4/ 零 diff）。
- gate-1 manifest 的 6 個外部輸入（UNISIM 的 FDCE／FDPE／FDRE／FDSE／LDCE／LDPE .v，絕對路徑）今日仍在且 sha256 相符。
- 兩個 verifier 都只比對**記錄**的 head（manifest 對 report；gate report 對 batch），不讀 live `git rev-parse HEAD`、不檢查 porcelain。所以在 archive commit 的 detached worktree 裡跑歷史 verifier是可行的，不需要改任何歷史 tree 或原件。

### 5.2 程序（文件化；由修訂單位交付為 `docs/` 的一頁，每一步有停止點）

| 步 | 動作 | 停止條件 |
|---|---|---|
| 1 | 從 archive 的 `manifest.json` 讀：`head`（code HEAD）、`tool_files`、`inputs`（repo 內 45 檔）、`external_inputs`（絕對路徑 + digest）、`exclusion.registry_snapshot`、receipt | manifest 不可讀或 schema 不符 → 停 |
| 2 | 找 archive commit：`git log --diff-filter=A --format=%H -- <archive dir>` 的最早一筆；核對其 parent = code HEAD 且 `git diff --stat <code HEAD> <archive commit> -- . ':(exclude)<archive dirs>'` 為空 | 不成立 → 具名記錄差異，停；不以其他 commit 代替 |
| 3 | `git worktree add --detach <dir> <archive commit>` | — |
| 4 | 在 worktree 內核對：`tool_files` 每個 digest 等於檔案 sha256；`inputs` 每個 digest 相等；`external_inputs` 每個絕對路徑存在且 digest 相等；`evidence/b4/sim/` 的 registry 內容等於 `registry_snapshot` | 任一不等 → 停，具名；**外部輸入缺失不以替代檔補** |
| 5 | 在 worktree 根以 `python3 -B` 跑該版 `b4/host/b4_sim_verify.py <archive>`（及 gate 的 `b4_gate_verify.py`），三行標頭（archive commit、code HEAD、命令、UTC）存檔 | exit 非 0 或 findings 非空 → 照該版 verifier 的 finding 記錄；不是新判決 |
| 6 | 核對 worktree 內 archive 的 bytes 與 live repo 的同 commit blob 相同（同一 commit，恆等；仍記錄） | — |
| 7 | 紀錄存進執行重驗的單位的 evidence 目錄；worktree 移除 | — |

HEAD → tool digest 的檢查（步 4 的一部分）只是必要條件；完整程序是 1–7。

### 5.3 protocol identity（機器可讀的方法版本；不是通用版本選擇器）

**問題**：thresholds 表的 digest 只覆蓋數字；task 版本、panel 版本、applicability 規則、統計複本、ledger／record schema、engine／carto／replay 的方法都不在裡面。

**設計**：`b4/host/b4_protocol.py` 產生一份 canonical JSON 文件 `protocol_identity`：

```
{ "architecture_revision": "<文字，資訊用，不入 digest>",
  "thresholds_sha256": sha256(canonical THRESHOLDS 不含版號文字),
  "task": {"version": "task-v0.2", "module_sha256": <b4_landscape.py>},
  "k9": {"panel_version": "k9-panel-v1", "applicability_rule": "v2-sr-driven", "module_sha256": <b4_k9.py>},
  "k10": {"module_sha256": <b4_k10.py>, "tau": 2},
  "statistics": {<七個複本函式名>: <per-function digest，來自 IMPORT.json>},
  "engine_sha256", "carto_sha256", "replay_sha256", "execution_sha256", "snapshot_sha256",
  "schemas": {seeds: "1.2.0", manifest: "1.2.0", gate_report: "1.0.0", ...},
  "hypothesis_sha256": <v0.3>, "certificate_sha256": <...> }
protocol_sha256 = sha256(canonical JSON 不含 architecture_revision)
```

- manifest 記錄整份 identity 與 `protocol_sha256`（新欄位；manifest schema 升版；舊 manifest 無此欄位 → 視為「v0.1.16 身分」由 `tool_files` 與 thresholds 表推定，**只用於拒絕訊息的命名**）。
- verifier 啟動時計算自己樹的 identity；與 archive 的相等 → 進入本版 schema／方法；不等 → **具名拒絕**：列出不同的組件（哪些 digest／版本不同），指向 §5.2 的程序，exit 非 0；**不**重判、**不**逐欄比對、**不**實作多版本分派。
- 版號文字移出 THRESHOLDS 表（v0.1 的方案 C）仍做，但它只消除一項文字耦合；方法版本由 identity 代表。

### 5.4 label 與 seed（不變的部分）

anchor 公式不變（`sha256(label|HYPOTHESIS_SHA256)[:4]`）；新版本必須用新 label（task 版本不在 anchor 內，同 label 會重現同一組 seed）；`b4-gate-1`／`b4-sim-3` 進已消耗清單，harness 拒絕再推導；exclusion 自動含 gate-1 的 401 值。是否把 `protocol_sha256` 併入 anchor：**不建議**（anchor 綁模型，label 綁一次執行，protocol 在 manifest），owner 定。

---

## 6. 停止政策（工程 go／no-go；R6）

**定位**：下面每一條都是**為了不浪費 gate 預算的工程政策**，在探索前固定，明標**不是**科學上的不可能性判定；no-go 不建立「map 無益」或任何否定命題；go 也不預測 gate 結果。

### 6.1 探索 `b4-sim-4`（S = 32）後的 go／no-go

| 項 | 規定 |
|---|---|
| 前提 | 32 個 planned seed 全部 `complete` 且 batch 非 invalid、非 incomplete；否則**無決定**（§9.1 的規則先於本政策），停下報告 |
| 統計量 1 | Ω − R 的單尾 exact sign test（`b4_gate_stats.sign_test_p` 複本；H1: P(Ω − R > 0 \| ≠ 0) > ½；ties 排除於 n、計數並報告）於**事前指定的 budget `B_go`**；本稿提議 `B_go = 64`（grid 中段；owner 定）；同時報告十個 budget 的 p、均值、正／負／平、d（描述） |
| 統計量 2 | K9 (b′) 七個語意的逐 seed 中位數 |
| go 條件 | 在 `B_go`：positives > negatives **且** p ≤ `α_go`（提議 0.20，owner 定）；**且** K9 (b′) 七個中位數皆 ≥ 0.50 |
| no-go 的意義 | 「在 S = 32 上，固定的 certificate 分組配既定 operator 未顯示正向訊號」或「新 estimand 下覆蓋仍不足」——**代理量**（Ω 不是所有 map 的上界），用來決定是否花 gate 預算；no-go 後的下一步（換分組形狀／operator、改刺激、或結案）各自另立單位 |
| 缺值 | 任何 pair 的任一臂無 B_go 的值（不可能發生於 complete batch；若發生 = invalid） |
| 不做 | 不在探索後改任何門檻、panel、規則、`B_go`、`α_go`；不以探索的 K5 scan 結果調 S 或 d |

### 6.2 gate `b4-gate-2` 之後

- valid FAIL：v0.2.0 的結果，記錄並結案本版本。**owner 政策（提議）**：本計畫不自動續版；任何 v0.3 需獨立的估計量論證與授權。**不寫成**「兩版 FAIL 證明第三版必是 overfitting」。
- invalid／incomplete／init_failed：照 gate-1 計畫 §3；label 消耗。

### 6.3 措辭修正

- 「K1 (a) 不再恆成立」→「task-v0.2 下 ceiling 由構造可達；K1 (a) 是否在本次有 seed 達到 ceiling 不預測」。
- 「Ω − R 中位數 ≤ 0 就停」→ 刪除；代之以 6.1 的 sign test 在指定 budget 的政策（中位數在 ties 多時為 0 卻可伴隨正均值與正向 sign test）。

---

## 7. 2c-obs 可獨立撰寫的內容（D2；只列清單，不授權 tracked 文件）

| 項 | 能寫什麼 | 條件與揭露 |
|---|---|---|
| A2 positive-control 位址 | 七個語意各一個 (address, background) 對 | **選法事前固定**：每語意取「在 gate-1 的 K9 紀錄中 covered 的 seed 數最多」的對；tie-break：genome bit 小者、背景 genome 小者；**揭露這是對 gate-1 紀錄的 tuning**；板上驗收另依 carrier 裁定，**不稱獨立驗證**；若 R-K9-A′ 採用，`ff_srval`／`sr_kind` 的候選只從 SR-driven 背景取 |
| A3 raw-observation schema | 禁止 expected value 的 schema | 若 R-T′ 採 H，phase enum 增 `target`／`target_holdout`，且 schema 要能表達「此觀測不屬任何臂」；A3 與 protocol 互讀，不是互不相關 |
| A5 isolation 負測試 | 形式 | 若有 target phase，測試要涵蓋「target 觀測在 base 之前」的殘留 |
| A8 初始化觀測設計 | INIT／SRVAL restore 的兩個示範；少一個時 claim 失去什麼 | 不依賴 gate |
| universe／holdout | address-only universe 與 whole-site holdout **不互斥**，可同時定 | 不依賴 gate |
| A6／A7 | bench 清單、standing check | 不依賴 gate |
| falsifiers 的種類 | §9.1 的 invalid／incomplete；carrier 層待 CV2 | — |

不能推進：N、B\*、prediction、sessions、rates、pins（lifecycle 未決）、carrier v2 RTL。**R0 不影響 B4-R**（§1.3）。

---

## 8. 揭露表與紀錄（R1、D3）

| 觀察 | 來源 | 驅動的選擇 | 性質 |
|---|---|---|---|
| Ω − R 十個 budget 均值全負；七臂中位數 41；最高 51；holdout ≈ 40／80 | gate-1 只讀彙總（`read_curves.out.txt`；owner 核實） | R-T′ 的**動機**（task 契約是候選變數之一） | 事後描述；不證明 task 是原因 |
| tied-low 覆蓋恆 0；driven+sync+FF 0.575 | gate-1 只讀彙總（`read_k9.out.txt`） | R-K9-A′ 的動機；機制解釋的前提 | 模型定義層為演繹；0.575 的解釋為事後 |
| driven-only 中位數 0.8125／1.0 | 同上 | 僅說明方向 | 事後；非依據非驗證 |
| `sr_kind` 103／200 恰 0.5 | 同上 | 把 `sr_kind` 納入 R-K9-A′ | 事後 |
| 生成器「reachability NOT guaranteed」；B2 D2 | 程式碼與 B2 文件 | R-T′ 的形式 | 事前存在的設計差異 |
| `PublicTask` 帶 seed；engine 的 ctx 帶 seed | 讀碼（本稿） | §3.1 的 K／H 契約 | 事實 |
| scorer 對 None 不給分；latch 的 x5FF None | 讀碼（本稿） | §3.2 的 T-i／T-ii／T-iii | 事實 |
| archive commit = code HEAD + archive；verifier 不讀 live HEAD | git 只讀核對（本稿） | §5 的程序可行性 | 事實 |

紀錄位置：`build/wip/b4_protocol_revision_readonly_2026_10_20/`（腳本、完整輸出、git 核對、README 含來源 commit `5070967` 與 blob 核對引用）。不刪、不重跑補紀錄。

---

## 9. 本稿不做的事

不改任何 tracked 檔案；不跑 verifier、測試、模擬、production 模組；不推導或列印 seed；不建立 `b4-sim-4`／`b4-gate-2`；不 commit、push、merge；不選定 P1／K／H／T-i；不凍結 v0.2.0；不授權 2c-obs tracked 文件、carrier、2d、routing、板上工作。`d19cc2f` 覆核的兩件文件收尾（README 時間 P3、owner 覆核紀錄歸檔）與本稿無關，仍待下一筆適當文件 commit。

## 10. 需要 owner 裁定的問題（本稿交審的核心）

1. **研究範圍**：是否接受「target 來自一個配置在 fabric 下的觀測」這個 public-task 契約的實質變更？不接受 → R-T′ 整段作廢，剩 R0 或另尋不依賴 fabric 的 task 構造（本稿未找到）。
2. **契約 K 或 H**（§3.1）。
3. **target 型別 T-i 或 T-ii**（§3.2）。
4. **R-K9-A′ 是否作為 v0.2.0 的判定 estimand**（(b′) 判定、(b) 並列報告）。
5. **go／no-go 的 `B_go`、`α_go`**（§6.1）與「不自動續版」政策（§6.2）。
6. **protocol identity 的組件清單**（§5.3）是否如列；版號文字是否移出表。
7. 2c-obs 的 A2 選法是否接受為預先固定的 tuning（§7）。

裁定前，本稿不進入任何實作。
