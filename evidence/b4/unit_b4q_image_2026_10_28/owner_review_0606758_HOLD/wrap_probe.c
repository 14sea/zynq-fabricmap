/* Original app, injected console; preserve production reply/heartbeat ratio (10 per attempt). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "b4q_app.c"
static unsigned first,last,count,wraps,polls;
static char tx[16384];static size_t tn;
void b4q_con_putc(char c) {
 if(tn+1<sizeof tx)tx[tn++]=c;
 if(c=='\n'){unsigned seq=0;tx[tn]=0;if(sscanf(tx,"B4Q1 %*s %u",&seq)==1){if(count&&seq<=last)wraps++;if(!count)first=seq;last=seq;count++;}tn=0;}
}
int b4q_con_rx_ready(void){polls++;return 0;}
char b4q_con_getc(void){return 0;}
int b4q_con_rx_flush(void){return 0;}
int b4q_plat_watchdog_start(void){return 0;}
void b4q_plat_kick(void){}
void b4q_plat_halt(void){exit(99);}
uint32_t b4q_rd32(uint32_t a,uint32_t*r){(void)a;*r=2;return 0;}
uint32_t b4q_wr32(uint32_t a,uint32_t d){(void)a;(void)d;return 2;}
int main(void){uint32_t words[24];int ret;strcpy(S.token,B4Q_WIRE_ZERO_TOKEN);S.seq=B4Q_APP_SEQ_LIMIT-1u;S.sum.lines=S.seq;S.sum.kicks_requested=S.seq;
 ret=b4q_sign("00000000","0000000000000000",words);
 printf("ret=%d initial_allowed_seq=0x%08x first=0x%08x last=0x%08x frames=%u wraps=%u polls=%u requests=%u final_end=%d\n",ret,B4Q_APP_SEQ_LIMIT-1u,first,last,count,wraps,polls,S.sum.sign_requests,S.sum.end);return 0;}
