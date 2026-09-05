#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "b1_carto.h"
#include "b1_wire.h"
static int mode_wire(void)
{
    static char out[8192];
    static char rec_out[8192];
    static b1_carto c;
    static char carto_json[2048];
    static char render[20480];
    p3_wire_identity_in in;
    p3_wire_record_in rec;
    static const char *tables[6] = {"0000000000000000", "0000000000000030", "0000000000000000",
                                    "0000000008000000", "0000000000001000", "0000000000000000"};
    uint16_t changed[8] = {284,285,286,287,288,289,290,291};
    int i;

    memset(&in, 0, sizeof(in));
    in.pss_idcode = 0x13722093u;
    in.token = "a13f38b53355fd4c1cac3145244727f8";
    in.uboot_epoch = 0;
    in.carrier_sha256 = "956379fa8d23f8a6f1e0c80fe18b8c4aee68e76cc650499911a4bdb7807e610a";
    in.nonce_at_start = 0x9e3779b97f4a7c15ull;
    in.status_at_start = 0x900u;
    in.fclk0_hz_decoded = 50000000u;
    in.app_epoch = 0;
    in.master_seed = 1123460948u;
    in.schedule_mode = "carto-v1";
    in.operator_data_sha256 = "895baf85ed31df9beae28a533646182ffb8d0e0735c9849ede9641af81ee7458";
    in.protocol = "rel-v4";
    in.rec_retry_control = 1;
    in.sign_retry_control = 1;
    in.carto_version = B1_CARTO_VERSION;
    in.universe_sha256 = "895baf85ed31df9beae28a533646182ffb8d0e0735c9849ede9641af81ee7458";
    in.probe_budget = 333u;
    in.carrier_variant = 0x42310001u;
    if (p3_wire_identity(&in, out, sizeof(out)) == 0u)
        return 7;
    printf("IDENT %s\n", out);

    b1_carto_init(&c, 1123460948u, 333u);
    b1_carto_bind(&c, "a13f38b53355fd4c1cac3145244727f8", "895baf85ed31df9beae28a533646182ffb8d0e0735c9849ede9641af81ee7458", 0x12345678u);
    for(i=0;i<B1_N;i++){c.e[i].lut=-1;c.e[i].init=-1;c.e[i].state=B1_ST_CONTRADICTION;c.e[i].code_mask=511;c.e[i].confirm_seq=335;c.e[i].observed=1;}
    c.probes_issued=333;c.anomalies=UINT32_MAX;c.pairs_n=32;
    for(i=0;i<32;i++){c.pairs[i].a=291;c.pairs[i].b=290;c.pairs[i].seq=334;c.pairs[i].result=2;}
    for(i=0;i<9;i++)c.code_seq[i]=i+2;
    if (b1_carto_render(&c, render, sizeof(render)) == 0u)
        return 8;
    if (b1_carto_record_json(&c, B1_PH_CODE, 2, changed, 8, carto_json, sizeof(carto_json)) == 0u)
        return 9;
    memset(&rec, 0, sizeof(rec));
    rec.seq = 2;
    rec.genome = "00000000000000000000000000000000000000000000000000000000000000000000000000000000";
    rec.outcome = "SCORED";
    rec.audited = 1;
    rec.arm = NULL;
    rec.carto = carto_json;
    rec.have_sign_reply = 1;
    rec.commit = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    for (i = 0; i < 6; i++) rec.tables[i] = tables[i];
    rec.tag = "88c45cf12e6857e7af54751d700e0f71";
    rec.have_oracle = 1;
    rec.staged_sha256 = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    rec.staged_stream_sha256 = "3ec0c49aed63997df3346caf51e92843d08df351b1dc15e215a8f1d82f2d02b9";
    rec.readback_sha256 = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    rec.envelopes_n = 3;
    rec.audit_available = 1;
    rec.have_arm = 1;
    rec.nonce_before = 0x9e3779b97f4a7c15ull; rec.nonce_after = 0xdc1b77ae0bf34dadull;   /* one xorshift64 step */
    rec.status_after = 0xf54u; rec.fault_after = 0; rec.key_loaded_observed = 1;
    rec.writes_issued = 25; rec.settle_polls = 16; rec.settle_polls_max = 1000000u; rec.settled = 1; rec.status_first = 0x901u;
    rec.have_score = 1;
    rec.hw_candidate_commit = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    for (i = 0; i < 6; i++) { rec.readout[i] = tables[i]; rec.scores[i] = 18u; }
    rec.hb_before = 1; rec.hb_after = 2;
    rec.seq=335;rec.settle_polls=1000000;rec.hb_before=UINT32_MAX;rec.hb_after=UINT32_MAX;
    rec.tag="88888888888888888888888888888888";
    for(i=0;i<6;i++)rec.scores[i]=UINT32_MAX;
    if (p3_wire_loop_record(&rec, rec_out, sizeof(rec_out)) == 0u)
        return 10;
    printf("REC %s\n", rec_out);
    printf("SIZES map=%zu carto=%zu record=%zu frame_bound=%zu\n",strlen(render),strlen(carto_json),strlen(rec_out),((strlen(rec_out)+2)/3)*4+60);
    char bounded[4096];
    if(!p3_wire_loop_record(&rec,bounded,sizeof(bounded)))return 11;
    return 0;
}


int main(void){return mode_wire();}
