# Owner ruling — B4 protocol-revision scope v0.2 (2026-10-20)

**PASS 作為範圍提案；以下裁定取代未定選項及下列殘留歧義。** 不再要求第三份 ignored 範圍稿。下一單位是完整的 host-only 文件單位，不是實作、探索、gate 或矽上驗收。v0.2.0 是待寫入的 protocol 設計版本，不是已通過 gate 的版本。

審查基線：b4-gate-1-execution@d19cc2faf5c42208ac020663ac81edf4bfafdf30。已讀 v0.2 草案全文、保存的只讀紀錄與相應源碼；未跑測試、模型、replay、模擬或 seed 推導。tracked 樹乾淨。gate-1 的 valid FAIL 與舊證據原樣保留。

## 七項選擇

1. **接受 fabric-dependent planted target 作為一個新的 host benchmark 契約。** 不稱為修復 gate-1 的已證原因，不稱與 B2 D2 等價，也不從新版本的將來表現反推舊版 FAIL 的因果。必須披露 sim-3、gate-1、前稿與本次裁定對設計的影響。R0 仍是可停止研究的政策選項，但本輪選擇先完成新契約文件。

2. **採 H，限於固定程式與 API 的存取契約。** executing-side input 不直接帶 landscape seed、g* 或 private target 記錄；engine/carto 不讀 PrivateTask、host archive、mapping/hypothesis 或 diagnose，也不實作 seed/g* 的反推。operator seed 與控制流程依已宣告用途使用。不可寫成資訊論／密碼學隱藏；32-bit stimulus 可能洩露 seed 的限制仍披露。板上沒有自動獲得資訊隱藏或安全保證：物理分離也不能阻止從公開 stimulus 推回 seed，未來還須處理誰執行 target 配置、哪些程式看得到該配置與如何隔離。replay 證明既定程式序列一致，不是不可洩漏證明。

3. **採 T-i。** host 依證書 mapping 確定 storage_kind 位，固定為 flip-flop，其餘 20 位按事前固定規則一次抽取；不排除全零 base，不因 genotype 相同、trace 相同、低分或 None 而再抽。候選搜尋 universe 仍是原 21 位，search/holdout mask、權重、ceiling 64/80 與 None 不給分規則維持。target 的 FF-only 先驗及 latch 區的低分特徵須揭露；新主要比較不構成 latch-target 任務的證據。正式 target 出現 None/畸形值是 invalid，保留並停止，不切換到 T-ii 或縮 mask。T-ii/T-iii 不在本版本做。

   g*≠base 的特別拒絕條款刪除；相同或等價配置造成的平凡 pair 保留，仍按所有 planned seeds 統計。search 非平凡性由 R 臂既有 base/search-stimulus trace 與 target search trace 比對，不另加 harness base 呼叫；本版本不要求 base 的 holdout trace 比對，不得拿 search-base trace 冒充。這不是根據 gate-1 值訂新的非平凡性門檻；K1 原有兩中位數條件保留。

4. **採 K9 (b′) 的 SR-driven 條件 coverage 為新判定量，七語意中位數門檻仍為 0.50；K9 (a) 仍為至少 0.90 的 seeds 具七語意正控制。** 舊版全 panel (b) 並列作描述；其餘五語意的適用規則不改。舊版的 applicability（包括既有 latch/x5FF 排除）與新 conditional applicability 分開記錄，不能只把單一 applicable 改 false 就失去舊量。

   本版本保留舊 comparison set 的完整紀錄與舊 applicability 所要求的觀測，再由同一批 raw grids 分別重算 (b)/(b′)。不能把沒觀測的 tied-low 對依模型填 covered=0，冒充重測的全 panel coverage。K9 的兩套分母、排除原因、計數與比例均須能離線重算；host decode/applicability 不進 engine/carto。

5. **採工程 go/no-go：S=32、B_go=64、α_go=0.20。** 前提是所有 32 planned pairs 完整且來源／工具契約有效；在 B=64 的 Ω−R 正數多於負數，排除並報告 ties 後的單尾 exact sign-test p≤0.20，且 K9 (b′) 七語意中位數均≥0.50，方屬 go。缺值、invalid 或 incomplete 無 go/no-go 決定，停下報告。十個 budget 的描述值完整保留；不得改挑較好 budget。這只是成本政策，不是顯著性科學結論、不是完整 gate、也不自動授權下一次執行。沿用既定 stimulus 長度、SR 稀疏規則、operator、統計與其他正式數字；文件將規則明列後，探索前固定。

   採不自動續版政策：no-go 停下，valid FAIL 結案本版本，任何後續研究都須另有理由與授權，不寫成科學不可能性或第三版必然 overfitting。

6. **採多組件 protocol identity，文檔 revision 為資訊欄位；anchor 公式不變。** 執行／判定方法 payload 必須包括 thresholds、task、panel/applicability、K10、統計、engine/carto/execution/snapshot/replay、summary、judge、validators/verifiers 與 schema 的權威版本／digest，以及 hypothesis/certificate；可引用完整 tool-file inventory，避免漏掉 summary/judgement stack。schema 不只寫版本字串，也有其實際內容／實作 digest 綁定。不要產生自指 digest。

   archive payload 必須與由本版受信任 source/inventory 重建的 payload 比較，不能只核對 archive 自己記錄的 digest。architecture_revision 不僅排除於 hash，也排除於方法相等比較；仍保留為 provenance。畸形 identity 與不支援版本均具名拒絕，不做新版方法重判舊版。此處未授權通用版本選擇器。

