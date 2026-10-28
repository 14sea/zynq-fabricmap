#!/usr/bin/env bash
# Build the B4Q standalone image (b4q_app.elf / .bin / .map) with the instrument's pinned xPack toolchain (read-only use of
# zynq-psoracle's toolchain directory) and the same hand-assembled Cortex-A9 standalone BSP from Xilinx 2025.2 embeddedsw
# sources that the B1 image uses (firmware/b1/bsp/build.sh, copied and re-pointed; B1's files stay untouched). Host-only:
# produces an ELF, a raw binary and the linker map under the top-level ignored build/ (the B3 rule); touches no board.
#
#   bash firmware/b4q/bsp/build.sh            # -> build/b4q_image/b4q_app.{elf,bin,map}
#   OUT=<dir> bash firmware/b4q/bsp/build.sh
#
# The image links the target's units (target/b4q_board_main.c, b4q_board_hal.c, b4q_app.c, b4q_wire.c, b4q_psmap.c) with the
# executing side (b4q_tx.c, b4q_cmd.c) and the derive unit (b4q_derive.c) — the SAME sources the host harness runs — and the
# console glue bsp/src/console.c (B1's, byte for byte). Load address 0x02000000 (lscript.ld), entry = the vector table there:
# the host loads the .bin at that address and `go`es there, as the instrument's L5 runner does (APP_LOAD_ADDR).
set -euo pipefail

REPO=$(cd "$(dirname "$0")/../../.." && pwd)
INSTRUMENT=${PSORACLE_ROOT:-/home/test/zynq_psoracle}
TC=$INSTRUMENT/toolchain/xpack-arm-none-eabi-gcc-14.2.1-1.1
CC=$TC/bin/arm-none-eabi-gcc
SA=${EMBEDDEDSW_STANDALONE:-/home/test/Xilinx/2025.2/data/embeddedsw/lib/bsp/standalone_v9_4/src}
WD=${EMBEDDEDSW_SCUWDT:-/home/test/Xilinx/2025.2/data/embeddedsw/XilinxProcessorIPLib/drivers/scuwdt_v2_6/src}
FW=$REPO/firmware/b4q
BSP=$FW/bsp
OUT=${OUT:-$REPO/build/b4q_image}
IMAGE=${IMAGE:-b4q_app_v2}            # v2: the evidence log and its pull (protocol b4q-v2); the v1 image 010f6a05... is history
for need in "$CC" "$SA/common/xil_io.h" "$WD/xscuwdt.h"; do
  [ -e "$need" ] || { echo "build input missing: $need (the pinned toolchain / embeddedsw sources are not available here: no image is produced)" >&2; exit 2; }
done
mkdir -p "$OUT"

ARCH="-mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard"
INC="-I$BSP/include -I$SA/common -I$SA/arm/common -I$SA/arm/common/gcc \
     -I$SA/arm/cortexa9 -I$SA/arm/cortexa9/gcc -I$WD"
BSP_CFLAGS="$ARCH -std=gnu11 -O2 -g $INC -DUSE_AMP=0 -ffunction-sections -fdata-sections"
APP_CFLAGS="$ARCH -std=c99 -O2 -g $INC -I$FW -I$FW/target -Wall -Wextra -Werror -ffreestanding -ffunction-sections -fdata-sections"

ASM_SRCS="arm/cortexa9/gcc/boot.S arm/cortexa9/gcc/cpu_init.S \
          arm/cortexa9/gcc/translation_table.S arm/cortexa9/gcc/xil-crt0.S \
          arm/cortexa9/gcc/asm_vectors.S"
C_SRCS="arm/cortexa9/xil_cache.c arm/cortexa9/xil_mmu.c arm/cortexa9/xil_misc_psreset_api.c \
        arm/cortexa9/xl2cc_counter.c arm/cortexa9/xtime_l.c \
        arm/common/vectors.c arm/common/xil_exception.c \
        common/xil_assert.c common/xil_printf.c common/print.c common/xil_mem.c \
        common/xil_sutil.c common/xil_util.c common/outbyte.c common/inbyte.c"
SYS_SRCS="arm/common/gcc/sbrk.c arm/common/gcc/_sbrk.c arm/common/gcc/write.c \
          arm/common/gcc/read.c arm/common/gcc/close.c arm/common/gcc/fstat.c \
          arm/common/gcc/isatty.c arm/common/gcc/lseek.c arm/common/gcc/_exit.c \
          arm/common/gcc/_open.c arm/common/gcc/open.c arm/common/gcc/unlink.c \
          arm/common/gcc/getpid.c arm/common/gcc/kill.c arm/common/gcc/errno.c \
          arm/common/gcc/abort.c"
WDT_SRCS="xscuwdt.c xscuwdt_g.c xscuwdt_sinit.c"
APP_SRCS="target/b4q_board_main.c target/b4q_board_hal.c target/b4q_board_console.c target/b4q_app.c target/b4q_wire.c target/b4q_psmap.c target/b4q_ring.c b4q_tx.c b4q_cmd.c b4q_derive.c"

OBJS=()
for s in $ASM_SRCS; do o="$OUT/$(echo "$s" | tr / _).o"; "$CC" $BSP_CFLAGS -c "$SA/$s" -o "$o"; OBJS+=("$o"); done
for s in $C_SRCS $SYS_SRCS; do o="$OUT/$(echo "$s" | tr / _).o"; "$CC" $BSP_CFLAGS -c "$SA/$s" -o "$o"; OBJS+=("$o"); done
for s in $WDT_SRCS; do o="$OUT/wd_$s.o"; "$CC" $BSP_CFLAGS -c "$WD/$s" -o "$o"; OBJS+=("$o"); done
"$CC" $BSP_CFLAGS -c "$BSP/src/console.c" -o "$OUT/console.o"; OBJS+=("$OUT/console.o")
for s in $APP_SRCS; do o="$OUT/$(echo "$s" | tr / _).o"; "$CC" $APP_CFLAGS -c "$FW/$s" -o "$o"; OBJS+=("$o"); done

CRTI=$("$CC" $ARCH -print-file-name=crti.o)
CRTBEGIN=$("$CC" $ARCH -print-file-name=crtbegin.o)
CRTEND=$("$CC" $ARCH -print-file-name=crtend.o)
CRTN=$("$CC" $ARCH -print-file-name=crtn.o)
"$CC" $ARCH -nostartfiles -Wl,--gc-sections -Wl,--build-id=none \
      -Wl,-T,"$BSP/lscript.ld" -Wl,-Map,"$OUT/$IMAGE.map" \
      -o "$OUT/$IMAGE.elf" "$CRTI" "$CRTBEGIN" "${OBJS[@]}" \
      -Wl,--start-group -lgcc -lc -lm -Wl,--end-group "$CRTEND" "$CRTN"
echo "LINK OK -> $OUT/$IMAGE.elf"
"$TC/bin/arm-none-eabi-size" "$OUT/$IMAGE.elf"
"$TC/bin/arm-none-eabi-objcopy" -O binary "$OUT/$IMAGE.elf" "$OUT/$IMAGE.bin"
echo "IMAGE  -> $OUT/$IMAGE.bin"
sha256sum "$OUT/$IMAGE.bin"
