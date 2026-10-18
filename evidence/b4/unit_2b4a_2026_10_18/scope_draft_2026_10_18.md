# B4 前置：host-only 探索工具（exploration harness）與執行範圍的只讀範圍草案（2026-10-18）

**定位：只讀草案，等 owner 裁定。** 依 owner 對 2b-3 的裁定 §6：「2b-3 文件先提交覆核，之後先提 host-only 探索工具／執行範圍：控制 D／X、K7 快照／K9 固定 panel、replay 與 seed／archive／時限的實作驗收，及 dirty／no-clobber／終止規則。現有純功能不等於已有可稽核的 exploration harness；不能為探索臨時自由補這些方法。」

本稿只提「工具要做什麼、怎麼驗收、探索一旦授權會跑什麼」。**本稿不授權任何事：** 不寫程式、不跑模型、不抽 seed、不算任何 K 值；S = 32 探索、正式 gate、2b-4、2c、2d、push／merge、板上工作全部維持未授權。文中每個數字都來自架構 v0.1.13a §9 或程式碼現況，不是新門檻。

名詞固定：**「run」** = `b4_engine.run` 的一次呼叫（一個 arm、一個 pair、budget 256，含 holdout）；**「pair」** = 一組 `(landscape_seed, operator_seed)`；**「arm」** = R／F／O／X 四個主臂加 D／Ω／A0 三個控制，共七個；**「觀測」** = 對 `ObservationPort.observe` 的一次成功呼叫（host 模型，不是板）；**「批」（batch）** = 一次 harness 執行所涵蓋的全部 pair。

## 1. 盤點：已有的純函式、缺的 harness

| 需求 | 已有（分支 `b4-prework` tip） | 缺 |
|---|---|---|
| 七個 arm 的 run | `b4_engine.run(arm, task, port, operator_seed, budget, view=None, control_seed=None)`：R／F／O 直接；X 需 `control_seed`；D／Ω／A0 = `run("F", …, view=<MapView>)`。`RunResult` 已有 `completed`／`search_completed`／`evals`／`best_trace`／`ledger`（每筆含 `map_version_before/after`、`map_commitment_after`、`q_grid`、`fitness`）／`cost`／`frozen_view`／`map_version_final`／`map_commitment_final`／`x_*`／`control_failure`／`terminal`／`other_refusal`／`provenance` | 把七個 arm 按固定順序跑完一個 pair、逐 arm 歸檔、逐 arm replay 的 orchestration |
| D 的輸入 | `b4_carto.shuffled_view(view, seed)`；F run 後 `RunResult.frozen_view`（groups）、`map_version_final`、`map_commitment_final` | 從 F 的 `RunResult` 重建 `MapView`（origin `learned`、provenance `("learned",)`、privileged False），並用 F 的 ledger 前綴（base＋21 probes）重新 ingest 核對 commitment 相等後才交給 `shuffled_view` |
| X／D 控制 seed | 公式已寫在 §8（sha256 前 4 bytes） | 實作與測試 |
| Ω／A0 | `oracle_view(mapping)`／`address_only_view(addresses)` | 無；只需歸檔 `given_view` |
| replay | `b4_replay.replay(result, task)`（重執行＋全欄位 diff） | harness 內每個 run 結束立即 replay 並歸檔 findings；有 finding 即觸發停止規則 |
| K7 (a)(b) | ledger 每筆有 `map_commitment_after`；`ObservationCarto.ingest/view/commitment` | 「前綴快照」：對 O 的 ledger 第 1 到 B＋1 筆（base 到第 B 次 search）重新 ingest，逐筆核對 version／commitment，取四態計數（和為 21）；每個 grid B 各一份 |
| K9 固定比較集 | §9.3 文字；`Fabric(mapping, hypothesis)` 可對任意 configuration＋stimulus 給 trace | panel 建構、forced pairs、適用性規則、coverage 計算與逐位址報表 |
| K10 | `b4_stats.four_corner/classify/seed_max/summarise`；`Rng.uniform` | 兩個固定背景、210 對、τ = 2 的 driver 與歸檔 |
| 統計 | `host/b2_gate.sign_test_p/bootstrap_reject_rate/required_pairs/percentile/cohen_d`（在 pinned 邊界外） | 複本進 `b4/` namespace＋digest 記入 `b4/IMPORT.json`（§9 K5 要求「by copy」）；複製的時點見 §6 問題 2 |
| seed 推導 | §9.2 公式與 38 個來源檔＋digest；`host/b2_search.pair_seeds` | B4 的複本：anchor、排除集載入（逐檔重驗 digest）、pooled 排除、歸檔 |
| 歸檔／報表 | B3 的 `sim_report.json`／`raw_F*.json` 形式可循 | `b4_sim_report` schema、raw 檔、`seeds.json`、`STOPPED.json` |
| dirty／no-clobber／時限／停止 | B3 只記錄 `worktree_dirty_at_start` | 全部缺；本稿 §3 定義 |

