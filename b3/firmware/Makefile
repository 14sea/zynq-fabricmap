# B3 firmware — host twin only (image stage 1: the cartographer).
#
# `make twin` builds the HOST driver (b3_carto_twin.c + b3_carto.c) that b3/tests/test_b3_carto_twin.py
# drives against b3/host/b3_carto.py. It is host tooling, not a board image; nothing here is
# cross-compiled (the board application and its build evidence are later stages).
#
# Build products go to the repository's top-level ignored build/ directory, never under b3/: the B3
# pin rule pins every regular file under b3/**/*, and a build product is not a pinned source.
#
# The cartographer is compiled with the board build's warning flags (-Wall -Wextra) plus -pedantic,
# -Wshadow, -Wstrict-prototypes, -Wmissing-prototypes, -Wconversion and -Werror: a construct the
# board compiler tolerates but the standard does not is still a defect here, and the unit must be
# clean under the strictest host warnings before it is ever cross-compiled.

CC      ?= cc
CFLAGS  ?= -std=c99 -O2 -Wall -Wextra -Werror -pedantic -Wshadow -Wstrict-prototypes -Wmissing-prototypes -Wconversion
BUILD   ?= $(abspath $(CURDIR)/../../build/b3_firmware)

.PHONY: twin clean
twin: $(BUILD)/b3_carto_twin

$(BUILD)/b3_carto_twin: b3_carto_twin.c b3_carto.c b3_carto.h
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -o $@ b3_carto_twin.c b3_carto.c

clean:
	rm -rf $(BUILD)
