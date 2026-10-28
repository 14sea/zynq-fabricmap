# B4Q executing side — host builds only (nothing here is cross-compiled into a board image; the board build and its
# evidence are a later stage, as firmware/b1/bsp/build.sh does for B1).
#
#   make twin      the derive twin (b4q_derive_twin.c + b4q_derive.c) for tests/test_b4q_derive.py
#   make host      the executing-side program b4q_tx.c driven on the host through the injected transport (b4q_host_main.c)
#   make xcheck    compile-only check of the pure units with the instrument's pinned cross toolchain, if present (no link, no image)
#
# Build products go to the top-level ignored build/ directory, never under firmware/ (the B3 rule).
# The units are compiled with the board build's warning flags plus -pedantic -Wshadow -Wstrict-prototypes -Wmissing-prototypes
# -Wconversion -Werror: a construct the board compiler tolerates but the standard does not is still a defect here.

CC      ?= cc
CFLAGS  ?= -std=c99 -O2 -Wall -Wextra -Werror -pedantic -Wshadow -Wstrict-prototypes -Wmissing-prototypes -Wconversion
BUILD   ?= $(abspath $(CURDIR)/../../build/b4q_firmware)
XGCC    ?= /home/test/zynq_psoracle/toolchain/xpack-arm-none-eabi-gcc-14.2.1-1.1/bin/arm-none-eabi-gcc

.PHONY: twin host apphost wiretwin waittwin seqcut xcheck clean
twin: $(BUILD)/b4q_derive_twin
host: $(BUILD)/b4q_host
apphost: $(BUILD)/b4q_apphost
wiretwin: $(BUILD)/b4q_wire_twin
waittwin: $(BUILD)/b4q_wait_twin
seqcut: $(BUILD)/b4q_seqcut_twin

APP_SRCS = target/b4q_app.c target/b4q_wire.c target/b4q_psmap.c target/b4q_ring.c b4q_tx.c b4q_derive.c b4q_cmd.c
APP_HDRS = target/b4q_app.h target/b4q_wire.h target/b4q_psmap.h target/b4q_ring.h target/b4q_console.h target/b4q_platform.h b4q_tx.h b4q_hal.h b4q_derive.h b4q_data.h b4q_regmap.h b4q_cmd.h
# the host harness waits in COUNTS of console polls like the board; the board's counts are the defaults in b4q_app.h, the harness's
# are small so that a silent host is a fast test, never a measured time on either
APP_HOST_BOUNDS = -DB4Q_APP_IDLE_POLLS=400000u -DB4Q_APP_REPLY_POLLS=200000u -DB4Q_APP_HB_EVERY=50000u

$(BUILD)/b4q_apphost: target/b4q_app_host.c $(APP_SRCS) $(APP_HDRS)
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -D_POSIX_C_SOURCE=200809L $(APP_HOST_BOUNDS) -I. -Itarget -o $@ target/b4q_app_host.c $(APP_SRCS)

$(BUILD)/b4q_wire_twin: target/b4q_wire_twin.c target/b4q_wire.c target/b4q_wire.h target/b4q_psmap.c target/b4q_psmap.h b4q_cmd.c b4q_cmd.h b4q_regmap.h b4q_derive.h
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -I. -Itarget -o $@ target/b4q_wire_twin.c target/b4q_wire.c target/b4q_psmap.c b4q_cmd.c

$(BUILD)/b4q_derive_twin: b4q_derive_twin.c b4q_derive.c b4q_derive.h b4q_data.h
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -o $@ b4q_derive_twin.c b4q_derive.c

$(BUILD)/b4q_host: b4q_host_main.c b4q_tx.c b4q_derive.c b4q_cmd.c b4q_tx.h b4q_hal.h b4q_derive.h b4q_data.h b4q_regmap.h b4q_cmd.h
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -o $@ b4q_host_main.c b4q_tx.c b4q_derive.c b4q_cmd.c

xcheck:
	@mkdir -p $(BUILD)/xcheck
	@if [ -x "$(XGCC)" ]; then \
	  $(XGCC) -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -std=c99 -O2 -Wall -Wextra -Werror -c b4q_derive.c -o $(BUILD)/xcheck/b4q_derive.o && \
	  $(XGCC) -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -std=c99 -O2 -Wall -Wextra -Werror -c b4q_tx.c -o $(BUILD)/xcheck/b4q_tx.o && \
	  for u in b4q_cmd.c target/b4q_app.c target/b4q_wire.c target/b4q_psmap.c target/b4q_ring.c; do $(XGCC) -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -std=c99 -O2 -Wall -Wextra -Werror -I. -Itarget -c $$u -o $(BUILD)/xcheck/$$(basename $$u).o || exit 1; done && \
	  echo "xcheck: b4q_derive.c, b4q_tx.c, b4q_cmd.c and the target's pure units compile for cortex-a9 (objects only; the image is bsp/build.sh's)"; \
	else echo "xcheck: cross toolchain absent at $(XGCC)"; exit 2; fi

clean:
	rm -rf $(BUILD)

# the receive-budget twin: the application's own b4q_sign / main-loop wait under injected console fixtures (a silent peer, a flood of
# stale replies, an overlong line, a flood of malformed lines), counting every readiness poll — tests/test_b4q_app.py::Bounds
$(BUILD)/b4q_wait_twin: target/b4q_wait_twin.c target/b4q_app.c $(APP_SRCS) $(APP_HDRS)
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -Wno-unused-function -DB4Q_APP_IDLE_POLLS=20000u -DB4Q_APP_REPLY_POLLS=10000u -DB4Q_APP_HB_EVERY=2000u -I. -Itarget -o $@ target/b4q_wait_twin.c target/b4q_wire.c target/b4q_psmap.c target/b4q_ring.c b4q_tx.c b4q_derive.c b4q_cmd.c

# the sequence-cut twin: the harness with the line sequence cut to its limit inside a transaction (R2) — tests/test_b4q_app.py
$(BUILD)/b4q_seqcut_twin: target/b4q_seqcut_twin.c target/b4q_app.c target/b4q_app_host.c $(APP_SRCS) $(APP_HDRS)
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -Wno-unused-function -D_POSIX_C_SOURCE=200809L $(APP_HOST_BOUNDS) -I. -Itarget -o $@ target/b4q_seqcut_twin.c target/b4q_wire.c target/b4q_psmap.c target/b4q_ring.c b4q_tx.c b4q_derive.c b4q_cmd.c