## 2. 交付物（一個單位，建議代號 2b-4a；owner 可拆）

全部在 `b4/host/`，測試在 `b4/tests/`，皆為 host-only：

1. **`b4_seeds.py`**
   - `master_seed(label, hypothesis_sha256) -> int`：`int.from_bytes(sha256(utf8(label + '|' + hypothesis_sha256)).digest()[:4], 'big')`。label 與 digest 分開傳；拒絕已含 `|` 的 label（防止雙 label）。
   - `EXCLUSION_SOURCES`：§9.2 表格的 38 筆 `(path, field_spec, sha256)` 逐字複製；`B4_EXPOSED_VALUES`：§9.2 列出的曝光值（landscape 3／5／7／8、operator 11／12／13、X control 5／6／7／8、fixture 1／2／3／5、derangement 5／6／9／1、草案 base 觀測 7）。
   - `load_exclusion_set() -> ExclusionSet`：逐檔讀取、重算 sha256，**digest 不符或檔案不存在 = 拒絕**（`ExclusionSourceRefusal`，具名列出）；依 field_spec 抽出整數；與 `b2_search.EXCLUDED_SEEDS` 複本及 `B4_EXPOSED_VALUES` 聯集成**單一 pooled 整數集**；回傳含每來源 `count`／`values` 數、總數、各檔 digest。`evidence/b4/sim/` 不在來源表內，不存在即不是缺檔。
   - `pair_seeds(master, count, exclude) -> list[(l, o)]`：B2 演算法複本（32-bit、單一 stream、兩個位置都查 pooled 集、`l == o` 跳過、已抽過的值跳過），複本 digest 記入 `b4/IMPORT.json`。
2. **`b4_controls.py`**
   - `x_control_seed(l, o)`／`d_shuffle_seed(l, o)`：§8 公式；輸入必須是 int 且非 bool。
   - `f_frozen_view(f_result) -> MapView`：由 `frozen_view`／`map_version_final`／`map_commitment_final` 重建；再用 F 的 ledger 第 1 到 22 筆（base＋21 probes）對新 `ObservationCarto` 重新 ingest，`view().groups` 與 `commitment()` 必須與重建值相等，否則 `ControlInputRefusal`。
   - `d_view(f_result, l, o) -> MapView`：`shuffled_view(f_frozen_view(f_result), d_shuffle_seed(l, o))`；回傳的 `provenance` 必為 `("learned", "shuffled")`、`privileged` False、`base_commitment` = F 的 commitment；實際置換另存。
3. **`b4_snapshot.py`**
   - `prefix_states(result, B) -> dict`：只接受 arm O（其他 arm 另有 `arm_states(result)` 給完整 run 的四態，標明「非 K7 (b) 的量」）；對 ledger 第 1 到 B＋1 筆（`phase` 必為 `base` 後接 `search`）依序 ingest 到新 carto，**逐筆**核對 `map_version_after`／`map_commitment_after`；回傳四態計數（`unknown`／`effect_seen`／`no_effect_seen`／`context_dependent`，和 = 21）、`not_unknown`、該前綴的 commitment；任何不相等 = `recompute_mismatch`（K7 (a) 的 finding，不是結果）。
   - `recompute_findings(result) -> list[str]`：對 O／X／F（含 probe 段）的整條 ledger 做同樣的逐筆核對；X 用 `relabel_genome(genome, x_perm)` 餵 carto、真 genome 餵 shadow，重算 `isomorphic_addresses`。
