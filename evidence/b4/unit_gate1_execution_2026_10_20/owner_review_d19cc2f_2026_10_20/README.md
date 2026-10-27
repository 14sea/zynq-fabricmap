# Owner review: d19cc2f (2026-10-20)

覆核 PASS；production b4-gate-1 執行交付單位結案，正式判決維持 valid FAIL。

審查範圍為 5070967 的 production archive 與 d19cc2f 的執行／驗證紀錄。兩個 fresh-process deep verifier 均獨立重跑，exit 0、findings {}、clean true，輸出及命令列於本目錄。4005 個 committed blobs 與磁碟檔案全等，無缺無多。工具／模型／門檻與 B3 歷史路徑未改動，工作樹乾淨。

另從 200 份 pair 文件核算各 budget 的 Δ1 mean、sample Cohen's d、one-sided sign-test p 及 K7 中位數；由 K9 的 per-address 計數彙整 per-semantic coverage 再取 200 seeds 的中位數；從 84,000 組 K10 四角分數重算 interaction；均與報表相符。完整重放及 bootstrap N scan 由 deep verifier 持有；手動核算不另行聲稱獨立實作 bootstrap。核算結果在 independent_checks.json。

執行身分、S=200、deadline=3600、receipt 66 值、起跑前 pool 2224 均符合授權。45 個 repository inputs、25 個 tool/schema 項目與 6 個 external inputs digest 全等；25 個 tool/schema 項目符合 00336d0 基線。只讀取已歸檔值核對：本次 401 個 master/pair 值互異且與起跑前 pool 零碰撞，現行 pool 為 2625；未呼叫任何 seed 推導。

結果：budget rule FAIL，B*／N 為 null；K9 因 ff_srval median 0.40625 < 0.50 而 FAIL；K1–K7 not_assessable，K8／K10 PASS。此結果只限已宣告的模型、task/panel、operator/control、budget grid 與方法，不推論 silicon、carrier、整個 FF class 或效應不存在。Label 已消耗，不重試、補抽、換 label 或回調門檻。

一項不阻擋結案的 P3：unit README §2 將 batch+judgement 31.7 min 寫成 inside 全流程 50–70 min estimate，範圍不一致。應分寫 batch+judgement 約 31.7 min；含兩次 fresh-process verification，由 10:25:26Z 至 11:15:01Z 約 49.6 min。併入下一筆適當文件 commit 即可，不另開覆核輪、不重跑。包裝命令的 tail 錯誤不改變兩個 verifier 的獨立 exit 0。

不新增 push、merge、protocol revision 實作、新 gate/seed、RTL、2d、routing 或板上授權。無須為本 PASS 額外製作一筆結案 commit；如需歸檔，本紀錄可併入下一筆適當文件提交，標明來源。