7. **接受 A2 的資料知情 tuning 選法。** 在 gate-1 固定 K9 集內，各語意選跨 seeds covered 次數最多的 unique forced pair；tie-break 固定為 genome bit、g0、g1 的數值序，避免多個 backgrounds 合併後仍有歧義。ff_srval/sr_kind 只從 SR-driven 且舊 applicability 適用的 pair 選。須披露這是對 gate-1 的 tuning，不是事前未看資料的獨立驗證；board positive controls/A8 仍需另案。**本次不執行該選擇，不填 2c tracked 文件**，只在設計文件固定選法。

## 文件內必須直接落實的補充契約

### Target setup 與失敗紀錄

- 七臂共用一份在臂啟動前固定的 task。harness 做 search target 與 holdout target 兩次 setup 觀測，來自同一 source identity；臂觀測來源也須與之相符。
- PrivateTask 的抽取規則、salt、PRNG 將在文件固定；不把任何 production seed 推導當成寫文件的需要。task digest、公開／私有欄位與 target_source commitment 的計算範圍明列。
- 在第一次 target 呼叫前，先持久化 seed/pair 身分、g* 與預定 setup；每次 target 回傳立即保存 raw trace 與 provenance，然後才進下一次呼叫。第一次成功、第二次中斷也要留第一份結果。不能只在兩次都完成後才寫 task_private.json。
- setup 已開始的 pair 不得標「尚未開始」；依實際進度記 setup in-progress/partial 與停止點。DOMAIN/SourceRefusal/drift 為 invalid；deadline/外部中斷為 incomplete；沒有 redraw。完整 task 尚未形成時，不要求捏造完整 task digest 或臂紀錄。
- target 不走任何臂的 ledger/learn，不進 map、population、parent、champion、best-so-far 或 operator RNG；pair-level setup 有自己的紀錄與離線重建。holdout target/trace 不作搜尋、選擇、map 或調參的輸入；不因 setup 時已量測就稱為訓練資料。
- 成本設計為每 pair 共享兩次 setup；臂內預計 R/O/X/D/Ω/A0 為 B+2、F 為 B+23。這是待 fixture 呼叫數驗收的設計預期，不是實測結果；K9/K10 logical observations、physical calls、memo hits 另外逐項記錄，不能把 cache hit 當新 physical call。
- replay 使用保留的 target 觀測作一致性重建，不重新問 fabric；維持 observation authenticity limit，不把 replay-clean 當作 target 的物理真實性證明。

### 歷史重驗程序

接受使用 archive commit 的 worktree：sim-3 為 5c08536（code HEAD 933545a），gate-1 為 5070967（code HEAD a243ee8）。已核實 code→archive commit 除相應 archive 外零變更；不需這次真的建立 worktree 或跑 verifier。

草案 §5.2 步4「archive commit 的 registry 等於起跑前 snapshot」必須修正：前者多了本次 batch。實際值：sim-3 起跑前為空，archive tree 有自身；gate-1 起跑前恰有 sim-3，archive tree 有 sim-3 + gate-1。先對照 code HEAD 的起跑前 registry 與 manifest snapshot，再對照 archive commit 是該 snapshot 加本次具名 batch；核對各筆原 bytes/digest，不要刪目錄來湊相等。程序按該版欄位形狀與實際 inputs 清單檢查，不硬抄45個為通用常數。

仍須分清 code HEAD、archive commit、歷史 repo inputs 與外部依賴；無法滿足就具名停止，不回填或重判。舊 archive 與結果不動。

## 現在授權的完整單位

可由 d19cc2f 建立本地分支 **b4-protocol-v2**，完成一個純文件單位：

- docs/b4_architecture.md：DRAFT v0.2.0，寫入上述已選契約、數字、限制、資料影響與未實作狀態；明寫文件審核不等於新方法已經工具驗收、探索或 gate。
- docs/b4_archive_reverification.md：上述歷史重驗程序與兩個具名 archive 對照。
- evidence/b4/unit_protocol_v2_design_2026_10_20/：最小 README、兩版草案與本裁定的來源／digest、資料影響與選擇理由；保存的只讀彙總腳本與輸出可在此歸檔，不重新執行補結果。owner 來源依實際取得方式標明，不將摘錄寫成完整逐字原件。
- 順帶完成 d19cc2f 待辦：unit gate1 README 的31.7/49.6分鐘P3，以及該 owner review 目錄的來源歸檔；原 archive、判決、receipt、seeds 均不動。

整批本地一筆 commit 交審即可；單位內自行解決文件一致性、引用、表格與 diff 檢查，不逐步詢問。不改 b4/ 程式、hypothesis、IMPORT、thresholds 表或既有 architecture 之外的 frozen surfaces；不改 docs/b4_gate_execution_plan.md 的歷史計畫，不填實或凍結 2c skeleton。

不跑測試、模型、replay、verifier、mechanics batch、探索、gate 或 seed 推導；不 push/merge，不做 RTL、佈建、routing 或板上工作。b4-sim-4/b4-gate-2 僅保留為提案名稱，未授權推導或執行。套用 evidence proportionality 裁定；本次無須另做第三份 ignored scope 或單獨結案 commit。
