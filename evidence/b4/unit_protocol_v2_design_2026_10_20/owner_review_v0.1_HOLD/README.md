# Owner review — B4 protocol-revision scope draft (2026-10-20)

**HOLD：不批准 P1 直接進入 architecture v0.2.0 或工具實作。** 這不重開 d19cc2f 的工程驗收；b4-gate-1 維持 valid FAIL。R0 保留為可選擇停止本研究版本的方案，不自動選定。

審查對象：build/wip/b4_protocol_revision_scope_draft_2026_10_20.md；repo HEAD d19cc2faf5c42208ac020663ac81edf4bfafdf30。只讀檢查源碼與已歸檔 JSON，未執行模型、engine、replay、測試、模擬、gate 或 seed 推導，未改 tracked 檔案。

## 數字核對

另以只讀 JSON 彙總核實：Ω−R 十個 budget 均值全負；B=256 七臂中位數均 41、全體最高 51；七臂 holdout 均值 39.83–40.485；K9 tied-low 的 ff_srval/sr_kind covered 皆為 0，driven+sync+FF 為 7360/12800=0.575；sr_kind 恰為 0.5 者為 103 seeds。詳見 readonly_aggregate.json。這些核對接受的是描述值，不是草案的因果推論。

## R1 — P1：歸因強度超出證據

草案 §0、§1.2–1.3、§2.1、§2.3、R0、R-O 及停止規則需一併更正。

- oracle_view 只是 certificate-derived 固定分組：每元件一組、slice-wide bits 一組（b4_carto.py 的 oracle_view），配上既定 group_move；它不是所有 map/operator 的最優上界。Ω 輸給 R 不能排除 grouping、operator、task 與 budget 的交互，也不能證明 cartographer 不可能是因素。
- 最高觀測值 51、各臂中位數相同，以及生成器「不保證可達」，都不證明 ceiling 不可達、landscape 無可利用結構或任何 map 都不會贏。K10 已測得 interaction，也不能等同於 map 必有或必無收益。
- 正確措辭是本次樣本與指定設計未達預設正向收益及覆蓋條件；不得寫成 map 無益、ff_srval 不可觀測。後者與 200/200 seeds 有七語意正控制本身不相容。
- budget rule 與 K9 是不同判定構件；不等於已證明兩個獨立因果缺陷，亦不能宣稱只修其中一項，新 gate 就必 FAIL。改刺激可能同時影響兩者，新 seeds 的結果也不是舊樣本的必然延伸。

## R2 — P1：公開 planted genome 會公開已知解

R-T 的 g* 由 PublicTask.seed、公開 salt 和公開 PRNG 直接生成；PublicTask 同時把 seed 及 address order 交給各臂。若 target 是同一配置的觀測，執行端可直接恢復並評估 g*，不需要 map。這與 B2 D2 的公開 phenotype target 不等價：B2 的 phenotype→genome 對應並非免費提供。

下一份設計必須選清楚：這是公開已知解、限定固定 operators 的 benchmark，還是解對 executing side 不可取得的任務。後者需另立 task-construction 的私有輸入／公開輸出契約，不能仍從公開 seed 推導 g*、再宣稱它隱藏。只把欄位改名或不 import mapping 無法解決。若採 fabric-dependent target，需承認這是舊 mapping-independent public task 契約的實質變更，重新裁研究範圍；目前未批准這個變更。

## R3 — P1：planted target 不保證 ceiling 64，也不保證非平凡

21-bit 均勻 g* 可能是 latch 配置。現行模型在該配置不給 x5FF 四元件讀出；search mask 包含全部八個元素的八次 readout，而 scorer 對 None 永不給分。於是 g* 的 target trace 含 None 時，g* 自身也不能得 64；這不是 DOMAIN 問題。PublicTask 的 target 目前也只允許 0/1。

設計必須處理 target 的型別、固定 mask/ceiling 與缺失讀出；限制 planted 配置、改 mask 或改缺失值語意都是新研究設計，須具名揭露其先驗與影響，不能依當次 None 或分數篩選候選、變動 ceiling 或重抽。g*≠0 也不保證觀測不同於 base；不得把 genotype 不同當成 phenotype 非平凡性證明。

## R4 — P1：target 建構、隔離與成本契約尚未完整

- 搜尋與 holdout 使用不同刺激，需要各自的 target readout。依現行 observe(config, stimulus) API，不能以一次 search-target 觀測就聲稱兩者皆已取得；B+3/F 的 B+24 尚未成立。須列清 logical observations、physical calls、cache hits、共享 setup 成本與各臂成本，不先抄新常數。
- 先取得並綁定完整 task，再評 base。草案把 target 觀測放在 base 評分之後，需釐清預備 trace、task digest 形成與正式 evaluation 的時序，避免循環。
- target 不能進 cartographer、map/specimen、population、parent、champion、best-so-far 或 operator RNG。現行 entry 對非 holdout 都會 learn，單加 target phase 並不會自動隔離。
- 同一 pair 七臂必須使用同一份已固定 target 與來源身分；不能各臂重新量測各自 target。需列明 DOMAIN／SourceRefusal／中斷、來源漂移與 replay 的處理，不作 target redraw。
- holdout target 必須在搜尋之前固定，holdout trace/score 不進選擇、map 或調參；train 可達不代表 holdout 的完整 ceiling 可達。held-out-stimulus 行為一致性可以成為研究量，但不自動證明識別到唯一配置或一般化；與 whole-site engineering holdout 是兩個不同軸。

