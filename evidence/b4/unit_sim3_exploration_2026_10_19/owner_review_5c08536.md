# The owner's review of 5c08536 (2026-10-19) — 覆核重點摘錄 (the key points, as relayed by the user; not the review copied unchanged — the owner's item 3 on 00754d3)

獨立 deep verify：exit 0、findings {}。B* = null 與資料一致，但摘要有三處錯誤：

- K5 計算的是 O−R，不是 F−R。
- K9：ff_srval median coverage 0.427083、sr_kind 0.5，其餘五項才是 1。
- K5 全部掃描 power 為 0～0.064；只看 N=32 為 0～0.046。
