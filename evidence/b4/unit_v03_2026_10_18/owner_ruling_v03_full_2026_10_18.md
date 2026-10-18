# The owner's full ruling on the v0.3 scope draft (2026-10-18) — archived verbatim from `build/wip/b4_v03_model_revision_owner_ruling_2026_10_18.md` (the owner's P3 on `12eaa72`)

# v0.3 模型修訂：範圍裁定（2026-10-18）

依據：`build/wip/b4_v03_model_revision_scope_draft_2026_10_18.md`，起點 `b4-prework@c0689f8`，十四筆本地 commit 保留。main 仍 `d5bf815`，乾淨。本輪只讀核對草案、既有模型／engine／loader 與本機 UNISIM LDCE 原文，未執行新模型或實作修訂。

**授權按以下修正版範圍實作 v0.3；不必再送同一範圍的草案。完成後本地 commit 交覆核，不 push、不 merge。**

## 1. 來源強度：三層分開，不做二選一

- L1 來源條目標 `host exploration/readback/bitstream correspondence`。正式新增來源先只 pin D1′ attempt 2 的 `probe_report.json`，README 作導讀，不另作行為來源。這是一組端點的 host 對應紀錄，不是 certificate 或 silicon attestation。
- L2 維持既有 UNISIM 檔案／digest／採用行，解釋 primitive 在廠商模擬模型中的規則。不得聲稱這份模型已觀測或證明矽。
- **整個 v0.3 解碼規則**應標為「由 L1／L2 支持、在明列推廣假設下採用的模型讀法」；不能因 L1 有紀錄就把整個 domain 的推廣排除於 assumed 之外。檔案頂層 `status: unverified` 與 loader 的強制檢查不變。

G1–G6 要保留具名，但修正其範圍：

1. G1：固定 latch context 與 CLKINV 值後，其餘 **19 個自由位元**的組合推廣；不要把一組端點對應說成全部配置的證明。
2. G2/G3：區分 host 模型的定義與未來外推矽所需的未驗證前提。用 UNISIM 建立本次模擬不等於已接受「UNISIM 即矽」為實機事實；也不必另斷言與 FF 共用同一個實體反相 mux。
3. G4：保留工具版本／配方的來源條件，不宣稱已證明其他工具、anchor 或 LUT 佔用下均可移植。超出凍結來源的外推仍未驗證。
4. G5：certificate mapping 給出位址與 slice 粒度，不承擔「讀法可推廣到其他組合／所有適用元件」的行為證明。其他組合、LDPE 等使用新讀法的推廣屬 L3；不擴到其他 site 或 holdout。
5. G6：明列既有 init 的原子語意：在 init 步 Q:=INIT，不 settle；第一個 set 步才按既有順序 settle。若把 init readout 類比 GSR，必須限定為 GSR 有效時的讀出，或明標的原子抽象；不能把它當成 GSR 釋放後、gate 開且 GE 有效時仍保持 INIT 的證據。carrier 是否能提供這個讀出窗口仍是 A8。

## 2. 保留原始 v0.2 檔，另增 v0.3

`b4/hypothesis/ff_behaviour_v0.2.json` 保留 byte-identical（原始 schema_version 0.2.1，既有 digest `1118bedf4831bac3806be4aa3d9b56630912a946156869807f2c26f6374e6ed2`），在 IMPORT／文件標為歷史來源；不修改其內容來補歷史標籤。

新增 `ff_behaviour_v0.3.json`，正式 loader 只轉到這一檔並更新 pinned digest。沿用草案列的資料改動：latch bit_zero= inverted、basis／meaning／valid_configuration、來源與 revision，formal_input 的現行檔名；behaviour flags、primitive selection、適用性、初始事件、可見性／DOMAIN 契約不變。保留 unknown enum、UNKNOWN_ALLOWED、拒絕機制與測試用途；更新過時註解，但不改驗證／解碼邏輯。

歷史 `v021_hole` helper 從**保留的原始 v0.2 檔**讀入，先核其固定 raw digest，再經 fixture_file／fixture 正式標記入口建立物件；不以 v0.3 改回一個 reading 就冒充完整的 0.2.1 文件。外部／歷史檔不會因此成為 formal；其 trace/result 必須明標 fixture。舊正式結果只存在其原來的 commit/evidence，絕不改寫。

mechanics fixture 保留且繼續明標；它用於機制驗收，不是正式 v0.3 的替代品。

## 3. 驗收校正：呼叫數與 latch 刺激順序

