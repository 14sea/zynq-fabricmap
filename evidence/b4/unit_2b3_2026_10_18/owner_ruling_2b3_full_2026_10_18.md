# B4 2b-3 範圍與數值裁定（2026-10-18）

依據：b4_2b3_thresholds_scope_draft_2026_10_18.md；只讀核對 b2a958c、12eaa72/c0689f8 的相關 B4 程式、B2/B3 統計與 seed 原始實作。本次不跑模型、不抽 seed、不計 gate 結果，不改 tracked 檔案。

## 0. P3 與授權界線

b2a958c **PASS**：來源表已改為正式 v0.3 的四個 machine source kinds，歷史 v0.2 分開；full ruling 在新增的兩行導言之後與原 ignored 裁定全文相同，摘錄已具名。純文件不需重跑測試。v0.3 工程驗收維持結案。

**授權按本裁定完成 2b-3 一筆本地文件 commit，交覆核；不必再送同範圍草案。** 可改 docs/b4_architecture.md 的方法與門檻、相關互相矛盾的文字及版本/§13，新增 evidence/b4/unit_2b3_<date>/ 的理由、完整裁定、變更核對。b4/、hypothesis、所有 production/test code、既有 evidence 不改。git diff --check 與引用核對即可，不跑測試、run 或正式 proof。

這是事前固定的工程研究判準，不聲稱數值有經驗保證、統計校準或矽上效力；50% 等選擇失敗即如實報告。不是 gate-ready。任何探索後修訂須保留舊版、理由、舊結果，另行授權並完整重跑；新門檻不得回填判定舊運行。

## 1. 數值、grid 與選取規則

正式 gate S **固定 200**，不因結果增加樣本。grid = [8,16,24,32,48,64,96,128,192,256]，B_max=256。以下每項均為事前固定的政策選擇。

- K1：Omega 的 best-so-far 第95百分位 <64；median(best_R)>median(base_r)。是兩個 median 比較，不是 median(best_R-base)>0。percentile 用 B2 的線性插值公式。
- K2：population variance(Delta1)>0；至少同一個 grid B 同時有正、負 Delta1；在 B* 用 N(B*)，X-R 的單尾 sign-test bootstrap 非拒絕率 >=0.90。1000 次，alpha=.05，Python random.Random(7)，拒絕條件 p<=.05；ties 不進有效 sign-test n，但原配對仍保留且 bootstrap 抽原始含 ties 的配對。X 殘餘結構全數回報，不選取。
- K3：mean(F-R)>0 且 mean(D-R)<=.10*mean(F-R)；mean(O-R)>0 且 mean(X-R)<=.10*mean(O-R)；D、X 單尾 sign test p>.05。負分子可通過，不取絕對值；分母為零或負值不可被當成比例成立。
- K4：median(Omega)<=.90*64=57.6；mean(Omega-R)>0 且 mean(F-R)>=.50*mean(Omega-R)。50% 是本次事前判準，不是已知可達效果。Omega 僅是 privileged grouping reference，並非已證明的搜尋全域上界或最優解。
- K5：paired Cohen d(Delta1)>=.5；alpha .05、bootstrap power>=.90、1000 次、Python random.Random(1+N)；N 按每個整數從8到S完整升序掃描，不二分、不跳過；cap=4000 **search evaluations**。
- K6：S=200、N>=8，完整排除與固定 seeds。S 是全部原定 seeds，不是完成者數目。
- K7：依第2節修正：0個可重算的 ledger/relation 不一致；O 在 B* 的 median 非 unknown 位址數>=11。非 unknown 不等於有可用分組，更不等於語意已解碼。
- K8：所有實際運行（R/F/O/X/D/Omega/A0）的 replay 無 finding，q grid 重算 fitness 一致，X shadow 同構與來源/fixture 邊界成立。工具契約破裂按第4節 invalid，不包裝成正常 landscape FAIL。
- K9：依第3節的固定 context panel，至少90%的全部 seeds 在七個語意上各有一個正向對照位址；每個語意的 per-seed context coverage median>=.50。非七個語意覆蓋率再取平均。
- K10：tau=2 個 fitness score units（本 task 權重全1，等於2個得分 cells，2/64）。**interacting 為 max|I|>2，恰等於2進 nonzero_below_threshold 類**。interacting seeds / 全S >=.50；四類全報。第5節固定兩個背景、210對與模型可比性的範圍。

Delta1=O-R 是 primary search accounting。Delta2=O-end_to_end_F 與原始 F-R 的均值、sign test 等只報告、不另設支持宣稱的顯著門檻；F-R 仍被上述 K3/K4 當比較參考，不能一邊說完全無門檻，一邊隱藏其正值/相對大小條件。

B* 僅在 K1 成立且 N(B)存在的 B 中，取 N(B)*3*B 最小，平手取小B。不能為讓其他列通過而改選。N 無解的 B 不合格；全部無解則 B*不存在、budget rule FAIL；後續依賴 B*/N 的列標 not assessable，整個 gate 不可 PASS，不虛造 B*或N。

