// The bench's fabric: a model of b4_target_slice that implements the behaviour hypothesis
// b4/hypothesis/ff_behaviour_v0.3.json for a 21-bit genome the bench sets (hierarchically), in the step order of
// b4/host/b4_ff_model.py. Same module name and ports as rtl/b4/b4_target_slice.v so b4_core / b4_top see no
// difference; this file is compiled INSTEAD of the RTL target in the bench (sim/b4/run.sh). It is the hypothesis,
// not silicon: a bench pass means the carrier reproduces the model (docs/b4_observation_contract.md 9.1, A2 / A8 row).
//
// Genome bit order = the mapping's address order (b4_ff_mapping.site_mapping().addresses):
//   0 sr_kind (FFSYNC: 1 = synchronous)      1 ff_srval A5FF (ZRST: 1 = SRVAL 0)   2 ff_srval B5FF
//   3 sr_mode (SRUSEDMUX: 1 = SR driven)     4 ce_mode (CEUSEDMUX: 1 = CE driven)  5 ff_srval C5FF
//   6 clock_mode (CLKINV: 1 = inverted, FF; latch: bit 1 = NOT inverted)           7 ff_srval D5FF
//   8 ff_srval AFF   9 ff_srval BFF   10 storage_kind (LATCH)   11 ff_srval CFF   12 ff_srval DFF
//   13 ff_init AFF  14 ff_init A5FF  15 ff_init B5FF  16 ff_init BFF  17 ff_init CFF  18 ff_init C5FF
//   19 ff_init D5FF  20 ff_init DFF                   (ZINI: 1 = INIT 0)
// Element order of d / q: AFF, A5FF, BFF, B5FF, CFF, C5FF, DFF, D5FF.
// An element that is not a storage element under the hypothesis (x5FF under a latch) drives 1'bx: the carrier
// samples a physical value there on silicon; the model has none (the D1 rule of the contract, 3.4).
`timescale 1ns/1ps
`default_nettype none
module b4_target_slice (
    input  wire       slice_clk,
    input  wire       ce,
    input  wire       sr,
    input  wire [7:0] d,
    output reg  [7:0] q,
    input  wire       gsr
);
    reg [20:0] genome = 21'd0;          // the bench sets this (dut.target.genome = ...)
    reg        gsr_init_effect = 1'b1;  // the bench may clear it (the hypothesis swap `init_no_effect`: a persisting fabric)

    // decode (b4_ff_hypothesis readings)
    wire        sync_sr   = genome[0];
    wire        sr_driven = genome[3];
    wire        ce_driven = genome[4];
    wire        clkinv    = genome[6];
    wire        latch     = genome[10];
    wire [7:0]  zrst = {genome[7], genome[12], genome[5], genome[11], genome[2], genome[9], genome[1], genome[8]};
    wire [7:0]  zini = {genome[19], genome[20], genome[18], genome[17], genome[15], genome[16], genome[14], genome[13]};
    wire [7:0]  init_v  = ~zini;        // ZINI = 1 <=> INIT = 0
    wire [7:0]  srval_v = ~zrst;        // ZRST = 1 <=> SRVAL = 0
    wire        ce_eff = ce_driven ? ce : 1'b1;          // tied high when not driven
    wire        sr_eff = sr_driven ? sr : 1'b0;          // tied low when not driven
    // the physical clock / gate: FF: inverted when CLKINV = 1; latch: bit 1 = not inverted, bit 0 = inverted (v0.3)
    wire        pclk = latch ? (clkinv ? slice_clk : ~slice_clk) : (clkinv ? ~slice_clk : slice_clk);
    wire [7:0]  applicable = latch ? 8'b01010101 : 8'hFF;   // under a latch the x5FF elements are not storage elements

    integer i;
    reg pclk_q = 1'b0;
    // the init event: Q := INIT on every applicable element (an atomic assignment — G6; the level effects
    // settle afterwards as they do in the model's first set step)
    always @(posedge gsr) begin
        if (gsr_init_effect)
            for (i = 0; i < 8; i = i + 1) q[i] <= applicable[i] ? init_v[i] : 1'bx;
    end
    // level effects: asynchronous SR (level, priority), latch transparency; evaluated whenever anything moves
    always @(*) begin
        if (!gsr) begin
            for (i = 0; i < 8; i = i + 1) begin
                if (!applicable[i]) q[i] = 1'bx;
                else if (sr_eff && (latch || !sync_sr)) q[i] = srval_v[i];        // async SR acts on level; a latch's SR is always async
                else if (latch && pclk && ce_eff) q[i] = d[i];                     // transparent while the gate is high and GE
            end
        end
    end
    // edges of the physical clock (flip-flops only)
    always @(posedge pclk) begin
        if (!gsr && !latch)
            for (i = 0; i < 8; i = i + 1) begin
                if (sr_eff && sync_sr) q[i] <= srval_v[i];                        // synchronous SR has priority over capture
                else if (!sr_eff && ce_eff) q[i] <= d[i];
            end
    end
    initial q = 8'bxxxxxxxx;   // never initialised until the first init event (the model's initial q is null)
endmodule
`default_nettype wire
