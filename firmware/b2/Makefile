# B2 firmware — host twin only.
#
# `make twin` builds the HOST driver (b2_twin.c + b2_search.c + p3_derive.c) that
# tests/test_b2_twin.py drives against host/b2_search.py and host/b2_landscape.py. It is
# host tooling, not a board image. The board application (b2_app.c) is cross-compiled by
# firmware/b2/bsp/build.sh with the instrument's pinned xPack toolchain (read-only use).
#
# The pure unit is compiled with the board build's warning flags plus -pedantic -Werror: a
# construct the board compiler tolerates but the standard does not is still a defect here.

CC      ?= cc
CFLAGS  ?= -std=c99 -O2 -Wall -Wextra -Werror -pedantic
BUILD   ?= build

.PHONY: twin clean
twin: $(BUILD)/b2_twin

$(BUILD)/b2_twin: b2_twin.c b2_search.c b2_orch.c b2_wire.c p3_derive.c b2_search.h b2_orch.h b2_wire.h p3_derive.h p3_data.h
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -o $@ b2_twin.c b2_search.c b2_orch.c b2_wire.c p3_derive.c

clean:
	rm -rf $(BUILD)