cap 4000 是計畫主實驗的三臂搜尋評估數 N*3*B*，**不是單一 board session、時間、總觀測或總記錄上界**。F另有21 probes/對；R/O 完整呼叫 B+2，F B+23。每對主臂基本觀測合計3B+27，尚不含未設計的板端額外baseline/audit/傳輸與重試。B4沒有實測速率，session split 仍由2c/後續 qualification 決定，不能借 B3 rate 當實機保證。草案 16*3*83=3984 且83不在grid，刪除此例或改用真grid值，例如16*3*64=3072。

## 2. K7、D、來源與 accounting 的必要修正

### K7 不拿證書 partition 冒充閉書觀測的正確答案

oracle_view 依 certificate 的 element/slice 分組；ObservationCarto.view 依實測影響的 elements 分組，且把所有 multi-element 地址放同一組。slice-wide bit 在某個刺激下可能只影響一個元件，與該元件位址同組；這不表示 cartographer 有bug。模型也沒有保證兩種 partition 相等。

刪掉「任何 learned group 跨 Omega group 即 anomaly/缺陷」的驗收。可另報 partition mismatch 作診斷，無門檻，不影響 run或選 seed。K7 的零 anomaly 改指：從該 arm 的真 ledger 單翻配對重算 affected_cells/presence、pair counts、contexts、evidence refs、版本與最終/該B map，和已記錄的 relation 不一致；不是對 semantic truth 的宣稱。

主K7覆蓋量取 **O 的 B* search-prefix**，不含B*之後/holdout的資訊；每個 seed 的21位址按 unknown/effect_seen/no_effect_seen/context_dependent 四類分開報，總和21，非unknown含後三類。F的probe後凍結map、其餘控制相應資料另報，不用F掃完21位址代替O的>=11判準。B*快照可從真ledger前綴重建，不另跑候選。X自身關係與其shadow核對在X-A契約下判，不要求錯貼標map符合真certificate partition。

D 明定為**同seed F由probes學得並凍結的 MapView**經 shuffled_view 的一次置換（保留父來源）；不是 shuffled oracle。只送該view到 F-with-given-view 搜尋，不重學、不看之後結果挑圖。D為host控制，可共享F probe產物，但成本另列21 probes/取得一次的邏輯成本；其search比較仍按B對齊。A0用address_only_view；Omega用oracle_view，始終標privileged，均不送入主R/F/O/X。

控制seed在觀測前固定，UTF-8十進位無空白：
- X control seed = int.from_bytes(SHA256('b4-x-control-1|<landscape_seed>|<operator_seed>')[:4], 'big')。
- D shuffle seed = int.from_bytes(SHA256('b4-d-control-1|<landscape_seed>|<operator_seed>')[:4], 'big')。

使用各自Rng，不消耗task或operator stream；數值偶然碰撞照記，不重抽。X保留derangement算法本身的所有attempt；D沿用普通shuffle，可保留partition，記錄實際置換/殘餘結構，絕不為消除殘餘結構而重抽。

F end-to-end secondary按既定21次probe成本平移。T<=21時取已觀測base分數（搜尋尚未開始，明標mapping-in-progress），T>21取F第T-21次search的best-so-far。不是把probe候選當search champion，也不是對故障終止前綴補值。holdout分數不混入訓練曲線。

## 3. K9：固定的 host-only positive-control context panel

只寫90%/50%而未指定contexts會留下事後選取自由度。本單位把以下方法一併寫成文字，不執行：

1. 每個seed用task-v0.1原本的search stimulus，不修改/挑選刺激，不看champion，不用holdout。讀整份公開q_after trace，**含init readout**；K9是觀測可辨識度，不是fitness mask覆蓋。INIT差異靠原子init抽象，仍conditional on A8。
2. 固定panel背景：五個slice mode bits（ce_mode/sr_mode/sr_kind/storage_kind/clock_mode）的全部32組合；16個per-element INIT/SRVAL位元背景各取全0及全1，得到64個固定背景。這個panel由host mapping建立，只供audit；不交給cartographer/engine作prior。
3. 對每個真位址a和每個背景，將a分別強制0/1，其餘bit固定；相同兩端點配對去重，按genome數值排序，保留兩端完整配置與trace引用。這只涵蓋此有限panel，不宣稱遍歷其餘19自由位元的全部組合。
4. per-element semantic只比較所屬元件q_after；slice-wide semantic可比較任何適用元件。x5FF的INIT/SRVAL在latch下不適用，sr_kind在latch下不適用，具名列出並排除相應分母。storage_kind本身的兩端點可含presence改變；其他關係要有兩端皆適用的可比較讀出。其他值差異(0/1)、storage_kind的None/present差異均須明列位置，不從decode直接聲稱trace有分離。
5. covered(address, context)=該對trace在上述讀出範圍至少一處可區分。每seed/semantic coverage = covered適用配對數 / 全部適用配對數（每對固定等權）；另報每位址的適用/覆蓋配對數及比例、沒有任何覆蓋的位址/contexts。分母為0要not assessable，不記100%。每semantic的正向對照=至少一個適用地址-context配對可區分。七者全有者才計入90%的seed數。