4. **`b4_k9.py`**
   - `panel(mapping) -> list[int]`：64 個背景 = 5 個 slice-wide mode 位址的全部 32 組合 × 16 個 per-element INIT／SRVAL 位全 0／全 1；位址角色由 `b4_ff_mapping`（host mapping，只供 audit）取得；回傳按 genome 數值排序、去重後**恰 64 個**。
   - `forced_pairs(panel) -> list[(g0, g1, address)]`：每個真位址 × 每個背景，強制 0／1；端點相同的對去重；按 genome 數值排序。
   - `applicable(semantic, address, g0, g1, mapping, hypothesis) -> bool | None`：§9.3 第 4 點逐條：per-element 語意只看所屬元件；latch 下 x5FF 元件的 INIT／SRVAL 與 `sr_kind` 不適用；`storage_kind` 允許 presence 差異；其他語意要兩端點讀出皆適用。回傳 None 的對列入 `not_applicable` 清單並具名。
   - `coverage(task, fabric, mapping, hypothesis) -> dict`：對每個適用對取兩端點在 `task.stimulus`（原樣，含 init readout）下的完整 `q_after` trace；`covered` = 指定讀出範圍內至少一處不同（值差 0／1 或 None／present 皆列出位置）；回傳每語意 `applicable`／`covered`／`fraction`（分母 0 → `not_assessable`，不寫 1.0）、每位址計數、無覆蓋的位址與背景、七語意是否各有正向對照、此 seed 的 K9 觀測次數。**所有觀測走獨立的 `ObservationPort(fabric)`，不進任何 run 的 ledger，不計入 4 000 cap。**
5. **`b4_k10.py`**
   - `backgrounds(l) -> (0, Rng((l ^ 0x4C0A4E55) & 0xffffffff).uniform(1 << 21))`：第二個值取新 Rng 的**首次** `uniform` 呼叫；兩值相同也保留。
   - `seed_k10(task, fabric) -> dict`：兩背景 × 210 個無序對 × `four_corner`；`f(g)` = 該 configuration 在 `task.stimulus` 下的 fitness；可用以 genome 為 key 的 memo（不改任何值，記 `cache_hits`）；回傳全部對的 `I`、四角 configuration 與分數、`comparable`／`not_comparable` 計數、`max_abs`、`classify(max_abs, 2)`；任何 `DomainRefusal` 直接上拋（harness 依停止規則處理為 invalid，不吞成 not_comparable）。
6. **`b4_gate_stats.py`**：`sign_test_p`／`bootstrap_reject_rate`／`required_pairs`／`percentile`／`cohen_d`（paired：對 Δ 序列算 mean／sd）由 `host/b2_gate.py` 逐字複製，`b4/IMPORT.json` 記來源路徑與 digest。
7. **`b4_sim.py`**（harness CLI；§3 是它的契約）。
8. **`b4/schemas/b4_sim_report.schema.json`** 與 raw 檔格式（§4）。
9. 測試與 mutants（§5）、`b4/IMPORT.json`、架構文件 §13 新列與版本註記、`evidence/b4/unit_2b4a_<date>/`（tests.txt、mutants.txt、README）。

**不改的東西：** `b4_engine`／`b4_carto`／`b4_replay`／`b4_execution`／`b4_landscape`／`b4_stats`／`b4_ff_*`／hypothesis／mapping 皆不動（K7 (a) 用 ledger 的 commitment 鏈即可，不需在 `RunResult` 加欄位；見 §6 問題 3）。

## 3. harness 契約（`b4_sim.py`）：前置條件、順序、停止、時限、no-clobber

