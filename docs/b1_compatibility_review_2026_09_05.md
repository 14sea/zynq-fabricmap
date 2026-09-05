B1 compatibility review — package §7，2026-09-05

**結果：HOLD。** 對 image `54b00663…` 的靜態審查與離板驗證發現一項阻擋：`SIGNREF` 分支沿用 P3「拒絕後繼續」的行為，違反 B1「任何未 SCORED candidate 都結束 epoch」的契約。其餘 §7 項目結果如下。這份 review 不執行 freeze、不授予 board ruling，也不將 carrier 標為 qualified。

審查基準：fabricmap `a548bfb2afe145c37a66df0d4f1cec3fc4629819`；instrument `689dde1dad374536c625bbe2b05986ee89eb4c94`。開始審查時兩棵樹均乾淨，fabricmap 與本地 origin/main 一致。原有 firmware、image、RTL、manifest 與 evidence 均未因本次審查改動；本次只新增此報告與離板 review artifacts。

| 綁定 | sha256 |
|---|---|
| manifest | `b85746114fa3dab1b09f8046cb034545a6de0b0fab928200c6c4a66e4612a895` |
| image，114708 bytes | `54b006636fe07d1b52784e636452cfbd1191407a100699a7666c57b96ba4d6c8` |
| ELF | `9d23ddf9190d4cde0e11a02a2adf469acd6d65d8b4963e26afee50c0371233f7` |
| carrier | `d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f` |

已重新核對以上 bytes，以及 93 個 fabricmap pins、128 個 instrument pins 和 IMPORT.json 的每個來源／verbatim copy。函式級比較顯示 b1_app.c 有 49 個共同函式逐字不變；共同函式中只有 axi_readable、establish_identity、run_candidate、main 改動，新增 carto_block，移除 schedule_mode。完整 diff 與清單在 [review evidence](../evidence/b1/compatibility_review_2026_09_05/)。

