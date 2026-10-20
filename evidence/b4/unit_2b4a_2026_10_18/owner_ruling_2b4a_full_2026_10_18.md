# B4 2b-3 覆核與 2b-4a exploration harness 範圍裁定（2026-10-18）

依據：b4-prework@740d92c 的18筆本地commit；b4_2b4a_exploration_harness_scope_draft_2026_10_18.md；前次2b-3六節裁定。只讀核對現有engine/carto/replay、B2統計/seeds與文件，沒有跑測試、模型、探索，沒有生成正式seed set或K結果。

## 1. 3564236 + 740d92c 的結論

**PASS，2b-3 工程文件驗收結案。** 兩筆保留，不reset/rebase。第二筆把語意釘清的目的接受，一筆交付規劃之外的純文件follow-up不需拆掉。獨立重算§9.2的38個來源digest，全部相等；兩筆均只改architecture與本單位evidence；diff --check通過。覆核清單在build/wip/owner_review_2b3_740d92c_2026_10_18/checks.json。

接受K9的事前嚴格政策：任一seed對某語意不可評，就將該語意的全S median標not assessable，K9(b)不成立；另報不可評seed數。**這是本輪明確接受的政策選擇，不能只因沒有數字token變化就稱它不改判定規則。** 若既有panel正常運作，適用分母不應依seed變動；觀測沒有分離是covered=0，不是not applicable或not assessable。

一項P3文字修正授權併入下個本地文件/工具commit，不需重跑舊測試：K2/K3的sign-test H1須寫 **P(Delta>0 | Delta!=0)>1/2**；ties已排除於有效n。全ties時沿用B2 p=1，沒有正反證據，不把條件機率硬填0。原文無條件P(Delta>0)>1/2與實作不等價。bootstrap母體仍含全S的ties，方向、alpha、比較符號與數值門檻不變。

尚非gate-ready；不改threshold/grid/tau/anchor，不重判歷史結果。

## 2. 授權與八題逐項決定

**授權實作修正版2b-4a工具與局部機制驗收，不必再送同範圍草案。** 限新B4 host模組、schema/tests、IMPORT、architecture相應註記與新單位evidence。engine/carto/replay/execution/landscape/stats/ff model/hypothesis/mapping原模組邏輯不改；若非改不可，停下報告。可加必要的B4 package/helper檔，但不擴到舊pinned面。

1. **報表**：接受數值旁列事前threshold與固定exploration standing，沒有正式gate verdict/criteria-pass欄位；complete/invalid/incomplete是執行狀態。禁止的是冒充gate判決，不是禁止保存原始例外/裁定引用裡的PASS/FAIL字串。candidate B*/N是S=<actual>探索資料的估計，不可轉成正式S=200的N或預註冊結論。無eligible B時仍可batch complete，candidate B*/N為null並列原因；不能因無power而invalid。
2. **統計複本現在做**：sign_test_p/bootstrap_reject_rate/required_pairs/percentile/cohen_d，及其所需mean/median等小型依賴，從B2逐函式複製到B4；stdlib依賴math/statistics/random，runtime不import舊模組。IMPORT記完整來源sha與採用範圍/函式digest。以手算ties/全ties/方向/離散bootstrap/無N、邊界percentile等測試，必要時測試中唯讀比對舊函式。不得偷偷換PRNG或power掃描。報表JSON不輸出NaN/Infinity字面值；合法的d=+infinity要顯式special標記，數值欄null，不能當作0或無故invalid。
3. **K7採既有ledger重建，不改RunResult**。逐筆核map version before/after及commitment，重建完整relations供存檔，最後核result的終態。O的每個grid prefix恰B+1筆。F僅base+21 probes學圖，search/holdout不再ingest；不得把整條F ledger餵新carto再冒充凍結map。X按pi重貼標、shadow用真genome、逐specimen完整同構。R無learned map，D/Omega/A0用given view，無relations的量標not applicable，不虛造四態。
4. **測試seed規則接受**：只用已曝光固定值做小型mechanics tests；需新值同commit登記。可計算假digest的手算master或人工fixture的pair stream；不得生成/觀察正式b4-sim-1或b4-gate-1 set來做測試或挑值。patch依R7用with/addCleanup清理；CLI沒有fixture/allow-dirty/test-mode bypass。測試內依賴替換須局限hermetic副本/行程，evidence明標mechanics，不能當正式探索成果。
5. **前置條件接受**：乾淨樹無開關、formal v0.3 + truth +來源核對、out已存在即拒、deadline必填正整數（非bool）、label白名單。另加第3節的排除、寫入、起訖provenance與deadline校正。
6. **單工**：不做workers>1；固定pair與arm順序。避免首次停止後其他worker還在產生觀測；將來多工另裁。不能聲稱把最後rows排序就等價於逐run fail-closed。
7. **測試不等於探索**：已曝光fixture seeds的小型單元/整合測試可跑模型，不比較arm優勢、不量K分布、不掃seed。該授權不含S=32探索。formal輸入/fixture邊界仍須被測到，不能全靠mock略過。
8. **三筆implementation commit，最後整批覆核**：A seeds/controls/snapshot（可含P3文件修正），B k9/k10/stats，C harness/schema整合。每筆相應IMPORT與局部測試；最終B4局部全套、必要hermetic mutants與完整evidence。不需每筆再問同一範圍，不push/merge，不跑B1/B2/B3全套或歷史proof。

