# Attribution and technical provenance

This is a continuation/integration of existing community work, not a claim
that this fork invented IPQ5018 Ethernet, Realtek support, NSS or ath11k.

| Source / contributor | Contribution used here |
| --- | --- |
| [OpenWrt](https://github.com/openwrt/openwrt) and Linux developers | Build system, kernel/userspace, DSA, ath11k and platform infrastructure |
| [fl1ck3r EX511 branch](https://github.com/fl1ck3r/openwrt/tree/tplink-ex511-v2) | Original EX511 board investigation and early boot/NAND/2.4-GHz port used at the start |
| [gusfm EX511 work](https://github.com/gusfm/openwrt-nss-edma) | Existing EX511 support on the IPQ50xx NSS tree, switch/memory contributions and hardware findings |
| [kuncy7 NSS tree](https://github.com/kuncy7/openwrt-nss-edma) and [matching feed](https://github.com/kuncy7/nss-packages/tree/ipq50xx-rebase) | Adopted IPQ5018 upstream-DWMAC/DSA + downstream NSS/ECM/ath11k integration and subsequent fixes |
| Julius Bairaktaris and NSS contributors | Earlier vendor NSS stack integration underpinning this branch; current [PPE-NSS project](https://github.com/JuliusBairaktaris/openwrt-ppe-nss) has a different hardware scope |
| George Moussalem and upstream contributors | IPQ5018 Ethernet/PCS and MultiPD/ath11k work carried by the baseline |
| Archer AX55 contributors / [wiki](https://openwrt.org/toh/tp-link/archer_ax55_v1) | Reference for related SoC/switch work and the inactive-slot/serial-free idea; board layout/recovery/RX-gap claims do not transfer automatically |
| TheHugoHypothesis owner project | Factory-file MAC/calibration checks, protected slot1 profiles, reviewed boot selection, private stock analysis, SSH installation and owner test reports |

The original EX511 contribution recorded in our adopted baseline is commit
`fee402cdf729cce626938dafab277472e4d12465`. The initial adopted NSS snapshot
was `a915ef7f2d3f1500f455ed9e4721c0490349fe66`; the later October 21 baseline
comparison and feed pins are recorded in
[upstream-comparison-2026-10-21.md](upstream-comparison-2026-10-21.md) and
[slot1-env-validation.md](slot1-env-validation.md).

## What this fork adds

- Read MAC/calibration by UBIFS filenames instead of a fragile physical offset.
- Validate EEPROM length/header/checksum and regional/FEM BDF matching; only
  modify RAM copies, preserving factory NAND.
- Provision MAC bases before the NSS conduit starts and through radio setup.
- Separate all-read-only diagnostic, protected persistent slot1 and explicit
  environment-control profiles, without replacing the board hardware wholesale.
- Guard sysupgrade targets/metadata so firmware writes remain in rootfs_1.
- Plan/verify boot selection with exact environment CRC/map/tail checks,
  standard-tool locking, private backups and no automatic reboot.
- Document actual SSH install, readbacks, preserved stock, recovery entry,
  memory failures and bounded hardware traffic results honestly.

The board was already supported in the adopted NSS base. A claim of "first
EX511 OpenWrt port" or "first SSH installation ever" is not established by
our work. We demonstrate this path on one unit and credit the reference idea.

## Licenses and private data

Existing component/SPDX notices remain in force. A repository-level README
does not relicense Linux, OpenWrt, firmware, vendor BDFs or stock extracts.
No proprietary decompiled source or newly extracted BDF/calibration binary
is added by this publication. Reproduction requires locally obtained matching
board data; redistributability must be established separately before any
binary release. Keep raw factory/firmware captures and credentials private.
