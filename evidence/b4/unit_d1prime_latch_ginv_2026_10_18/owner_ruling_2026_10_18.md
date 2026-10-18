# F/domain 與 X-A 範圍裁定（2026-10-18）

依據：`build/wip/b4_f_domain_xa_scope_draft_2026_10_18.md`。已只讀核對 `b4-prework@fe16c25`、既有 latch probe 文件與 recipe、當機 UNISIM LDCE 原文。main 仍 `d5bf815`，乾淨；九筆 B4 本地 commit 保留。本裁定只新增 ignored 文件，未實作、未執行 Vivado、未探索 landscape、未碰板。

## 1. 先校正草案的推論

每個**random-safe** child 從全零 parent 翻 k 位，出 domain 的組合比例確實是：

`C(19,k-1)/C(21,k)`，k=1..4 均勻時平均 `3/28`。

`(25/28)^8 = 152587890625/377801998336 ≈ 0.40388323` 需要八次獨立、均勻的 random-safe 抽樣。它是理想抽樣模型下 R 第一代的計算；不是目前固定 PRNG/seed 集合的已證頻率。O/X 在每個成功 specimen 後就可能建立 group，第一代尚未 selection 不代表 operator 仍然是 random-safe。因此不能把這個八次乘積套到 O/X，也不能從它推出「任何 arm 的完整 run 都會是少數」。刪除該外推；保留 F 必然在完整單翻 pass 中止的確定事實。

D1′ 不稱「唯一」路線；D3 的三個例子也沒有排除所有可能的 closed-book probe 設計。有限、不完整但保留 unknown 的盲 probe 設計不必然違反 closed-book；只是它不能單獨消除 R/O 的 domain 洞。本次不選這條設計路，也不授權改 probe。

## 2. 選 D1′，授權獨立、有限的 host probe 單位

授權在 `b4-prework` 的新 B4 probe 路徑內，建立並執行一對固定配方端點：四個 main LDCE 的 `IS_G_INVERTED=0` 與 `=1`。目標只用 mine site `SLICE_X2Y25`，anchors 沿用既有 recipe；不建 holdout、不讀 holdout bitstream。兩端點以同一版本工具／配方／其餘參數建置，不把歷史 bitstream 與新 recipe 未核對地拼成對照。

- 可新增 `b4/probes/` 下的 RTL、Tcl、host 解析與局部測試；需要借用舊 recipe 時保留唯讀原件，以複本及來源 digest 記入 B4 provenance/IMPORT。舊 `scripts/`、`vivado/`、`gate_runs/`、證書與歷史 evidence 不改。
- raw 輸出放新的 `build/` 路徑，交付放 `evidence/b4/` 的新單位目錄；既有輸出不覆寫。保存完整配方、命令、工具版本、stamp、exit codes、logs、DCP/bitstream/readback digest，以及成功或失敗的結果。版本化配方先記錄，再執行；不用建置結果選工具種子／site／版本。
- 逐一核對四個 cell 的 primitive、LOC/BEL、反相屬性、G/GE/CLR/D 連接及兩端點佔用／控制條件；不能只確認請求值或第一個 cell。取得不到 resolved 屬性即具名未解，不代填。
- 保存完整 raw diff 與所有 mover 分桶、方向、位址；預期是 latch 保持 1、該 site 的 CLKINV 由 1→0，其餘差異完整報告（含 ECC），不能只列預期位址而過濾其他 mover。
- 這次授權包含 host RTL/synthesis/place/route/bitstream 解析；不包含燒錄、JTAG/port、任何板上工作、正式 certificate 或 carrier 修改。它也不屬於 landscape 品質探索，不產生 K 值、門檻或 gate 結果。
- 不建得、屬性不符、CLKINV 不動或有其他未解 mover 都是本次 probe 的結果：原樣歸檔後停下覆核，不自動退到 D1/D2、不補語意、不擴 site 或追加條件追預期答案。

若得到預期對照，只能稱「此 mine-site 配方的 host build/readback/bitstream 對應證據」。它不是新 certificate、不是矽上時序觀測，也不能單獨證明任意 latch 組合安全或整個 21 位址 domain 已被驗證。

## 3. v0.3 另立單位，尚未授權

D1′ 完成後先覆核來源強度，再裁模型修訂範圍。即使端點如預期，UNISIM 行為及位元到 primitive 的推廣仍須分開寫，silicon status 維持 unverified。不得在本次 probe 內改正式 hypothesis、`HYPOTHESIS_SHA256`、domain 或 F 事實測試；舊 0.2.1 的結果保留。

## 4. 授權 X-A 為後續獨立純功能單位

採草案 §3 的地址重貼標方向；lane permutation 留作 cartographer 的 symmetry 測試，不增第五個 arm。授權範圍包含 B4 implementation/tests/schema/IMPORT、`docs/b4_architecture.md` 的相關契約及 `evidence/b4/unit_xa_<date>/`，每個單位獨立 commit。正式 hypothesis/mapping/model 行為及舊 pinned 輸入不改。

補充必須落實的條件：

1. π 使用獨立的 control RNG；不消耗 operator RNG，並在 base 觀測前固定。重放從 control seed 推導並核對記錄的 π。先驗 derangement 演算法中排除有固定點的 Fisher–Yates attempts 屬生成程序；禁止的是看過 map、partition 或結果後再挑 seed/π。規則、內部嘗試及最終 π 均可稽核。
2. ledger 保存真實 genome；cartographer 的 π(genome) 可重建。逐 specimen 的 shadow 核對覆蓋設計稿所列全部狀態。殘餘結構只事後報告，不參與 operator、重抽或樣本選擇；明定 groups_moved 的計數口徑。
3. 同構失敗是 **control failure**，不是 DOMAIN、科學 KILL 或觀測前拒絕。明定發生的提交點並保存已成功取得的觀測／specimen及失敗證據，停止後不抽樣、不評下一個候選、不 selection。不得為套用目前拒絕 schema 丟掉那筆成功觀測；engine 與 replay 的 stage、counts、狀態及事件必須一致。
4. 以手算 partition-changing fixture 與 partition-preserving derangement 反例驗收；測試不能要求每個 π 都破壞分組。涵蓋 base／中途終止、control failure、完整重放及有意義 mutants。只驗機制，不量 arm 優勢、不做 seed 掃描或 landscape 探索。

## 5. 文件、順序與後續閘門

先做 D1′ host probe，歸檔並覆核；再按已授權範圍做 X-A 獨立單位，本輪不並行。v0.3 另議。

X-A 的 §8/§9 修訂併入 X-A commit，限轉換／同構／殘餘結構與非保證句，不填門檻或 τ。domain/F 的正式修訂留給模型單位；在此之前只保持「未解、非 gate-ready」，不以刪除 F 判準或選 survivors 取代原研究。

2b-3、landscape 探索、正式 gate、push、merge、採購及板上工作仍未授權。門檻／τ／seed anchor 的單獨 commit 仍須在任何 landscape 探索之前。main 及所有歷史 B1/B2/B3 證據保持原狀。
