B1 v2.3.1 compatibility review — package §7，2026-09-05

**結果：PASS（package §7 的靜態審查與離板驗證範圍）。** 本結論只適用於下列 image、來源與 carrier。先前 SIGNREF 後繼續執行，以及 opening baseline 誤設 closing baseline 旗標的兩項阻擋均已關閉。這是新 image 的重新審查；[舊 review](b1_compatibility_review_2026_09_05.md) 對 `54b00663…` 的 HOLD 保留，`54b00663…` 與 `31663e2d…` 的 WITHDRAWN / DEFECTIVE / NO-RUN 狀態不變。

| 綁定 | 值 |
|---|---|
| fabricmap HEAD／本地 origin/main | `3955b17`，完整 commit 見 evidence metadata；開始審查時一致且工作樹乾淨 |
| instrument | `689dde1dad374536c625bbe2b05986ee89eb4c94`，工作樹乾淨 |
| manifest SHA256 | `4aa69c32a5dd4b76798c0b6da38ee8b084844a628651f458d8a5f1d8964906d9` |
| image SHA256，114708 B | `300b12b1104b70d1612f4c6236a9280a0556443757b2ddf9dbadd9ef993d5abb` |
| ELF SHA256 | `8de78efc76b26bc49c22fbd25b3cc957d1499c3a5fd42e8268a40da3586e0022` |
| carrier SHA256 | `d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f` |
| build evidence SHA256 | `aa5af8337d71c8453b596cd7b5f792f72bc3d35f560d0e1aebbbacbd2d77d96a` |

已重新計算本地 image、ELF、carrier、build evidence、應用程式 sources、47 個 translation units、86 個 headers、7 個 toolchain objects 的 hash，核對 102 個 fabricmap pins、128 個 instrument pins，以及 IMPORT.json 的來源與 verbatim copies。既有兩次乾淨 build 的 image hash 均符合本次 image；本次沒有再做兩次完整 build，而是以相同 ARM flags 編譯七個 application units，加上 `-fstack-usage`，並確認其反組譯指令與原 build objects 全部相同。

完整 diff、hash 綁定、stack／ELF 結果、payload 輸出與 application 情境 log 位於 [review evidence](../evidence/b1/compatibility_review_2026_09_05_v231/)。目前 application 對 instrument 有 49 個共同函式逐字相同；共同函式僅 `axi_readable`、`establish_identity`、`run_candidate`、`main` 改動。新增 `carto_block`、`note_scored`、`b1_session_init/run/finish`，移除 `schedule_mode`。逐項核對依 package §7 與 instrument 的 L6 preregistration §2 相容性清單；B1 的搜尋方式、零表簽章與 carrier 語義則依 B1 自身契約。