### 3.1 前置條件（任何一條不成立 → 拒絕啟動，不寫任何檔）
1. **乾淨樹**：`git status --porcelain` 為空。**沒有** `--allow-dirty` 之類的開關。HEAD 寫入報表。
2. **正式輸入**：hypothesis 走 `b4_ff_hypothesis.load()` 預設驗證路徑（`fixture` 必為 False、digest 必等於 §9.2 的 `59948f9b…`）；mapping 走 `site_mapping()`；fabric kind 必為 `truth`。任何 fixture 入口都不接受。
3. **輸出目錄不存在**：`--out` 預設 `evidence/b4/sim/<label>_<UTC yyyymmddThhmmssZ>/`；目錄已存在（即使是空的）→ 拒絕。**從不覆寫、從不追加**既有檔。
4. **時限必填**：`--deadline-s <int>` 沒有預設值；owner 在授權時給值。
5. **label 必填且屬於白名單**：探索只接受 `b4-sim-1`（或 owner 裁定的後續 `b4-sim-N`）；`b4-gate-1` 在此工具被拒絕（正式 gate 是 2b-4 的工具）。
6. **排除集可載入**：§2.1 的 `load_exclusion_set()` 成功；任何來源拒絕 → 不啟動。

### 3.2 凍結順序（在第一次觀測之前完成，且各自寫檔）
1. `seeds.json`：label、anchor（hypothesis digest）、master、排除集來源逐檔（path／field／digest／count）、pooled 總數、`B4_EXPOSED_VALUES`、`count = S`、全部 pair。**寫完 `seeds.json` 之後才允許第一次觀測**；測試用 `SpyPort` 驗證順序。
2. `manifest.json`：HEAD、UTC、hypothesis／mapping digest、engine 常數（μ=4、λ=8、KMAX、B_max=256、grid）、τ=2、K10 salt、arm 順序、deadline、工具檔 digest（`b4/host/*.py`、`b4/schemas/*`）。

### 3.3 每個 pair 的固定順序
`task = make_task(l, addresses)`，然後依序：**R → F → O → X → D → Ω → A0**，每個 arm 一個新的 `ObservationPort(fabric)`（觀測計數逐 arm 記），budget 256，含 holdout。
- F 完成後才建 D（需要 F 的凍結圖；D 的 21 probes 邏輯成本另列，不重觀測）。
- X 的 `control_seed = x_control_seed(l, o)`。
- Ω／A0 用 `oracle_view(mapping)`／`address_only_view(addresses)`，記 `privileged`。
- **每個 run 結束立刻 `replay(result, task)`**，findings 寫入該 run 的紀錄；接著對 O 做每個 grid B 的 `prefix_states`，對 O／X／F 做 `recompute_findings`。
- 七個 arm 都完成且無 finding 後，對該 seed 做 K9 `coverage` 與 K10 `seed_k10`。
- 該 pair 的 `raw_<r>.json` 在 pair 結束時**一次寫出**（寫入前先寫 `raw_<r>.json.part` 再 rename；殘留 `.part` = 該 pair 未完成）。
- 多工（`--workers`）見 §6 問題 6；若允許，每個 pair 自成一個工作單元，結果按 r 排序，順序不影響任何值。

### 3.4 停止規則（fail-closed；依架構 §9.1）
以下任一事件 = **invalid**，harness 做完三件事後以非零 exit code 結束，**不進入下一個 arm、不進入下一個 pair**：
- run 的 `terminal` 非 None（DOMAIN）、`other_refusal` 非 None、`control_failure` 非 None；
- `SourceRefusal`／`ControlInputRefusal`／`ExclusionSourceRefusal`；
- `replay` 或 `recompute_findings` 有任何 finding；
- K9／K10 計算中出現 `DomainRefusal` 或任何例外。
三件事：(1) 把觸發事件所屬的 run／計算的紀錄照原樣寫入當前 pair 的 `raw_<r>.json`（已完成的 arm 保留，未開始的 arm 列為 `not_started`）；(2) 寫 `STOPPED.json`（原因類別、pair 索引 r、arm、attempt／seq、UTC、已完成 pair 數）；(3) 不寫 `sim_report.json` 的 summary（只寫 `batch_status = "invalid"`）。**沒有「跳過這個 seed 繼續」。**

### 3.5 時限
每個 arm 開始前檢查 `now − start ≥ deadline_s`；到期 → 不開始新 arm，當前 pair 標 `incomplete`（已完成的 arm 保留），寫 `STOPPED.json`（原因 `deadline`），`batch_status = "incomplete"`，非零 exit。**不中斷正在跑的 arm**（一個 arm 最多 B＋23 次觀測，可預期）。任何 incomplete 批都不產生 summary 判讀；是否續跑原定未執行的 pair 由 owner 另裁，且續跑是新目錄、新 `STOPPED`／`RESUMED` 紀錄，不覆寫。

