/* b4q_psmap — see b4q_psmap.h. */
#include "b4q_psmap.h"
#include "b4q_regmap.h"
#include "b4q_derive.h"
#include "b4q_wire.h"

static int axi_readable(uint32_t off)
{
    switch (off) {
    case B4Q_STATUS: case B4Q_FAULT: case B4Q_Q_LIVE: case B4Q_IN_LIVE: case B4Q_SLOT_READ: case B4Q_SLOT_ADDR: case B4Q_WITNESS:
    case B4Q_TIMING: case B4Q_HEARTBEAT: case B4Q_NONCE_LO: case B4Q_NONCE_HI: case B4Q_VARIANT: case B4Q_STEP_IN:
    case B4Q_BASE_STATE: case B4Q_SLOT_IN_READ:
        return 1;
    default:
        return off >= B4Q_HW_COMMIT0 && off < B4Q_HW_COMMIT0 + 4u * B4Q_HW_COMMIT_WORDS && (off & 3u) == 0u;
    }
}

static int axi_writable(uint32_t off)
{
    if (off == B4Q_CTRL || off == B4Q_SLOT_ADDR || off == B4Q_STEP_IN) return 1;
    if (off >= B4Q_PAYLOAD0 && off < B4Q_PAYLOAD0 + 4u * B4Q_PAYLOAD_WORDS && (off & 3u) == 0u) return 1;
    if (off >= B4Q_TAG0 && off < B4Q_TAG0 + 4u * B4Q_TAG_WORDS && (off & 3u) == 0u) return 1;
    return 0;   /* the key window among the rest: the signer principal's, never this program's */
}

static int devcfg_reg(uint32_t a)
{
    uint32_t off = a - B4Q_PSMAP_DEVCFG_BASE;
    return a >= B4Q_PSMAP_DEVCFG_BASE && (off == 0x000u || off == 0x00Cu || off == 0x018u || off == 0x01Cu || off == 0x020u || off == 0x024u);
}

static int in_buffer(uint32_t a, uint32_t base, uint32_t words)
{
    return a >= base && a < base + 4u * words && (a & 3u) == 0u;
}

int b4q_psmap_readable(uint32_t addr)
{
    if (addr >= B4Q_PSMAP_AXI_BASE && addr < B4Q_PSMAP_AXI_BASE + B4Q_PSMAP_AXI_SIZE) return (addr & 3u) == 0u && axi_readable(addr - B4Q_PSMAP_AXI_BASE);
    if (devcfg_reg(addr)) return 1;
    if (addr == B4Q_PSMAP_SLCR_PSS_IDCODE) return 1;
    if (in_buffer(addr, B4Q_PSMAP_CMD_BUF, P3_READBACK_CMD_WORDS)) return 1;
    if (in_buffer(addr, B4Q_PSMAP_DST_BUF, P3_READBACK_WORDS)) return 1;
    if (in_buffer(addr, B4Q_PSMAP_WR_BUF, (uint32_t)P3_ENVELOPE_COUNT * P3_STREAM_WORDS)) return 1;
    if (in_buffer(addr, B4Q_PSMAP_PAGE_ADDR, B4Q_PAGE_WORDS)) return 1;
    return 0;
}

int b4q_psmap_writable(uint32_t addr)
{
    if (addr >= B4Q_PSMAP_AXI_BASE && addr < B4Q_PSMAP_AXI_BASE + B4Q_PSMAP_AXI_SIZE) return (addr & 3u) == 0u && axi_writable(addr - B4Q_PSMAP_AXI_BASE);
    if (devcfg_reg(addr)) return 1;
    if (in_buffer(addr, B4Q_PSMAP_CMD_BUF, P3_READBACK_CMD_WORDS)) return 1;
    if (in_buffer(addr, B4Q_PSMAP_DST_BUF, P3_READBACK_WORDS)) return 1;
    if (in_buffer(addr, B4Q_PSMAP_WR_BUF, (uint32_t)P3_ENVELOPE_COUNT * P3_STREAM_WORDS)) return 1;
    return 0;   /* the identity page is the host's (written before `go`), the IDCODE is read-only, the key window absent */
}
