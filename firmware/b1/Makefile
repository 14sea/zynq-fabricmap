# B1 firmware — host twin only.
#
# `make twin` builds the HOST driver (b1_twin.c + b1_carto.c + p3_derive.c) that
# tests/test_b1_twin.py drives against host/b1_carto.py over simulated fabrics. It is host
# tooling, not a board image. The board application (b1_app.c) is cross-compiled by
# firmware/b1/bsp/build.sh with the instrument's pinned xPack toolchain (read-only use).
#
# The pure unit is compiled with the same flags the board build uses for warnings, plus
# -pedantic -Werror: a construct the board compiler tolerates but the standard does not is
# still a defect here.

CC      ?= cc
CFLAGS  ?= -std=c99 -O2 -Wall -Wextra -Werror -pedantic
BUILD   ?= build

.PHONY: twin clean
twin: $(BUILD)/b1_twin

$(BUILD)/b1_twin: b1_twin.c b1_carto.c b1_wire.c p3_derive.c b1_carto.h b1_wire.h p3_derive.h p3_data.h
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -o $@ b1_twin.c b1_carto.c b1_wire.c p3_derive.c

clean:
	rm -rf $(BUILD)