## 3. 實作前必須補入的契約

### 3.1 排除集會隨歸檔增加，不只固定38筆

歷史38檔逐digest/shape驗證，不可只抽seed字眼附近所有整數（count、version、時間戳不等於seed）；field_spec必須落到確定schema欄位，型別/range嚴格且不接受bool，缺欄/錯schema具名拒絕。

**load_exclusion_set必須納入evidence/b4/sim/所有已歸檔seeds.json**（complete/invalid/incomplete/失敗/中止/作廢都算），不只是38固定檔+B4_EXPOSED_VALUES。目錄最初不存在可接受；一旦存在，不得把損壞/缺seed記錄的舊run當成不存在而略過。按路徑排序讀取seed registry，核schema、全部planned pairs及來源digest，計入單一pooled集合；保留來源path/sha/count與實際values。重複集合聯集去重，不能只排已完成pair。

目前新out不參與自己的exclusion；**先完整snapshot既有來源，再exclusive建立新out，seeds/manifest原子寫完之後才觀測**。新輸出目錄及每份最終檔以獨佔方式建立，抵抗同名race；不覆寫其他run。若初始化在第一次觀測之前失敗，也保留可識別的初始化失敗紀錄，不能把可能已觀測的目錄靜默略過。續跑/新label/新set另裁，本工具不自動resume或increment label。

### 3.2 不能等pair完成才第一次落盤

每個arm的原始RunResult在返回後**立即原子存檔，且先於replay/重算**；再保存audit findings。新檔逐次獨佔寫入，可用pair子目錄下arm_R.result.json等，pair raw總索引最後一次產生。F/D的view與置換、K7快照、K9/K10階段各自有checkpoint。若後續audit崩潰，已返回的run不會只留在RAM。

invalid保存觸發run/完整已得結果、原始例外和partial diagnostics、STOPPED及全planned清單，未開始標not_started。非DOMAIN例外不得因捕捉不全而直接丟失前面六個arm。Unexpected exception與deadline/SIGINT等原因分開；KeyboardInterrupt等外部中止是incomplete，不把它偽造為DomainRefusal。正跑黑盒engine時若沒有返回完整RunResult，明標in_flight/interrupted/result_unavailable，保留已落盤資訊，不捏造完整run或宣稱已保留未取得的內部prefix。

STOPPED與執行狀態報表規格一致：所有終止批都有typed sim_report.json（僅status/identity/已存檔索引/缺失原因），**沒有pooled numeric summary**；complete才寫完整summary。不得一處說不寫report、一處又要求report有status而使實作自選。

### 3.3 deadline是monotonic的soft deadline，涵蓋整批

採time.monotonic計時；UTC只作時間戳。檢查至少在每個arm前後、replay前後、每個snapshot工作單位、K9每個新trace/比較單位、K10每次新evaluation/四角單位、以及統計每個budget/N/有界bootstrap工作單位前後。time從開啟本次harness前置處理起算，不只搜尋階段。

**不改engine/replay而保留整個arm或一次replay為不可中斷工作單位**，因此deadline只是soft：可能超過一個已開始工作單位的時間，不是hard wall-time保證。截止後不再啟動新工作，當前已返回結果先落盤，寫incomplete與STOPPED。K9/K10/stats不得整段免檢查；wrapper分批保留進度，不更改原統計公式或random stream（分塊與未分塊結果必須相同）。不能因B+23觀測有界就宣稱時間有界，cartographer/replay也有計算成本。

實際S=32的deadline秒數本次不定、不執行，留運行授權時指定。測試用fake monotonic可驗deadline在K9/K10/統計階段也停止，不靠長sleep。

### 3.4 起訖provenance與輸出範圍