### 3.6 完成
全部 S 個 pair 完成且無 invalid 事件 → 寫 `sim_report.json`（§4），`batch_status = "complete"`，exit 0。

## 4. 歸檔格式（schema `b4_sim_report` 1.0.0；每個欄位型別化，replay 可重讀）

- `seeds.json`／`manifest.json`／`STOPPED.json`：§3.2、§3.4。
- `raw_<r>.json`：`r`、`landscape_seed`、`operator_seed`、`task_digest`、七個 arm 各一個完整 `RunResult.as_dict()`＋`replay_findings`＋觀測次數＋wall 秒；`d_input`（F 的重建 view、d seed、實際置換、`residual_structure`）；`x_input`（control seed、π、attempts、residual）；`k7`（O 每個 grid B 的四態與 commitment；O／X／F 的 recompute findings；F 凍結圖與其他控制的四態另列並標「非 K7 (b)」）；`k9`（§2.4 回傳全部）；`k10`（§2.5 回傳全部）；`curves`（每 arm 每 grid B 的 best-so-far 前綴值、F 的 end-to-end 值依 §9 的 T 規則：T ≤ 21 取 base 標 `mapping_in_progress`）。
- `sim_report.json`：`batch_status`；每個 grid B 的描述統計（各 arm median／mean、`Δ1 = O − R`、`Δ2`、`F − R`、`X − R`、`D − R`、`Ω − R` 的 mean／median／正負零計數、sign-test p、population variance）；`N(B)`（required_pairs 複本，n_min 8、n_max S）；按 §9 規則算出的 **candidate** `B*`；K7 (b) 的 median；K9 每語意的 seed 數與 median coverage；K10 四類計數。**每個數字旁列對應的 §9 門檻值作參照，但報表不寫 PASS／FAIL／holds 字眼，頂層固定一行 `"standing": "exploration under label b4-sim-1, S = <S>; not a gate verdict; thresholds of docs/b4_architecture.md v0.1.13a section 9 listed for reference only"`。** 門檻值由程式從常數讀出，不從文件解析（§6 問題 1）。

## 5. 驗收（tests 與 mutants；全部 hermetic，受保護路徑 patch 到暫存副本）

每條都是「有 N > 0 個測試跑過且 OK」才算；mutant 要 `Ran N > 0` 且 FAILED 才算殺。

| 模組 | 測試（節錄） | mutant（節錄） |
|---|---|---|
| `b4_seeds` | anchor 公式對一個假 digest 的手算值；`b4-sim-1` 與 `b4-gate-1` 的 master 不同；含 `\|` 的 label 被拒；某來源檔 digest 不符 → 拒絕並具名；某來源檔不存在 → 拒絕；`evidence/b4/sim/` 不存在不報錯；pooled 集同時擋 landscape 與 operator 位置（以一個已曝光 operator 值作 landscape 抽出的 fixture 驗證）；`l == o` 跳過；全部 pair 值互異且皆 32-bit | 刪除 `B4_EXPOSED_VALUES` 聯集；只查 landscape 位置；digest 不符時只警告 |
| `b4_controls` | 兩個 control seed 的手算值；D 的 provenance／privileged／base_commitment；F 重建圖與 ledger 重 ingest 不符 → 拒絕；D 不消耗 operator／task RNG（用 `SpyPort` 比對 R 的 ledger 不受影響） | 用 operator seed 當 shuffle seed；重抽直到 partition 改變 |
| `b4_snapshot` | 前綴恰用 B＋1 筆；四態和 = 21；逐筆 commitment 相等；篡改一筆 `q_grid` → finding；對非 O 的 arm 呼叫 `prefix_states` → 拒絕 | 前綴取 B 筆（off-by-one）；只核對最後一筆 |
| `b4_k9` | panel 恰 64 個、互異、32 個 mode 組合；forced pairs 去重；latch 下 x5FF INIT／SRVAL 與 `sr_kind` 不在分母；分母 0 → `not_assessable` 非 1.0；三個不同 seed 的分母相同（若失敗，報告並停，不改規則）；觀測不進任何 run 的 ledger | 分母 0 寫 1.0；把 champion 當刺激；ff_init 不計入七者 |
| `b4_k10` | genome1 公式手算；首次 `uniform` 呼叫；兩背景相同時仍兩個；210 對；`max_abs = 2 → nonzero_below_threshold`、`3 → interacting`；DomainRefusal 上拋不吞 | 第二背景取第二次 uniform；τ 比較用 ≥ |
| `b4_sim` | dirty tree 拒絕；out 目錄存在拒絕；deadline 缺省拒絕；label `b4-gate-1` 拒絕；`seeds.json` 在第一次觀測前寫出（SpyPort 時序）；`InjectingPort` 在 pair 1 的 O 注入 DOMAIN → `raw_0` 完整、`raw_1` 含該 run 與 `not_started` 清單、`STOPPED.json`、無 `raw_2`、無 summary、exit 非 0；注入 control failure／replay finding 同樣停；deadline 到期 → `STOPPED` 原因 `deadline`；完整小批（S = 2，fixture seeds）→ `sim_report.json` 無 PASS／FAIL 字串、每個數字旁有門檻參照；`.part` rename 行為 | 停止後繼續下一 pair；dirty 只記錄不拒絕；summary 在 incomplete 時仍寫 |