| package §7 項目 | 判定 | 核對結果與證據 |
|---|---|---|
| Wire contract | 通過本項 | rel-v4 framing、CRC、base64、REC／IDENT／SIGNREQ／TERM 的交易單元不變。b1_wire.c/h 的變更為 IDENT 1.4.0 新增 carrier_variant、carto_version、probe_budget、universe_sha256，以及 REC 1.2.0 新增 carto；B1 不輸出 arm。實際 C serializer 的 identity／record 被 instrument validator 接受。序列化 tally 的程式碼未改動。test_b1_wire 3 tests 通過。 |
| Settle poll | 通過本項 | settle_condition 與 arm_attempt 逐字不變。20 payload writes + 4 tag writes + 1 CTRL strobe；最多 1000000 次 STATUS reads；poll 不補發 ARM。只有 gate/scorer 均不忙且 fault 或 scorer_done 已鎖存才結束。保留 status_first、status_last、fault 與 nonce 的成功／失敗證據。B1 不要求 tables_match=1 才承認 cfg_valid。 |
| Audit service | 通過本項 | p3_pull.c/h、p3_rectx.c/h 的 imports 逐字相同；audit_pull 與全部 pull callbacks、audit_word、emit_record 逐字不變。1602 staging words + 1212 readback words = 2814，384-word window，8 chunks；AUDITDONE 完成與實際 served 才能標 audited。正常 SCORED 路徑仍在 ARM 前完成要求的 audit；pull 失敗走 STOP_AUDIT，不 ARM。B1 end-to-end 模型測試驗證 335 records 全數 audit。 |
| MMIO allowlists 對 B1 RTL | 通過本項 | app read 集合與 RTL decode 相等；新增唯讀 0x2034 VARIANT，值 0x42310001。CTRL 0x2000 仍不可讀；寫入只允許 CTRL、20-word payload 與 4-word tag。RTL 比 app 多的 write offsets 只有 0x2160–0x216C key window，app 不可寫；write-once key 與 key-read SLVERR 不變。MmioAllowlist 兩測試與 RTL bench 通過。 |
| DMA order | 通過本項 | devcfg_dma、devcfg_wait_done、stage_streams、write_envelopes、readback_frame、link2_witness、link3_witness 均逐字不變。先確認 PCAP mode、清除／確認 interrupt status，再依 SRC_ADDR→DEST_ADDR→SRC_LEN→DEST_LEN 寫四個 registers，等待 D_P_DONE，不能以 DMA_DONE 代替。readback 依 command→frame DMA→cleanup；prefill sentinel 驗證不變。link-2 比對先於 DMA，link-3 比對與 audit 先於 ARM。 |
| Cache／資料區界線 | 通過本項 | main 在第一次 staging 前，以相同 Xil_SetTlbAttributes 呼叫將 command、destination、staging、identity page 與 evidence ring 設為 strongly ordered／non-cacheable；沒有新增依賴逐筆 flush 的路徑。image／heap／stack 的連結區與上述 buffers 分離。 |
| No ICAPE2 | 通過既有產物核對 | B1 synthesis sources 不包含 ICAPE2；post_route_util.rpt 與 b1_build.json 均為 0 cells。B1 仍用 PS PCAP。carrier bitstream hash 相符。本次未重新跑 Vivado place-and-route，亦未以板上讀取驗證。 |
| No SLCR write | 通過 source／diff 核對 | b1_app.c 的 SLCR 使用為讀取 PSS_IDCODE 0xF8000530；沒有新增 Xil_Out32 到 SLCR。其餘寫入仍是既有 DDR／DEVCFG／受 allowlist 保護的 AXI。main 的 XTime_SetTime(0) 與 watchdog 初始化沿用原程式，不能把它們當成新增 SLCR writes。 |
| Watchdog gating | 通過本項 | flags.bit1 才執行 CfgInitialize→SetControlReg（prescaler 7、WD_MODE）→LoadWdt（1250000035）→Start，再設定 wdt_started。kick_watchdog 僅在 wdt_started 後 Restart；IDENT 發出時不會 kick 未初始化 instance。flag 關閉時不啟動 watchdog。這些程式片段與 progress kick points 不變；30 s 的時間解讀仍依賴已指定 clock，並非本次重新量測。 |
| 既有交易 bounds | 通過數值／程式比較 | 單次 bounded receive 仍受 8 s tick bound 與 poll cap 雙重限制；REC／pull idle cap 50000000，IDENT／SIGNREQ／TERM 100000000。交易最多 3 transmissions，stale lines 64、previous ACK 8、AUDITWAIT 3 的既有規則不變。C pure transaction units 與 wrappers 相同。 |
| B1 記憶體 | 通過靜態容量核對，非硬體高水位量測 | ELF 中 O=4664 B、g_carto_json=2048 B、g_map_render=20480 B、g_content=20480 B；加上 tables／variant／changed globals，B1 cartography 相關靜態配置約 48320 B。package 的「~34 KB state +20 KB render」是粗估，宜以這些實際符號數字表述。沒有把整份 map 放入 stack。 |
| C stack 與 linker bounds | 未見 B1 新增容量阻擋；有明確量測限制 | 用相同 ARM 編譯旗標加 -fstack-usage：run_candidate=9968 B，與 archived P3 相同；main=400 B（P3 為 368 B）；b1_orch_record_block=640 B；draw_pairs=640 B；b1_carto_render=200 B。主 stack 配置 16384 B，heap 1048576 B；ELF 的最後 stack endpoint 為 0x021414F0，位於從 0x02000000 起的 4 MiB 約定內。這是各函式 frame 與連結容量核對，沒有宣稱量得硬體 stack 高水位，亦沒有宣稱涵蓋 libc 全呼叫圖的形式化上界。 |
| Carto／REC payload | 通過離板壓力案例 | 既有測試僅用 2 筆 changed；本次另用相同 C renderer／serializer，以 8 筆 changed、292 contradiction entries、32 pairs、長數字欄位及 32-bit counter 極值做保守壓力案例：map=12446 B（buffer 20480）、carto=576 B（buffer 2048）、REC=2306 B（buffer 4096），base64 frame 保守長度 3136 B（buffer 7168）。實際 4096-byte output buffer 的 serializer 成功。此案例是容量測試，不是合格的科學 map 或 on-board observation；serializer 的 overflow→0 與 caller 的 PROTOCOL stop 也保留。 |
| B1 init／成功 session order | 通過本項 | main 在 opening baseline 前執行 b1_orch_init（內含 init+bind）；probes 從 readout 更新 map 後再輸出 commitment。正常 B1／B1Q 的 C↔Python session 與 335-record host model 通過。 |
| B1 未 SCORED 即停止 | **HOLD，阻擋 compatibility 通過** | run_candidate 的 SIGNREF 分支輸出 REFUSED_BY_GATE 並收到 RECACK 後 return 0，未設定 STOPPED。main 把 0 當成成功繼續，跳過 b1_orch_unobserved 與 break；對 code probe 可再提出相同 genome。詳見下方重現。 |
| RTL diff | 通過本項 | b1_arm_gate 在完成 sweep 後仍計算 tables_match，但 SEMANTIC_GATE=0 時它不再阻擋 valid_latch／scorer_arm；SipHash、nonce、write-once key、unsigned／replay／wrong-key refusal 與 sticky recovery 保留。b1_axil 新增唯讀 VARIANT；b1_core／b1_top 傳遞參數並改模組名；p3_siphash 完全相同。Vivado script 明確指定 SEMANTIC_GATE=0。 |