| package §7 項目 | 判定 | 核對結果 |
|---|---|---|
| Wire contract | PASS | rel-v4 framing、CRC、base64 與交易處理不變；IDENT 1.4.0 增加 B1 identity fields，REC 1.2.0 增加 carto，B1 不輸出 arm。serializer tally 不變。實際 C serializer 與 application 拒絕情境的 REC／TERM 通過 instrument validator。 |
| Settle poll | PASS | `settle_condition`、`arm_attempt` 與 instrument 逐字相同；20 payload + 4 tag writes，單次 CTRL strobe，最多 1000000 次 STATUS reads，不補發 ARM。保留 first／last status、fault、nonce 證據。 |
| Audit service | PASS | pull／rectx imports、audit callbacks、`audit_pull`、`audit_word`、`emit_record` 不變。2814 words、384-word window、8 chunks；完成實際服務才標 audited。link-3 與要求的 audit 仍在 ARM 前，失敗停止。e2e 模型的 335 records 全 audit 測試通過。 |
| MMIO allowlists 對 B1 RTL | PASS | application read 集合等於 RTL decode，包含唯讀 VARIANT `0x2034 = 0x42310001`。CTRL 不可讀；application write 僅 CTRL、payload、tag。RTL 額外 write window 只有 `0x2160–0x216C` key registers，application 不可寫。兩個 allowlist 測試通過。 |
| DMA order | PASS | DMA／wait／stage／envelope／readback／link-2／link-3 函式逐字不變。PCAP mode 與 interrupt 檢查後依 SRC_ADDR→DEST_ADDR→SRC_LEN→DEST_LEN 寫入；等待 D_P_DONE。readback command→frame→cleanup 與 sentinel 檢查保留。 |
| Cache／資料區 | PASS | main 的 non-cacheable TLB 設定及其時機不變，command、destination、staging、identity page、ring 在使用前設定。image／heap／stack 與這些 DDR buffers 分離。 |
| No ICAPE2 | PASS，既有產物核對 | B1 RTL 無 ICAPE2 instance；post-route utilization 與 build record 為 0，carrier hash 相符，仍走 PS PCAP。本次未重跑 Vivado。 |
| No SLCR write | PASS，source／diff | SLCR 僅讀 PSS_IDCODE；所有 Xil_Out32 目標仍為既有 DDR、DEVCFG 或受 allowlist 保護的 AXI。新增 helper／session 函式無 SLCR write。 |
| Watchdog gating | PASS | main 保留 flags.bit1 閘控、初始化失敗即停止、prescaler 7、load 1250000035、WD_MODE→load→start→wdt_started；kick 只在 started 後執行，progress points 不變。30 s 仍依指定 clock，未重新量測。 |
| 交易 bounds | PASS | receive 的 8 s tick bound 與 poll cap 不變；REC／pull 50000000、IDENT／SIGNREQ／TERM 100000000；最多 3 transmissions，stale／previous ACK／AUDITWAIT 界限及 imported transaction units 不變。 |
| Cartographer 靜態記憶體 | PASS | ELF：O 4664 B、carto JSON 2048 B、map render 20480 B、content buffer 20480 B；含 tables／variant／changed globals 合計 48320 B。package 的「~34 KB state +20 KB render」是粗估，實際容量以這些符號為準。整份 map 沒有放入 stack。 |
| Stack／linker bounds | PASS，靜態容量範圍 | 新編譯 `run_candidate` 9960 B（舊 image／instrument 為 9968 B），main 400 B，stage_streams 2176 B，orch record block 640 B，carto render 200 B。主 stack 16384 B、heap 1048576 B；最後 endpoint `0x021414F0`，在從 `0x02000000` 起的 4 MiB 約定內。這是 frame 與配置核對，並非硬體高水位或含 libc 全呼叫圖的形式化上界。 |
| Carto／REC payload | PASS，壓力案例 | 以目前 renderer／serializer 重跑 8 changed、292 contradiction entries、32 pairs 與長數字欄位：map 12446／20480 B、carto 576／2048 B、REC 2306／4096 B、保守 frame 3136／7168 B。實際 4096 B output buffer 成功，overflow→0 與 caller protocol stop 不變。此為容量案例，並非有效科學 map 或板上資料。 |
| Init／成功 session order | PASS | main 依 init→run→finish 呼叫；opening 前 init+bind。SCORED probe 從 PL readout 更新 map，REC 成功後才做正常簿記。DONE 且仍 RUNNING 才執行 closing control／COMPLETED。C↔Python twin、session 與 e2e 測試通過。 |
| 未 SCORED 即停止 | PASS，舊 HOLD 關閉 | SIGNREF 的 RECACK 成功後明確 STOPPED、return -1；RECACK 失敗也停止。run loop 不再提出下一個 candidate，finish 僅 restore cleanup 後 TERM。STOP_AXI 明確保證 stop；其他非 SCORED REC 路徑的 stop／return source audit 通過。 |
| Closing baseline 簿記 | PASS，P2 關閉 | `note_scored` 只在 is_baseline 且 O.step==DONE 設旗標；opening 的 step 為 PROBES。harness 共用此函式；opening 後旗標 0、closing 成功簿記後 1。probe／closing 被拒後的真 session loop 均產生 baseline=not_reached 的 TERM。 |
| B1 carrier RTL diff | PASS | 重生並核對 gate／axil／core／top diff：SEMANTIC_GATE=0 僅取消 expected tables 與 readout 比較對 valid／scorer_arm 的阻擋，tables_match 仍記錄觀察值；簽章、nonce、key、recovery 不變。AXIL 增唯讀 VARIANT；core/top 傳參數；SipHash 逐字相同；Vivado 明確指定 SEMANTIC_GATE=0。 |

本次重跑 **10 個 modules、55 tests、0 skip、OK**，見 `tests.log`：wire、carrier、build_evidence、leakage、twin、session、e2e、signer、records、hostapp。carrier 測試內重跑 SipHash 與 B1 core RTL benches，涵蓋零表簽章配非零 readout、tables_match=0 仍可 valid、no-key／wrong-key／wrong-commit／unsigned／replay refusal、key write-once／read refusal、VARIANT read／write refusal 與 reset 清 key。既有 route report 的 WNS +7.993 ns、WHS +0.026 ns、isolation passed 與 hash 亦已核對。

另存六個 application 情境的原始輸出：opening／probe／closing SIGNREF，以及 RECACK 失敗，都只有一個 SIGNREQ、零 CTRL／payload writes、三個 restore envelope DMAs、STOPPED TERM；closing.baseline 與 unsigned_control 均為 not_reached。RECACK 失敗情境恰有三次 REC transmissions。兩個狀態情境確認 opening 與 closing 簿記的旗標分別為 0、1。

**驗證限制：** hostapp 直接編入目前 `b1_app.c`，被拒 candidate、session loop、restore 與 TERM 執行實際 application 程式碼；此前 SCORED candidates 由 orchestrator observation 與 application `note_scored` 預置，沒有執行實際 PL staging／ARM／score 路徑。兩個成功簿記情境也不代表完整成功 hardware session。RTL simulation、host model 與 source audit 的通過不構成 silicon qualification。完整 suite 的 **1425／0 skip** 是已提交 `…T191204Z.json` 的乾淨樹紀錄；本次重算其 artifact hashes，未重新執行完整 suite。

本次只新增這份 review 與 evidence，未改 firmware、image、carrier、manifest、plans、predictions 或 pins；未 commit／push。`prereg.sha256=null`、`board_ready=false`、`qualification=null`、`qualified=false` 保持不變。下一站為 owner freeze，之後才是綁定凍結 manifest／prereg／本 image 的 B1Q ruling pair；本 review 本身不執行 freeze，也不授予 provisioning、載入 image 或接觸板子的權限。