此panel是事前工程診斷設計，與2c的板端刺激及安全合法性不是同一個契約。未覆蓋不得靠增加某次有利context回填；変更panel需新版本+理由+完整重報。

## 4. 不完整 run、失敗與無解

正式gate每一個預定arm/seed都要跑完B_max及既有holdout，completed必須為bool True、search_completed True、search evals與len(best_trace)均恰為B_max；拒絕/control_failure欄位為None。曲線各B為該完整run的實測prefix。全部完成是gate可作PASS判定的前提。

任何正式truth/v0.3 DOMAIN、other refusal、control failure、來源或replay違反契約都 **invalid**，依停止規則保留當次run與已完成前綴，停批回報。不要使用「完成配對子集」算出可接受的PASS。所有原定seeds仍列在清單中，未開始/中止也具名，不換seed、不補值、不重抽。

資源/時限/外部中止亦為incomplete evaluation，不能用倖存者判PASS；是否續跑原定未執行項另議。診斷可列完成配對數與實測值，但必須明標非正式gate判定；全S分母不變。

**完整有效運行但required_pairs無解，是正常的discriminability結果，不是工具缺陷，也不是「因不完整run」**。第1節的N/B*規則適用。其他門檻在有效完整資料上不成立是FAIL，不自動調整門檻。

## 5. K10 與 seeds

K10：genome0=0；genome1=Rng((landscape_seed ^ 0x4C0A4E55) & 0xffffffff).uniform(1<<21)，從該新Rng的首個uniform呼叫取得，與task/operator/control RNG獨立。只取一次；即使兩背景相同也保留，不挑第三個。兩背景各測全部210個unordered地址對，記背景、四角配置與分數、I，按既有four_corner固定其餘bit。per-seed max取兩背景所有可比對的值。

這是 **hypothesis/model-domain comparable**，不是實機legal/safe。v0.3的域內性不證明bitstream可建、可寫或組合安全；架構K10原來的legal字眼在2b的host量測要改清楚。若2c要求composition legality，是另一個凍結條件，不能拿此結果替代。應報四類、可比/不可比數；意外DOMAIN按invalid規則，不當作一般not-assessable吞掉。

anchor採 **正式hypothesis完整SHA當anchor值**，labels另傳：
- gate master=int.from_bytes(SHA256(UTF8('b4-gate-1|59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8'))[:4], 'big')。
- exploration相同公式、label改b4-sim-1。不要把已拼好label的整串再當anchor傳入，造成雙label。

本單位只固定公式，不生成任何seed值或讀候選結果。pair_seeds按B2算法的複本規格，landscape/operator均去重排除；既有archived sources逐檔列路徑、欄位/schema與digest，不是籠統寫directory含子目錄。B4所有探索/失敗/中止/作廢seed亦入排除集；目前不存在的evidence/b4/sim必須明列「尚未建立」，與已應存在而缺失的歷史seed來源分開，後者拒絕，不能靜默略過。

加上已曝光的單一正式觀測seed7，以及本次v0.3固定機制用的landscape/operator seeds（含11/12/13，依測試實參/既有紀錄盤點），其餘B4已有明確seed紀錄同樣列入來源清單。這是保守排除曝光值，不是據此估計任何分布。記錄草案的一次base觀測，不聲稱從未執行過模型。

探索set在探索前一次產生並歸檔，不看結果重抽。gate set只能在所有探索/失敗set已歸檔後，按固定master與完整排除集推導一次；凍結輸入清單、digest與最終seeds，run開始後不得因結果改排除集以重抽。anchor與排除集合都影響set，固定anchor本身不是選擇偏誤保證。換hypothesis/anchor不能自動換seed重試；必須另裁並保留舊set與結果。

## 6. 下一步與未授權項

**本次不授權S=32探索。** 2b-3文件先提交覆核，之後先提host-only探索工具/執行範圍：控制D/X、K7快照/K9固定panel、replay與seed/archive/時限的實作驗收，及dirty/no-clobber/終止規則。現有純功能不等於已有可稽核的exploration harness；不能為探索臨時自由補這些方法。無須另做2b-3的同範圍草案。

後續如授權S=32，只是探索資料，不能通過S=200的正式gate；所有結果與原先門檻並列保留，門檻不在運行中改。K1/K10的通過也不證明公開target可達；task reachability、baseline非最佳與composition/safety仍須各自的證據/限制，不能憑gate數字宣布硬體就緒。

16筆本地commit保留。push/merge、2b-4正式gate工具與運行、2c/2d、採購及板上工作仍未授權。main保持d5bf815乾淨。