RTL bench 已重跑：零表簽章配非零 readout 可 ARM、tables_match=0 仍 cfg_valid；readout 隨 fabric 改動；no-key、wrong-key、wrong-commit、unsigned、replay 均拒絕；key write-once／read refusal、VARIANT read／write refusal、reset 清 key 均通過。既有實體實作報告的 WNS +7.993 ns、WHS +0.026 ns、隔離 passed 亦核對；這些不是新的 silicon qualification，B1Q 仍須其獨立 ruling pair。

**阻擋的可重現行為。** [b1_app.c 的 SIGNREF 分支](../firmware/b1/b1_app.c#L1235) 沿用 P3 的「gate refusal is data; session continues」；[main loop](../firmware/b1/b1_app.c#L1571) 只在非零 return 時停止。這與 b1_architecture §3、b1_preregistration §2 和 b1_orch.h 的 B1 停止契約不一致。

本次 harness 從實際 b1_app.c 擷取 SIGNREF 分支，僅把 emit_record 換成成功收到 ACK 的 stub，連結真正 b1_orch.c／b1_carto.c／p3_derive.c。先完成 opening baseline，再讓第一個 code probe 收到 SIGNREF。輸出：

```text
SIGNREF rc=0 running=1 next_candidate=1 same_genome=1 probes_issued=2
```

這是 source 分支與 orchestrator 的離板重現，不是假稱執行了整個 ARM application 或板子。現有 test_b1_session 的 UNSCORED 模擬在 twin 內直接 break，因此無法捕捉 application 的這個回傳值；47 個既有相關測試全綠與此缺陷可以同時成立。即使事後 adjudicator 拒絕該 session，也不能替代 board application 在拒絕當下停止下一個 probe 的要求。

解除 HOLD 所需的修正範圍：

1. SIGNREF 成功記錄後，application 必須結束 epoch，不再發出下一個 probe、closing scored baseline 或 closing ARM；保留規範允許的 restore-only cleanup 與 terminal evidence。以明確成功／未 SCORED 結果或一致的 stop+return 契約落實，不只在 twin 中加入 break。
2. 補涵蓋實際 application 分支的 regression：opening baseline、一般 probe、closing baseline 分別收到 SIGNREF；包括 record ACK 失敗路徑。驗證無後續 candidate／ARM，以及 epoch outcome 不能宣告 COMPLETED。
3. 修正涉及 firmware，不能沿用本次 image hash。需重新建置、更新 build evidence／image pins，重跑 wire、session、非 SCORED 路徑與完整 suite，再對新 image 做 compatibility re-review。現有 carrier RTL 沒有在本次審查中發現需要變更的項目。

本次驗證為 9 個 test modules、47 tests、0 skip、OK；log 見 [tests.log](../evidence/b1/compatibility_review_2026_09_05/tests.log)。範圍為 test_b1_wire、carrier、build_evidence、leakage、twin、session、e2e、signer、records。本次沒有重跑全專案 1417 tests；既有 clean-tree report 是先前的記錄，不能當成已涵蓋這個新反例。

review artifacts 包括函式差異清單、application／wire／四個 RTL diff、SIGNREF harness、payload harness、ARM stack-usage 結果及綁定 metadata。可在 repository root 以以下方式重跑 SIGNREF 重現；不讀寫任何板子或 key store：

```sh
cc -std=c99 -O2 -Ifirmware/b1 evidence/b1/compatibility_review_2026_09_05/signref_repro.c firmware/b1/b1_orch.c firmware/b1/b1_carto.c firmware/b1/p3_derive.c -o /tmp/b1_signref_repro
/tmp/b1_signref_repro
```

原 manifest 仍為 prereg.sha256=null、board_ready=false、qualification=null、qualified=false。沒有 freeze、commit、push、serial access、power cycle、provision 或 image load。
