/* Reviewer fixture: compile original app unmodified; cap the fixture, not the app. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "b4q_app.c"
static unsigned polls_seen, replies, rxseq;
static int mode, enabled;
static char rx[1024], tx[16384];
static size_t rn, rp, tn;
void b4q_con_putc(char c) {
 if(tn+1<sizeof tx) tx[tn++]=c;
 if(c=='\n') {tx[tn]=0; if(strstr(tx,"B4Q1 SIGNREQ ")==tx) {replies++;enabled=1;} tn=0;}
}
int b4q_con_rx_ready(void) {
 if(++polls_seen>100000) {printf("OVER_BUDGET mode=%d polls=%u requests=%u frames=%u kicks=%u\n",mode,polls_seen,replies,rxseq,S.sum.kicks_requested);exit(77);}
 return mode && enabled;
}
char b4q_con_getc(void) {
 if(mode==2) return 'X';
 if(rp==rn) {const char *p="OK 999"; rn=b4q_wire_frame("SIGNREPLY",++rxseq,S.token,(const uint8_t*)p,strlen(p),rx,sizeof rx);rp=0;}
 return rx[rp++];
}
int b4q_con_rx_flush(void) {enabled=0;rp=rn=0;return 0;}
int b4q_plat_watchdog_start(void) {return 0;}
void b4q_plat_kick(void) {}
void b4q_plat_halt(void) {exit(99);}
uint32_t b4q_rd32(uint32_t a,uint32_t *resp) {(void)a;*resp=2;return 0;}
uint32_t b4q_wr32(uint32_t a,uint32_t v) {(void)a;(void)v;return 2;}
int main(int argc,char **argv) {uint32_t words[24]; int ret;
 mode=argc>1?atoi(argv[1]):0; strcpy(S.token,B4Q_WIRE_ZERO_TOKEN);
 ret=b4q_sign("00000000","0000000000000000",words);
 printf("RETURN mode=%d ret=%d polls=%u requests=%u frames=%u\n",mode,ret,polls_seen,replies,rxseq);return 0;
}
