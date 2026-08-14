# Claim B round 1 known answer (offline)

This directory holds the deterministic artifact requested by
[`docs/claimb_known_answer_request.md`](../../docs/claimb_known_answer_request.md). It is
offline evidence only: its presence does not authorize a board write.

The producer selects no candidate. It mechanically applies frozen reachability-report
entry 0 to the 49 LUT0 locations derived from the erratum-006 local map. The independent
consumer recomputes the artifact without importing the producer.

```sh
python3 scripts/build_claimb_known_answer.py --out /tmp/known_answer.json
cmp /tmp/known_answer.json gate_runs/claimb_round1_known_answer_2026_08_14/known_answer.json
python3 scripts/gate_claimb_known_answer.py
python3 scripts/mutate_claimb_arm.py
```

Pinned artifact SHA-256:
`b115e6be3c44b1500aaf0281bd7f480afa61654a12b1083a778fb9d9cb2f5ef1`.

The candidate changes 26 content bits over FARs `0x00400A20`–`0x00400A23`. Its
serialized payload SHA-256 is
`41b3a6f75de7d8f435b6c5f0a8d053397e978310586037e7c4ecb1875b635ed4`;
the complete 15-frame readback SHA used by the arm interlock is
`c82d7aa4e591321646e4e326b4d9f7fb827d95b53d3cd502ed3e497a031f7e02`.

The restore payload SHA-256 is
`07fbca9e93f0066a7873607b9a79ad89521e37a8853ef92ec88256dac4fdb9c6`;
its complete readback SHA is
`67fc9c21b69983a72c82dc8dd7c555cd7dd2702f55f523ea5fad9c81cdec9d42`.
