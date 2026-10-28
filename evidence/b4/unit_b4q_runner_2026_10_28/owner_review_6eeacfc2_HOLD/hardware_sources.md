# Primary sources used for the new clock check

Reviewed against AMD UG585 v1.15 (2026-02-06), retrieved for this review on 2026-10-28. These establish register semantics, not the state of any project board. No secondary-source hardware claim is used in the ruling.

- [IO_PLL_CTRL register details](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/Register-IO_PLL_CTRL-Details?contentId=6BqkscdadihuNAZVxMHx8g): bit 1 is PLL_PWRDWN; setting it powers down the PLL. Bit 3 selects whether the sampled BOOT_MODE bypass strap participates in bypass selection; bit 4 being clear does not alone establish non-bypass operation when qualification is enabled.
- [PLL_STATUS register details](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/Register-PLL_STATUS-Details): distinguishes lock from stable/bypass status. A feedback divisor is configuration, not a substitute for the selected PLL's operating state. Do not treat stable alone as proof of a multiplied PLL clock when bypass is possible.

The source audit/bring-up draft should identify the supported normal-clock assumptions and distinguish configured nominal frequency from physical measurement. The repair can conservatively refuse unsupported or unresolved states; it need not implement a general clock controller or configure hardware.