### F probe pass 與完整 run 分開計數

base + 21 probes 的成功觀測小計是 **22**，不是目前 engine 完整 run 的 port.calls。若 search budget=B，正常完整 F run 還有 B 次 search 與一次 holdout，總數是 **B+23**；budget=0 也仍會執行 holdout。

用預先固定的小 budget（例如 B=8）驗機制，沿用固定 seeds、不掃描：核對 base=1、probes=21、probe genomes 覆蓋全部 21 個單翻且各一次、mapping 在 probe 後凍結、search=B、holdout=1、總 calls=B+23、正式來源身分與 replay。不比較 arm 優劣。

所有原先以正式 0.2.1 觸發 DOMAIN 的測試（model、execution、engine、replay）要改用歷史 fixture，保留拒絕與終止驗收。不能只修版本常數後刪掉原測試；也不能把歷史 fixture 宣稱仍是正式來源。另立正式 v0.3 的來源與完成路徑驗收。

### 先在舊 clock settle，再切 clock

草案「clock=0、D=1 透明後，再 set(clock=1,D=0) 會 hold 1」不符合既有模型順序：新 D 先在舊 clock=0 的開啟反相 gate 下 settle，Q 已變成 0，之後才關 gate。

不改模型迎合該預期。手推 trace 要隔開 data change 與關 gate，例如在反相 gate、GE 有效、SR 未斷言下：

1. init：Q=INIT（G6 的原子讀出）。
2. clock=0、D=1：Q=1。
3. clock=1、D=1：以相同 D 關 gate，Q 保持 1。
4. clock=1、D=0：gate 關閉，Q 保持 1。
5. clock=0、D=0：gate 開啟，Q=0。

另測同時改 D／clock 的舊-clock-settle 行為、GE=0 的 hold 與 SR 優先；x5FF 仍為 None。bit-one 對照的初始化時序不能未經檢查就稱為完整鏡像。預期值由已採用的 vendor 規則及既有模型事件順序手推，不用模型輸出回填。

## 4. 檔案範圍與文件

可改草案列出的 B4 hypothesis、loader 路徑／digest／文字、model docstring、相關 B4 tests/helpers、IMPORT 及 `docs/b4_architecture.md`；證據新增至 `evidence/b4/unit_v03_<date>/`。必要的舊 DOMAIN fixture retarget 與正式來源斷言更新包括 execution/replay tests。

engine、execution、replay、cartographer、landscape、stats、RNG 的 production 邏輯不改；model 行為、SWAPS、正式 loader 的邊界與 source rehash 邏輯不改。若驗收顯示必須改這些邏輯，停下回報，不自行擴大。

IMPORT 的過期 used_by 與架構標題版本併入本單位修，不另開批准流程；active v0.3 與 historical v0.2 的角色須清楚。

§5.3／§13 要寫：v0.2.1 的 hole 及結果保留；v0.3 在新增的條件式模型讀法下解除這個定義性阻擋，F 的小型機制驗收可完成。**不宣布 gate-ready。** task 可達性、非平凡性、控制效果與 K1–K10 均未由本單位成立；2b-3 的門檻 commit 本身也不是 gate-readiness 判定。K7 不能把觀測 relation 數當 semantic decoded 數；新讀法相關 claim 需標其假設依賴。

## 5. 回歸與 mutants

跑 B4 局部全套及相關 hermetic mutants；不跑 B1/B2/B3 歷史全套或 proof。缺來源不 skip，patch 依 R7 清理。新 hypothesis 與 loader 的來源核對包含 D1′ report 的 digest，來源漂移測試只在副本執行。

草案 m1 要分開兩件事：hash 不符的拒絕測試，以及真正驗到 reading 的 semantic mutant。後者在 hermetic 副本內把 reading 改回 unknown 並同步副本的 formal digest，使測試因語意差異失敗，而非只死於過期 hash。

草案 m6 的「刪掉測試斷言」不算有效 production mutant；改成跳過／重複一筆 probe 等實作缺陷，讓獨立 calls／genomes／ledger 驗收抓到。其餘 pin、source rehash、gate inversion、swap、fixture 標記 mutants 保留，均須先有綠 baseline 且實際跑到相關測試。

十四筆既有 commit、所有 D1′／X-A／歷史 evidence 不動。完成後本地 commit 整批覆核；不採用修訂版結果回填舊紀錄。

2b-3、landscape 探索、gate、push／merge、採購、板上工作仍未授權。門檻與 τ 的單獨 commit 仍須在任何 landscape 探索之前。
