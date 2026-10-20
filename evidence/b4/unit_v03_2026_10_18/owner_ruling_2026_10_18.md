# The owner's rulings that open and bound this unit (2026-10-18; pasted text)

> **Labelling (the owner's P3 on `12eaa72`):** the X-A PASS below is the pasted text in full. The v0.3 section below is an
> **EXCERPT** — the summary the owner pasted as the final response to the scope draft. The owner's **full, detailed ruling** on
> the v0.3 scope draft (five sections: source strength and G1–G6, the kept v0.2 file, the acceptance corrections, the file
> scope, regression and mutants) is archived beside this file as `owner_ruling_v03_full_2026_10_18.md`, copied from
> `build/wip/b4_v03_model_revision_owner_ruling_2026_10_18.md` (an ignored path, not a tracked archive by itself).

## The X-A PASS on c0689f8, naming the next step

c0689f8 PASS，X-A 工程驗收結案。

獨立重跑 128 tests 全部 OK；額外探針確認 RNG 隔離、逐 specimen 同構、control failure 提交點及 replay 均成立，兩種 partition fixture 也符合預期。覆核證據 (build/wip/owner_review_c0689f8_2026_10_18/README.md)

此 PASS 僅驗機制，不代表負向控制數值成立或 gate-ready；正式 hypothesis 仍為 0.2.1，F 的 DOMAIN 限制未變。

十四筆本地 commit 保留。下一步可提 v0.3 模型修訂的只讀範圍草案，分清 host 對應證據、UNISIM 行為與推廣假設。v0.3 實作、2b-3、探索、gate、push／merge、板上工作仍未授權。

## The ruling on the v0.3 scope draft (`build/wip/b4_v03_model_revision_scope_draft_2026_10_18.md`, ignored), authorising this unit — AN EXCERPT (the full ruling: `owner_ruling_v03_full_2026_10_18.md`)

- L1 標為 host correspondence，釘 attempt 2 的 probe_report.json；整體讀法仍依賴具名前提，維持 unverified。
- 保留原 v0.2 檔案，bytes 不變；v021_hole 從此檔核對舊 digest 後建立標記 fixture。
- 保留 mechanics fixture。
- IMPORT 過期引用與架構標題併入本單位。
- 保留 unknown enum、DOMAIN 機制及既有拒絕覆蓋。
- §5.3／§13 明寫：v0.3 在新增假設下補上模型定義的洞，尚未證明 gate-ready。

實作前須修正三點：

- 固定 LATCH、CLKINV 後剩 19 個自由位元。
- F 的 base＋probe 小計是 22；完整 run 含 B 次搜尋與一次 holdout，總呼叫數是 B＋23。
- 手推 trace 須遵守模型先在舊 clock 下套用新 D 並 settle 的順序；不能同時關 gate、改 D，卻預期保留舊 Q。INIT 的原子賦值、不 settle 也須明列為模型抽象，A8 仍未解決。

限本單位模型文件、正式載入指向／digest、相關測試、IMPORT、架構與證據；行為狀態機及 engine 等 production 邏輯不改。完成局部回歸與有效 mutants 後，本地 commit 交覆核。

2b-3、探索、gate、push／merge、板上工作仍未授權。
