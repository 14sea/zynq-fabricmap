# B4 pre-work, unit 2b-1 — the model contract (2026-10-17)

The owner's authorisation and five rulings of 2026-10-17: mapping, hypothesis, model and deterministic
fixtures / tests only; the site fixed at `SLICE_X2Y25` (the mine site; no other site used for development);
no landscape exploration, no gate, no thresholds, no RTL, no board. Branch `b4-prework`.

| file | what |
|---|---|
| `b4/host/b4_ff_mapping.py` | the certificate mapping of `SLICE_X2Y25`: 22 feature names on 21 addresses (CLKINV / NOCLKINV one bit), every (element, semantic) once, numeric address order, the certificate `c69e419f…` pinned; the bit readings held to the certificate's specimen pairs, a disagreeing certificate refused by name |
| `b4/hypothesis/ff_behaviour_v0.1.json` | the behaviour hypothesis, `status: unverified`; sources by kind — six UNISIM models under `/home/test/Xilinx/2025.2/data/verilog/src/unisims` by path, sha256 and the lines adopted; the certificate by path and sha256; the project's decode assumptions — the eleven behaviour flags, the decode readings, `valid_configuration` / `applicable_semantics` / `observation_context` as three blocks |
| `b4/host/b4_ff_hypothesis.py` | the loader: shape, every source re-hashed (an absent source is a failure, not a skip), the decode through the hypothesis's own readings, the swap fixtures as new objects with their own digests |
| `b4/host/b4_ff_model.py` | the fabric: configuration + stimulus → trace, under a mapping and a hypothesis passed in separately; every observation starts from nothing; the trace records the complete context per readout; fixtures truth / permuted / dropout / six hypothesis swaps |
| `b4/IMPORT.json` | the seven new files with digests; the six external sources by root + digest; the certificate as a repository input |
| `docs/b4_architecture.md` v0.1.3 | the three contract corrections (§4.4 sources, §5.0 three contracts, §5.1 the complete context, §9 K10 fixed conditions and the seed anchor) and the 2b-1 row of §13 |

## Tests (`tests.txt`)

`python3 -B -m unittest -v b4.tests.test_b4_ff_mapping b4.tests.test_b4_ff_hypothesis b4.tests.test_b4_ff_model`:
**Ran 32, OK**, zero skip. Every expected trace in `test_b4_ff_model.py` was derived by hand from the
hypothesis file's adopted UNISIM lines and the plan's readings; three of the first hand derivations had the
element index wrong (BFF is index 2, CFF index 4; `d = 0x05` addresses AFF and BFF) and were corrected
against the UNISIM semantics, not against the model's output — the model was not changed.

Held: the init readout shows INIT and the SR readout shows SRVAL, and the two differ (INIT / SR as two
mechanisms); SR tied low when not driven; CE driven gates the capture, CE tied high does not, per element;
the capturing edge is the physical rising edge (the inverted clock captures on the slice clock's falling
edge, recorded per element); synchronous SR only at the edge, asynchronous SR at the level, FDPE preset;
latch transparency with the gate high and GE, hold with the gate low or GE low, the x5FF elements not
applicable (None) under a latch, LDPE preset; isolation (an observation starts from nothing; the init step
gives the value; a fresh fabric gives the same trace); the permuted fixture is the truth re-addressed and
not the truth; dropout addresses move nothing; every one of the six hypothesis swaps changes a trace the
truth would not; the trace carries the whole context and is deterministic and JSON-serialisable; the genome
order is the mapping's; the refusals of both loaders on temp copies (the committed files never touched).

## Mutants (`mutants.txt`; `build/wip/scratch_2026_10_17/b4_2b1_mutants.py`, ignored)

Hermetic whole-tree copies (`.git`, `build`, `evidence` excluded; the certificate copied in); a kill only
with Ran N > 0 and FAILED. **11 / 11 killed**: the model ignoring `ce_gates_capture`, ignoring the init
flag, the decode's polarity hard-coded, Q kept across observations, the NOCLKINV reading not checked, the
count and set checks gone, the latch flag ignored, synchronous SR acting at the level, x5FF applicable under
a latch, the clock inversion ignored, the permuted fixture equal to the truth. (A first mapping mutant that
made the loader refuse the real certificate in `setUpClass` ran zero tests and was replaced by the two
above — a refusal in a fixture is not a kill.)

## What this establishes, and only this

A model contract: the mapping is read from the certificate and nothing else; the hypothesis is a named,
hashed, unverified file the model consults for every behavioural choice; an observation is a replayable
trace that starts from nothing. Nothing about silicon, no landscape, no gate, no threshold, no number of
any kind that a later unit could be judged against.
