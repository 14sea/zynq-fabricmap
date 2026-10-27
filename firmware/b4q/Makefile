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

.PHONY: twin host xcheck clean
twin: $(BUILD)/b4q_derive_twin
host: $(BUILD)/b4q_host

$(BUILD)/b4q_derive_twin: b4q_derive_twin.c b4q_derive.c b4q_derive.h b4q_data.h
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -o $@ b4q_derive_twin.c b4q_derive.c

$(BUILD)/b4q_host: b4q_host_main.c b4q_tx.c b4q_derive.c b4q_tx.h b4q_hal.h b4q_derive.h b4q_data.h b4q_regmap.h
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -o $@ b4q_host_main.c b4q_tx.c b4q_derive.c

xcheck:
	@mkdir -p $(BUILD)/xcheck
	@if [ -x "$(XGCC)" ]; then \
	  $(XGCC) -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -std=c99 -O2 -Wall -Wextra -Werror -c b4q_derive.c -o $(BUILD)/xcheck/b4q_derive.o && \
	  $(XGCC) -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -std=c99 -O2 -Wall -Wextra -Werror -c b4q_tx.c -o $(BUILD)/xcheck/b4q_tx.o && \
	  echo "xcheck: b4q_derive.c and b4q_tx.c compile for cortex-a9 (objects only; no image, no link, no BSP)"; \
	else echo "xcheck: cross toolchain absent at $(XGCC)"; exit 2; fi

clean:
	rm -rf $(BUILD)