## R5 — P2：舊版重驗程序與版本辨識需補足

接受「舊證據不改、使用該版工具重驗」方向。但 git cat-file 已確認：933545a 不含 sim-3 archive，a243ee8 不含 gate-1 batch/gate archive，故單做 worktree add 到 execution HEAD 並不能完成重驗。

程序需分開 execution/code HEAD、archive commit（sim-3 的 5c08536、gate-1 的 5070967）及外部依賴，從 archive commit 取出原 bytes，在歷史工具及必要的歷史 inputs 下重驗，核對 digest；不要求更改歷史 Git tree 或原件。HEAD→tool digest 檢查只是必要條件，不是完整重驗程序。

版號移出 thresholds 表可以消除一項文字耦合；thresholds digest 不能單獨代表 task、panel、applicability、統計與 ledger 方法版本。需有具權威綁定的 machine protocol identity/digest，先識別支援版本，再進該版 schema／方法；不支援者具名拒絕並指向歷史重驗程序。不在本單位實作通用版本選擇器。

## R6 — P2：停止規則不能把代理量當成已證必要條件

Ω−R 的逐 seed 中位數≤0 不是「map 無益」的證明；ties 多時 median=0 仍可伴隨正的均值及正向 sign-test 結果。目前也沒指定用哪個 budget。若保留為節省成本的 go/no-go 政策，須事前指定 budget、統計量、ties、缺值及全部 planned seeds 的處理，明標為工程政策，不能寫成科學不可能性。

可達性也不保證有限次 search 會命中 64；「K1 不再恆成立」不能由 planted target 推成「本次一定有 seed 的 best_Ω=64」。兩版 FAIL 也不自動證明任何第三版都是 overfitting；可裁本計畫不自動續版，後續必須另有獨立論證與授權。所有方法、門檻與停止規則仍須在新探索前固定。

## D1 — R-K9-A 可以繼續設計，但屬新 estimand

SR tied low 時在此模型下沒有 SRVAL/SR-kind 效應，足以支持討論 SR-driven 條件下的 coverage。這是從全配置背景 coverage 改為條件 coverage，不是證明舊分母或舊判決錯誤。保留全 panel 的背景、分母、排除原因與未覆蓋報告，不能只報升高後比例；host applicability 不得進入 closed-book 搜尋。

0.575≈1−(3/4)^3 是事後機制解釋，不是獨立驗證；含 clock inversion 時應以 physical capture edge 描述，不能一律指定 stimulus 第1/3/5步。若聲稱解析預期，列明 Bernoulli／獨立性等近似前提與 PRNG 的區別。

## D2 — 2c-obs 與 routing 邊界

2c-obs 不依賴 gate 的 N/B*，不代表與 protocol 互不讀取；target phase 會影響 A3／A5 等契約。可留可獨立撰寫的內容清單，但 A2 若從最多成功的 gate-1 記錄挑選，須揭露 tuning，預先固定選法與 tie-break，另需板上驗收，不能稱獨立驗證。Address-only universe 與 whole-site holdout 不是互斥選項。

R0 只會停止所選 B4-FF 搜尋路線，不能推出獨立的 B4-R 必然失去全部上游；B4-R 依自己的 preregistration、R1–R7 與共用佈建／電源前置裁定。目前不授權 2c-obs tracked 文件或任何 routing 工作。

## D3 — scratchpad 彙總與後續授權

按「不寫程式」的原句，另寫 scratchpad 腳本確實超出字面邊界；不追稱原先已授權。此次只讀歸檔資料、未新觀測／推導 seed 的事後分析予以接受，不影響 gate-1；不得刪附錄或數字掩蓋實際操作。保留原腳本與完整輸出，與來源 commit/digest 一起留在 ignored 設計紀錄，後續適當文件提交再考慮歸檔；不要以重新跑新實驗補紀錄。

**現在授權一個完整的只讀設計修訂單位**：在 ignored 草案中一次處理 R1–R6、D1–D3；保留前稿，以清楚的新稿或修訂記錄呈現。可使用純讀既有 archive JSON 的彙總腳本，保留腳本、輸出與來源；不得呼叫 production model/engine/replay/seeds 產生新結果，不重算新 fitness、不生成新任務／刺激、不推導新 seed。整份完成再交審。

在上述契約釐清前，不選定 P1、不凍結 v0.2.0，也不授權任何 tracked 文件修改、工具實作、測試、模擬、gate、新 label 推導、commit、push、merge、RTL 或板上工作。b4-sim-4／b4-gate-2 僅為提案名稱，未分配執行授權。
