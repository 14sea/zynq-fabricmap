#!/bin/bash
# docs/b4_sim5_execution_plan.md section 1 command (1), the one production batch; stdout/stderr/exit captured outside the tree.
S=/tmp/claude-1000/-home-test-xilinx/3dfc91a4-48ce-4b4c-8804-097fc0dfcbc7/scratchpad/sim5_exec
cd /home/test/zynq_fabricmap || exit 99
{ echo "HEAD $(git rev-parse HEAD)"; echo "CMD python3 -B b4/host/b4_sim.py --label b4-sim-5 --seeds 32 --deadline-s 3600"; echo "START_UTC $(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > $S/run_header.txt
python3 -B b4/host/b4_sim.py --label b4-sim-5 --seeds 32 --deadline-s 3600 > $S/run_stdout.txt 2> $S/run_stderr.txt
rc=$?
echo "EXIT $rc" > $S/run_exit.txt
echo "END_UTC $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $S/run_header.txt
exit $rc
