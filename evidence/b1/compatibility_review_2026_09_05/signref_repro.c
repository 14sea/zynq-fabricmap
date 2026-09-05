#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "b1_orch.h"
enum {P3_RUNNING=0,P3_STOPPED=2};
static struct {int kind,refused;const char *rec_stop_why;} S;
static struct {int have_sign_refusal;const char *const *finding_kinds;int finding_kinds_n;} rec;
static int emit_record(void *r,const char *outcome){(void)r;(void)outcome;return 0;}
static void p3_stop(int kind,const char *why){(void)why;S.kind=kind;}
static int actual_signref_branch(void){const char *type="SIGNREF";
    if (!strcmp(type, "SIGNREF")) {
        /* a gate refusal is DATA, not a channel failure (§3c): the session continues.
         * NOT audited, and deliberately so: nothing was staged, so no raw words exist, and
         * this record makes no oracle self-report to check. Its evidence is the notary's
         * OWN refusal, which the host already holds and rule (vii) cross-checks — a
         * stronger corroboration than an audit, not a weaker one. */
        static const char *const refused_kind[] = {"gate_refusal"};
        S.refused++;
        rec.have_sign_refusal = 1;
        rec.finding_kinds = refused_kind;
        rec.finding_kinds_n = 1;
        if (emit_record(&rec, "REFUSED_BY_GATE") != 0) {
            p3_stop(P3_STOPPED, S.rec_stop_why); /* unacknowledged: no next candidate */
            return -1;
        }
        return 0;
    }
return -99;}
int main(void){b1_orch o;uint32_t a[10],b[10];uint64_t zero[6]={0};int is_b,kind;
b1_orch_init(&o,1123460948u,333u,"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","universe",0);
b1_orch_next(&o,a,&is_b,&kind);b1_orch_observe(&o,1,zero);
b1_orch_next(&o,a,&is_b,&kind);
int rc=actual_signref_branch();
int continues=S.kind==P3_RUNNING && rc==0;
int next=continues && b1_orch_next(&o,b,&is_b,&kind);
printf("SIGNREF rc=%d running=%d next_candidate=%d same_genome=%d probes_issued=%u\n",rc,S.kind==P3_RUNNING,next,next && memcmp(a,b,sizeof(a))==0,o.carto.probes_issued);
return !(rc==0 && next && memcmp(a,b,sizeof(a))==0);}
