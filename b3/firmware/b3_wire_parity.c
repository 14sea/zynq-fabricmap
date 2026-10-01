/* b3_wire_parity — the B2 / B3 wire parity driver (b3/tests/test_b3_wire_contract.py). B3 lifecycle 2, image
 * stage 3.
 *
 * Host-only. The SAME source is compiled twice: against firmware/b2/b2_wire.c (-DWIRE_B2) and against
 * b3/firmware/b3_wire.c, and called with the same fixed inputs; every public builder's output is printed one
 * per line ("<TAG> <bytes>"). The test requires every line to be byte-identical but the identity's and the
 * loop record's, which may differ only by what b3_wire.h declares (the identity's version and three fields,
 * the record's version). Nothing here is board code.
 */
#ifdef WIRE_B2
#include "b2_wire.h"
#else
#include "b3_wire.h"
#endif
#include "p3_derive.h"

#include <stdio.h>
#include <string.h>

static char out[65536];

static void show(const char *tag, size_t n)
{
    printf("%s %s\n", tag, n ? out : "<0>");
}

static uint32_t word_at(uint32_t i) { return (i % 7u == 0u) ? 0u : 0x01020304u * (i + 1u); }

static const char *zero_tables[6] = {"0000000000000000", "0000000000000000", "0000000000000000",
                                     "0000000000000000", "0000000000000000", "0000000000000000"};

static void scored(p3_wire_record_in *r, uint32_t seq)
{
    int i;
    static const uint32_t int_sts[3] = {0x1u, 0x20u, 0x300u};
    memset(r, 0, sizeof(*r));
    r->seq = seq;
    r->genome = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    r->outcome = "SCORED";
    r->audited = 1;
    r->have_sign_reply = 1;
    r->commit = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    for (i = 0; i < 6; i++)
        r->tables[i] = zero_tables[i];
    r->tag = "88c45cf12e6857e7af54751d700e0f71";
    r->have_oracle = 1;
    r->staged_sha256 = r->commit;
    r->staged_stream_sha256 = "3ec0c49aed63997df3346caf51e92843d08df351b1dc15e215a8f1d82f2d02b9";
    r->readback_sha256 = r->commit;
    r->envelopes_n = 3;
    r->envelope_int_sts = int_sts;
    r->audit_available = 1;
    r->have_arm = 1;
    r->nonce_before = 0x9e3779b97f4a7c15ull;
    r->nonce_after = 0xdc1b77ae0bf34dadull;
    r->status_after = 0xf54u;
    r->fault_after = 0x3u;
    r->key_loaded_observed = 1;
    r->writes_issued = 25;
    r->settle_polls = 16;
    r->settle_polls_max = 1000000u;
    r->settled = 1;
    r->status_first = 0x901u;
    r->have_score = 1;
    r->hw_candidate_commit = r->commit;
    for (i = 0; i < 6; i++) {
        r->readout[i] = zero_tables[i];
        r->scores[i] = (uint32_t)(10 + i);
    }
    r->hb_before = 7;
    r->hb_after = 9;
}

