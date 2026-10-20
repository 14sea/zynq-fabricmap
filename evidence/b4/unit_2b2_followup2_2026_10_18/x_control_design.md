# Control X for B4-FF — a design note for review (2026-10-18; the owner's P1-3 on `2eae943`, corrected on the owner's X-A ruling on `8d2757a`)

**Standing: a note for the owner's review, not a change.** The implemented X stays as it is until ruled on; no new
control is implemented, explored or tuned here; nothing numerical about any arm is inferred.

## 1. What the implemented X does, and why it is a symmetry control

B3's control X permuted the **positions** of a specimen's behaviour delta (384 LUT positions) before the online
cartographer, so the cartographer attributed effects to the wrong positions and its map named wrong columns; the
shadow (the true deltas) proved the permuted cartographer was the same algorithm under the permutation.

The B4-FF port of that contract permutes the eight visible **lanes** (elements) of a specimen's q grid. The owner's
probe shows what that preserves: for every address, whether it has effect / no-effect / context-dependent evidence;
the *set* of lanes it affects, bijectively relabelled; and therefore which addresses affect the same singleton lane
and which affect several. `ObservationCarto.view()` groups addresses by exactly these properties, so X's groups are
the shadow's groups **as a partition of addresses**, in another order. The group move samples a group uniformly and
uses only its address membership; lane names never enter the fitness or the guided decisions. X therefore keeps the
information the operator uses. It is a **symmetry check of the relation / partition structure**: the cartographer's relations and the
partition of addresses are invariant under lane relabelling (a property worth keeping as a test), but the
transformation does not remove the map's usefulness and cannot carry the negative-control reading K2 / K3 assign
to X in `docs/b4_architecture.md` §9. *(Corrected on the owner's point 5: this is not a claim of fixed-seed
trajectory equality — a changed group ORDER can change which group a fixed RNG index chooses, so X's and O's
searches may differ while their maps are the same partition.)*

## 2. What a negative control must remove, under the same null contract

The operator uses one thing from the map: **which addresses are grouped together** (the partition). A negative
control must make that partition wrong while the cartographer's algorithm, its RNG, the specimens' fitness and
the search are untouched, and while a shadow proves the control is the same algorithm under a stated
transformation (the isomorphism contract).

### Option X-A — permute the ADDRESSES the cartographer sees (recommended)

Before X's cartographer ingests a specimen, the specimen's **genome bits are relabelled by a fixed derangement
π over the 21 addresses** (drawn once per run from a control seed, B3's Fisher–Yates-with-rejection rule); the
q grid is untouched. The cartographer then pairs genomes that differ in bit π(a) with the effects address a
actually produced: every seen effect is credited to address π(a), so the map's partition is the IMAGE of the
true partition under π. The search itself observes the true genome (the fitness is honest); only the map is
transformed — the same shape as B3's X and as B2's D.

**What the transformation does NOT guarantee (the owner's correction).** A derangement of the 21 addresses
does not guarantee a changed partition, nor groups with "nothing in common on the fabric". Counterexample, on
the certificate's partition (eight groups of two — one per element — and one group of five slice-wide bits):
swap the two addresses within every pair and rotate the five-address group cyclically. That π has no fixed
point and maps every group onto itself: X's partition equals the shadow's, and the group move is as useful as
O's. Scrambling can preserve some or all of the relevant structure; an X benefit is therefore not, by itself, a
logical proof that O's benefit did not come from grouping — it is evidence under the stated null, whose
strength depends on how much structure the drawn π actually destroyed, which is measured post hoc (§2.4) and
reported, never fed back.

*Isomorphism contract (the owner's point 4):* the shadow ingests the true genomes; per specimen, X's state
must equal the shadow's under π in FULL — the address identities (relation[π(a)] of X is relation[a] of the
shadow), the seen cells and presence cells, the pair counts, the contexts, the evidence references (the same
seqs), the unknown / no-effect / context-dependent states, the version and the multi-bit count. EXACT; a
mismatch is a defect of the control, not a result. The execution ledger keeps the TRUE candidate (the genome
the search observed); the transformed cartographer input is reconstructible from the fixed π and is never
stored as if it were observed.

*π is fixed blind (the owner's point 1):* drawn once per run from the control seed by the line's rule, BEFORE
any map is learned or seen, and never redrawn or rejected after inspecting whether it changes the real
partition or improves the null result; every generated control seed and permutation is retained in the record,
including the ones that happened to preserve structure.

*What it removes, what it keeps:* it maps the partition through π — which may or may not change it; it keeps
the algorithm, the specimen stream, the fitness, the RNG and the lane symmetry. *Reported post hoc, never fed
back (the owner's point 2):* for each run, whether π preserved the partition (the shadow's partition against
X's), and how many groups it moved; the gate's rows for X carry these residual-structure counts beside the
numbers. *Expected reading (a hypothesis for the gate, not a prediction here):* over the seeds, X's group moves
should not profit over R; if they do, the map's usefulness is not shown to come from its grouping — and a run
whose π preserved the partition is reported as such, not dropped and not used to pick another π.

*Tests at implementation (the owner's point 3):* a hand fixture with an explicitly partition-CHANGING π (the
transform does what it says: the partition differs, the full isomorphism holds), AND the partition-PRESERVING
derangement above as a counterexample (no fixed point, the same partition, the isomorphism still holds, the
"partition changed" report false) — the absence of a false guarantee is itself tested; no test requires every
generated π to change the partition.

### Option X-B — keep the lane permutation as a symmetry control; move the negative reading to D and a new online scramble

Rename the implemented X "S" (symmetry) with its own row (the relation / partition structure is
lane-invariant; isomorphism holds), and revise §9 so that the negative-control reading rests on **D** (the
frozen map with its addresses relabelled — already implemented for the frozen arm, with the same non-guarantee)
plus an **online** D built as in X-A. This is X-A plus bookkeeping; it keeps the symmetry test as evidence of a
property the line would otherwise lose.

### Option X-C — scramble the cells across elements (not recommended)

A fixed permutation of (step, element) cells that mixes elements across steps changes *which elements* an
address appears to affect, collapsing many addresses into the multi-element group. It changes the partition, but
by a structured collapse rather than a relabelling, so the shadow's isomorphism would have to be defined over
cells rather than lanes, and the control would conflate "wrong grouping" with "fewer groups". It removes
information in a way that is hard to state as a null.

## 3. Recommendation, and what is asked

Adopt **X-A** (address relabelling before the cartographer, the full shadow isomorphism under π over genome
bits, π fixed blind and retained, residual structure reported post hoc) as the negative control named by K2 /
K3, with the non-guarantee stated in §9 — scrambling can preserve structure; the reading is evidence under the
null, not a proof — and keep the implemented lane permutation as a separate symmetry check ("S") of the
relation / partition structure. Both follow B3's derangement rule; neither changes the operator, the fitness
or the search. The architecture document's §8 / §9 would then name X-A as X and add S. **None of this is
implemented or explored here** (the owner's ruling on `8d2757a`: a design basis only); the implementation is a
separately authorised follow-up with its own tests — the partition-changing hand fixture, the partition-
preserving counterexample, the full per-specimen isomorphism, the blind-π rule.