**測試用 seed 的規則：** 測試只用 §9.2 已列的曝光值（landscape 3／5／7／8、operator 11／12／13 等）；若需要新字面 seed，同一 commit 必須把它加進 §9.2 曝光清單與 `B4_EXPOSED_VALUES`。測試跑模型是機制驗證，不讀任何 `b4-sim-1` seed 的結果，不構成探索（§6 問題 7）。

## 6. 請 owner 裁定

1. **報表只列值、不寫判讀**（§4）：是否接受「每個值旁列 §9 門檻作參照、頂層固定一行 standing、全文無 PASS／FAIL」；還是連門檻參照也不列，只列值。
2. **統計複本的時點**：`sign_test_p`／`bootstrap_reject_rate`／`required_pairs`／`percentile`／`cohen_d` 現在就從 `host/b2_gate.py` 複製進 `b4/`（harness 的描述統計與 2b-4 共用一份），還是留到 2b-4。
3. **K7 (a) 的實作路徑**：用 ledger 每筆既有的 `map_version_after`／`map_commitment_after` 重 ingest 核對（不改 `b4_engine`、不加 `RunResult` 欄位），還是要求把最終 relations 文件存進 `RunResult`（engine 改動＋replay shape 更新）。本稿建議前者。
4. **測試 seed 規則**（§5 末段）是否接受。
5. **前置條件**：乾淨樹無開關、deadline 必填、out 目錄存在即拒絕（§3.1）是否接受。
6. **多工**：是否允許 `--workers > 1`（每 pair 獨立、結果按 r 排序、值與排程無關），或探索一律單工。
7. **確認**：本單位的測試執行（在 fixture seeds 上跑模型）不算「探索」，且本單位交付後 S = 32 探索仍需另一次授權。
8. **單位切分**：七個模組一筆 commit，或拆成 (a) seeds＋controls＋snapshot、(b) k9＋k10、(c) harness＋schema 三筆。

## 7. 本稿不做、不主張

- 不寫程式、不跑模型、不抽 seed、不算 K 值；§3.3 的觀測次數算術（每 pair 主臂 3B＋27 = 795、七臂合計 1 827；K9 每 seed 去重前 ≤ 2 688；K10 每 seed 1 680 個角）是定義推算，不是量測，也不是時間或板上估計。
- 不宣稱 gate-ready；探索結果（若日後授權）只是探索資料，不能通過 S = 200 的正式 gate，門檻不在運行中改。
- 不對矽作主張；v0.3 仍 unverified、A8 未解；K10 的可比性只在模型 domain 內。
- 不碰 pinned 輸入、不上板、不 push、不 merge；`main` 保持 `d5bf815`。
