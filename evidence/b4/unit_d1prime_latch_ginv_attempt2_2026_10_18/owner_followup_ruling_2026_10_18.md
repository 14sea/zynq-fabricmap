# Owner's follow-up ruling on the D1′ latch_ginv probe, attempt 1 (2026-10-18) — as relayed by the user, verbatim

可以。此檢查應接受 ROUTED 與 INTRASITE。 AMD 2025.2 文件明定，INTRASITE 表示連線已在同一 site 內完成，並非錯誤。UG912 定義

我用兩份原始 readback 獨立核對：加入 INTRASITE 後，六條誤報全部消失；UNROUTED、PARTIAL、缺值等九種反例仍被拒絕。

授權這次 follow-up：

- 只把判準改成上述兩值，補正向與負向測試；其他預期條款不改。
- 先提交新 recipe，再做第二次 attempt，使用全新的 raw／evidence 目錄與 stamps。
- 第一輪 expectation_met:false、exit 2、artifacts 與紀錄全部保留，不覆寫或回填成功。
- 第二輪完成後交覆核；若有其他 finding，照原停止規則處理。

這只修正繞線完成狀態的判讀，不證明路徑相同或矽上行為。D1′ 尚未結案，X-A 等其覆核後再開；v0.3、push／merge、板上工作仍未授權。