int main(void)
{
    static const char *findings[2] = {"finding one", "a \"quoted\" one"};
    static const char *kinds[2] = {"GATE_KEY", "GATE_NONCE"};
    static char entries[8192];
    p3_wire_identity_in id;
    p3_wire_record_in r;
    p3_wire_summary_in s;
    uint32_t emitted, audited;
    size_t n;

    show("LINE", p3_wire_line("REC", 42u, "a13f38b53355fd4c1cac3145244727f8", "eyJhIjoxfQ", out, sizeof(out)));
    show("LINE_EMPTY", p3_wire_line("HB", 7u, "a13f38b53355fd4c1cac3145244727f8", NULL, out, sizeof(out)));
    show("LINE_SHORT", p3_wire_line("REC", 42u, "a13f38b53355fd4c1cac3145244727f8", "eyJhIjoxfQ", out, 20u));
    show("SIGNREQ", p3_wire_sign_request("a13f38b53355fd4c1cac3145244727f8", 3u, 17u,
                                         "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                                         0x0123456789abcdefull, out, sizeof(out)));
    show("AUDIT_READY", p3_wire_audit_ready(17u, "streams+readback", 4096u, 11u, 900u, out, sizeof(out)));
    n = p3_wire_sparse_entries(word_at, 0u, 384u, entries, sizeof(entries));
    printf("SPARSE %s\n", n ? entries : "<0>");
    show("AUDIT_SPARSE", p3_wire_audit_sparse(17u, 0u, 11u, "streams+readback", 4096u, 0u, 384u, entries, out, sizeof(out)));
    show("AUDIT", p3_wire_audit(17u, 2u, 11u, 768u, 384u, 4096u, "streams", "AAECAw", out, sizeof(out)));
    show("CLOSING", p3_wire_closing(0x9e3779b97f4a7c15ull, 0x9e3779b97f4a7c16ull, 0x2u, 0xf54u, out, sizeof(out)));
    show("HB", p3_wire_hb(15u, out, sizeof(out)));
    show("AUDITWAIT", p3_wire_audit_wait(17u, 10u, out, sizeof(out)));

    /* loop records: the evidence shapes of every outcome family, a baseline and a candidate */
    p3_wire_tally_reset();
    scored(&r, 2u);
    r.arm = "map_guided";
    r.search = "{\"pre\":\"rendered\",\"z\":[1,2]}";
    show("REC_SCORED", p3_wire_loop_record(&r, out, sizeof(out)));
    scored(&r, 1u);
    show("REC_BASELINE", p3_wire_loop_record(&r, out, sizeof(out)));
    scored(&r, 3u);
    r.arm = "random_safe";
    r.have_score = 0;
    r.outcome = "REFUSED_BY_PL";
    show("REC_REFUSED_PL", p3_wire_loop_record(&r, out, sizeof(out)));
    memset(&r, 0, sizeof(r));
    r.seq = 4u;
    r.genome = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    r.outcome = "REFUSED_BY_GATE";
    r.arm = "random_safe";
    r.have_sign_refusal = 1;
    r.finding_kinds = kinds;
    r.finding_kinds_n = 2;
    show("REC_GATE", p3_wire_loop_record(&r, out, sizeof(out)));
    memset(&r, 0, sizeof(r));
    r.seq = 5u;
    r.genome = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    r.outcome = "STOP_AUDIT";
    r.arm = "map_guided";
    r.have_audit_stop = 1;
    r.audit_stop_why = "retries exhausted";
    r.audit_chunks_served = 3u;
    show("REC_AUDIT_STOP", p3_wire_loop_record(&r, out, sizeof(out)));
    memset(&r, 0, sizeof(r));
    r.seq = 6u;
    r.genome = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    r.outcome = "STOP_SIGN";
    r.have_sign_stop = 1;
    r.sign_stop_attempts = 4u;
    r.sign_stop_why = "no ack";
    show("REC_SIGN_STOP", p3_wire_loop_record(&r, out, sizeof(out)));
    scored(&r, 7u);
    r.arm = "map_guided";
    r.search = "{\"pre\":\"rendered\"}";
    show("REC_SHORT", p3_wire_loop_record(&r, out, 100u));
    p3_wire_tally(&emitted, &audited);
    printf("TALLY %lu %lu\n", (unsigned long)emitted, (unsigned long)audited);

    memset(&s, 0, sizeof(s));
    s.token = "a13f38b53355fd4c1cac3145244727f8";
    s.kind = "COMPLETED";
    s.reason = "the session ran to its end";
    s.last_seq = 6u;
    s.scored = 2u;
    s.refused_by_gate = 1u;
    s.closing_restore = 1;
    s.closing_baseline = 1;
    s.closing_unsigned = 1;
    s.audited = emitted;
    s.total = emitted;
    s.crc_dropped = 1u;
    s.drop_budget = 8u;
    s.have_closing_control = 1;
    s.close_nonce_before = 0x9e3779b97f4a7c15ull;
    s.close_nonce_after = 0x9e3779b97f4a7c15ull;
    s.close_fault = 0x2u;
    s.close_status = 0xf54u;
    show("SUMMARY", p3_wire_summary(&s, out, sizeof(out)));
    s.kind = "STOPPED";
    s.closing_unsigned = 0;
    s.have_closing_control = 0;
    show("SUMMARY_STOPPED", p3_wire_summary(&s, out, sizeof(out)));

    memset(&id, 0, sizeof(id));
    id.pss_idcode = 0x13722093u;
    id.token = "a13f38b53355fd4c1cac3145244727f8";
    id.uboot_epoch = 5u;
    id.carrier_sha256 = "d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f";
    id.nonce_at_start = 0x9e3779b97f4a7c15ull;
    id.status_at_start = 0x900u;
    id.fclk0_hz_decoded = 50000000u;
    id.app_epoch = 2u;
    id.findings = findings;
    id.findings_n = 2;
    id.master_seed = 981420253u;
    id.schedule_mode = "b2-es-v1";
    id.operator_data_sha256 = "c6a4b23e1871e1889621191d671886f804c88edaa9748119d9a5006fd0b64296";
    id.protocol = "rel-v4";
    id.rec_retry_control = 1;
    id.sign_retry_control = 0;
    id.universe_sha256 = "895baf85ed31df9beae28a533646182ffb8d0e0735c9849ede9641af81ee7458";
    id.carrier_variant = 0x42310001u;
    id.search_version = "b2-es-v1";
    id.map_sha256 = "c6a4b23e1871e1889621191d671886f804c88edaa9748119d9a5006fd0b64296";
    id.fitness_id = "F1";
    id.budget_per_arm = 1000u;
    id.pairs_total = 8u;
    id.pair_first = 2u;
    id.pair_count = 3u;
#ifndef WIRE_B2
    id.carto_version = "specimen-carto-v1.1";
    id.arms = B3_WIRE_ARMS;
    id.b1_map_cost = B3_WIRE_B1_MAP_COST;
#endif
    show("IDENT", p3_wire_identity(&id, out, sizeof(out)));
    return 0;
}
