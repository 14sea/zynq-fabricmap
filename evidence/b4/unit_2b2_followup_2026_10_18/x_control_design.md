# Control X for B4-FF — a design note for review (2026-10-18; the owner's P1-3 on `2eae943`)

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
information the operator uses. It is a **symmetry control**: it shows the cartographer and the operator are
invariant under lane relabelling (a property worth keeping as a test), but it does not remove the map's usefulness
and cannot carry the negative-control reading K2 / K3 assign to X in `docs/b4_architecture.md` §9.

## 2. What a negative control must remove, under the same null contract

The operator uses one thing from the map: **which addresses are grouped together** (the partition). A negative
control must make that partition wrong while the cartographer's algorithm, its RNG, the specimens' fitness and
the search are untouched, and while a shadow proves the control is the same algorithm under a stated
transformation (the isomorphism contract).

### Option X-A — permute the ADDRESSES the cartographer sees (recommended)

Before X's cartographer ingests a specimen, the specimen's **genome bits are relabelled by a fixed derangement
π over the 21 addresses** (drawn once per run from a control seed, B3's Fisher–Yates-with-rejection rule); the
q grid is untouched. The cartographer then pairs genomes that differ in bit π(a) with the effects address a
actually produced: every seen effect is credited to the wrong address, the partition of addresses is π of the
true one, and a group move picks sets of addresses that have nothing in common on the fabric. The search itself
observes the true genome (the fitness is honest); only the map is wrong — the same shape as B3's X and as B2's D.

*Isomorphism contract:* the shadow ingests the true genomes; X's relations must equal the shadow's with every
genome bit mapped through π (relation[π(a)] of X equals relation[a] of the shadow, cells and presence equal,
counts and evidence equal, version equal). EXACT per specimen; a mismatch is a defect of the control, not a
result. *What it removes:* the address partition. *What it keeps:* the algorithm, the specimen stream, the
fitness, the RNG, the lane symmetry. *Expected reading (a hypothesis for the gate, not a prediction here):*
X's group moves should not profit over R; if they do, the map's usefulness does not come from its grouping.

### Option X-B — keep the lane permutation as a symmetry control; move the negative reading to D and a new online scramble

Rename the implemented X "S" (symmetry) with its own row (the cartographer and operator are lane-invariant;
isomorphism holds), and revise §9 so that the negative-control reading rests on **D** (the frozen map with its
addresses relabelled — already implemented for the frozen arm) plus an **online** D built as in X-A. This is
X-A plus bookkeeping; it keeps the symmetry test as evidence of a property the line would otherwise lose.

### Option X-C — scramble the cells across elements (not recommended)

A fixed permutation of (step, element) cells that mixes elements across steps changes *which elements* an
address appears to affect, collapsing many addresses into the multi-element group. It changes the partition, but
by a structured collapse rather than a relabelling, so the shadow's isomorphism would have to be defined over
cells rather than lanes, and the control would conflate "wrong grouping" with "fewer groups". It removes
information in a way that is hard to state as a null.

## 3. Recommendation, and what is asked

Adopt **X-A** (address relabelling before the cartographer, shadow isomorphism under π over genome bits) as
the negative control named by K2 / K3, and keep the implemented lane permutation as a separate symmetry test
("S") whose expected outcome is equality, not a loss. Both follow B3's derangement rule; neither changes the
operator, the fitness or the search. The architecture document's §8 / §9 would then name X-A as X and add S.
**None of this is implemented or explored here**; the decision — X-A, X-B, or a revision of the negative-control
requirement itself — is the owner's, and the implementation would be a separately authorised follow-up with its
own tests (the hand-ledger probe of the owner's review becomes a test: under X-A the partition must differ).