第一次觀測前把HEAD、architecture bytes sha、IMPORT bytes sha、threshold常數、task/engine/carto/hypothesis/mapping/外部來源與工具/schema清單digest、seed來源及最終seeds全部落盤。不得只記b4/host/*.py而漏hypothesis/證書/architecture/PRNG等實際輸入；檔案digest之外保留公式與版本。

結束與checkpoint處核HEAD/受用輸入仍同snapshot；最終核完整輸入與非輸出工作樹狀態。當次新out造成的預期untracked檔可識別排除，不能因此跳過所有dirty檢查；其他輸入或tree漂移=>invalid，保留結果，不發complete summary。manifest/工具常數與事前architecture門檻須由靜態測試逐欄一致性核對，或另設明確機器表並pin對應關係，不能只靠人眼說兩份大概相同；本次不新增改變門檻值的來源。

--out限此單位的全新exploration namespace（evidence/b4/sim/下、與label相符）；不可指向b4/、manifests/、舊evidence等受保護路徑，不跟隨輸出路徑symlink寫出允許root。測試用hermetic repo/root，不給production開逃逸開關。預檢拒絕不寫輸出；成功取得新目錄後的失敗以紀錄保留。

## 4. 各量的可稽核資料與測試要求

### 4.1 F/D、K7

f_frozen_view只接受已完成、已replay核對、task/來源相符的真正learned F結果（given_view=None、非privileged、正式來源），重建base+21單翻probes的carto，逐筆核ledger及最後frozen_view/map_version/map_commitment。返回重建的真MapView，不只相信任意result自稱origin=learned。D保留父commitment/provenance；實際置換由d seed及shuffled_view相同算法重建並與結果核對，可能identity/partition-preserving，照報不重抽。兩個control seed均須32-bit int非bool，不影響operator RNG。

K7的O prefix定義不變。以手工q-grid ledger做獨立預期snapshot/versions/counts，並以非最後一筆篡改、F解凍、X真genome未重貼標等有效mutants驗證；不要只有對同一函式呼叫兩次的測試。

### 4.2 K9/K10不能只保存摘要或score

K9每個固定pair要有semantic/address/背景或去重來源、兩端genome、適用/不適用理由、對應trace引用、指定讀出範圍及差異位置。每個唯一觀測保存stimulus/config/provenance/digest與完整q_after grid，供離線從原始讀出重算coverage，而不是只存covered=True。host-only applicability可讀mapping/hypothesis，不能交回engine/選候選。

K9 model applicability由配置決定，不由觀測剛好不同與否決定；不要把兩端trace相同踢出分母。對非storage_kind，若兩端有適用讀出，僅比較兩端皆適用的元件；storage_kind的presence改變按既定規則比較。

可用配置+stimulus+正式來源身分作key的**單seed獨立memo**，保存每筆cache引用與真正ObservationPort calls。memo只改次數，不改比較panel/分母；不跨seed/來源偷用trace。K9與K10觀測不入任何搜尋ledger，邏輯比較次數/角數與實際calls分開。

不跑模型也可手算K9測試的數目：64背景；每個global位址的forced pair去重後32對，per-element位址64對；排除latch x5FF及latch sr_kind後，ff_init與ff_srval各384適用對，ce_mode/sr_mode/storage_kind/clock_mode各32，sr_kind16。用人工trace的separation/未分離/None與presence例子驗分母及分子，且至少一個固定曝光seed的formal-model正向串接。若發現此手算與規則有矛盾，停下報明哪個context，不以運行結果選分母。

K10保存每個角的genome、score與可還原q-grid引用，按task mask重算score/I，不只信summary。保留兩個背景即使重合，unique cache hits只改真正calls。**既有four_corner會捕捉DomainRefusal並回comparable=False**，driver不能假設它會自動上拋；必須檢查回傳結果並立即升級為invalid，保留已得角，不改b4_stats本體也能做到。DOMAIN注入應在真four_corner內測到這條路，不只mock driver本身raise。

### 4.3 完成、報表與資源

harness不能只看refusal欄位空就算完成：typed completed/search_completed為True，evals/len(best_trace)/search cost恰256，觀測cost總和/port calls/ledger數與各臂規則一致，holdout恰1且來源正式；然後replay與重算全通過。D/Omega/A0的內部arm是F，外部control角色另存並核given_view，不改RunResult的arm冒充新engine arm。

schema須覆蓋seeds/manifest/raw/checkpoints/STOPPED及status report，或提供同等嚴格的逐檔typed validators與測試。jsonallow_nan=False；非finite合法統計量按第2節顯式表示。raw與summary有size/sha清單、相對路徑及互相引用核對；離線重讀能重算曲線、K7/K9/K10與摘要，不依賴記憶體物件或變動中的temp檔。不宣稱ledger replay證明模型或矽的authenticity。

七臂物理搜尋呼叫數在B=256時是7*(256+2)+21=1827，另加K9/K10各自calls。這只是次數算術，不是時限證據。保留time與calls，但mechanics測試不輸出arm優劣分布，不為找能通過的task掃seed。

hermetic mutants須綠baseline、Ran N>0且實際失敗原因對應所破壞契約；以setUp的無關pin refusal死掉不算該semantic mutant成功。額外覆蓋：漏讀既有B4 seed檔、寫pair前丟失已完成arm、F search誤更新map、K9觀測相同被排分母、four_corner吞DOMAIN、deadline漏K9/K10/stats、截止後仍啟動下一工作、input中途漂移、source或控制fixture混入formal CLI、NaN/Infinity不合規JSON。只寫必要的機制測試，不要求每個微小序列化分支各造mutant。

## 5. 交付後的閘門

A/B/C最後在乾淨本地提交樹上跑B4局部全套與必要mutants，evidence記exact HEAD/命令/結果/fixture標記/IMPORT核對，交整批覆核。無需每筆commit逐次問同一scope；不改先前結果與門檻。

**S=32 b4-sim-1、正式gate工具/運行、2c/2d、全量proof、push/merge、採購及板上工作仍未授權。** 本輪工具PASS後，再指定探索S、deadline、輸入HEAD/architecture/工具digest、seed封存/輸出目錄與停止規則，才啟動正式探索。
