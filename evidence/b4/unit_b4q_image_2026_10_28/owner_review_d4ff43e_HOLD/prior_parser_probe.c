#include <stdio.h>
#include "b4q_cmd.h"
int main(void) {
 const char *cases[]={"TX mystery 0 0", "TX normal 100000000 0", "TX normal 0 1 100000000", "TX normal 0 0 GARBAGE",
 "TX normal 0 0 TASK aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 2 1 0 0 1",
 "TX normal 0 0 TASK aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 1 257 256 256 65537"};
 unsigned i;for(i=0;i<sizeof cases/sizeof cases[0];i++) {b4q_tx_command c;int ret=b4q_parse_tx(cases[i],&c);
 printf("case=%u ret=%d kind=%d genome=%u steps=%d first_step=%u task_n=%d task0=(%u,%u,%u,%u) input=%s\n",i,ret,c.kind,c.genome,c.n_steps,c.steps[0],c.task.n,c.task.step[0],c.task.elem[0],c.task.target[0],c.task.weight[0],cases[i]);}return 0;
}
