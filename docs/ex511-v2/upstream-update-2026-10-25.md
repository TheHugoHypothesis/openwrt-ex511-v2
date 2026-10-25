# Kuncy7 integration — 25 October 2026

Merged c3po-tag-8021q through
[865da78e2ef7caee3d6854c0b353535413d878c9](https://github.com/kuncy7/openwrt-nss-edma/commit/865da78e2ef7caee3d6854c0b353535413d878c9),
17 commits after our previous 9caa35b4d718382ad882cb35c2372dbb569de901 base.
The merge retains upstream ancestry and our EX511 commits. Historical hardware
results describe older images; they do not validate this update on a router.

## Changes reviewed

Commit links below point to the original upstream changes and their evidence.

| Commits | Change and relevance |
| --- | --- |
| [ee8ec00e89](https://github.com/kuncy7/openwrt-nss-edma/commit/ee8ec00e89) | Correct HTT completion byte-offset arithmetic in ath11k. The previous struct-pointer addition could skip completions and leak queued packet buffers. Relevant to long-running dual-radio memory stability; upstream reports another board's results, not EX511 validation. |
| [55cbe825b4](https://github.com/kuncy7/openwrt-nss-edma/commit/55cbe825b4) | Stop only initialized ath11k TX rings when a radio shuts down. Relevant especially when NSS Wi-Fi offload is disabled. |
| [501040f6f2](https://github.com/kuncy7/openwrt-nss-edma/commit/501040f6f2) | Protect mesh next-hop reads and address lifetime with RCU/locking. Relevant when optional NSS mesh support is built and used. It does not enable mesh by itself. |
| [16b2dcae3d](https://github.com/kuncy7/openwrt-nss-edma/commit/16b2dcae3d), [68c3b4b876](https://github.com/kuncy7/openwrt-nss-edma/commit/68c3b4b876), [06157bbbc9](https://github.com/kuncy7/openwrt-nss-edma/commit/06157bbbc9) | Per-radio wifili traffic counters, mesh RX accounting and LuCI presentation. Better diagnostics; counters alone do not prove every flow is accelerated. |
| [f4764cdec1](https://github.com/kuncy7/openwrt-nss-edma/commit/f4764cdec1), [dcf8036648](https://github.com/kuncy7/openwrt-nss-edma/commit/dcf8036648) | Move NSS host-delivery interrupts with supported cellular modems, including Quectel drivers. Conditional on modem detection; not a new Ethernet-only EX511 policy. |
| [7cd522a286](https://github.com/kuncy7/openwrt-nss-edma/commit/7cd522a286), [91ab6f50ff](https://github.com/kuncy7/openwrt-nss-edma/commit/91ab6f50ff), [b0aa337b0a](https://github.com/kuncy7/openwrt-nss-edma/commit/b0aa337b0a) | QCA8K MIB frame validation, late-frame rejection, bridge flooding and VLAN-upper handling. Retained for other boards; EX511 uses a Realtek switch. |
| [f9b83dd621](https://github.com/kuncy7/openwrt-nss-edma/commit/f9b83dd621), [09217c4a61](https://github.com/kuncy7/openwrt-nss-edma/commit/09217c4a61) | CPU clock switching fixes and a final 1008/1296 MHz OPP table. Clock-driver changes retained, but EX511 deletes the 1296 MHz OPP: the overclock was tested upstream on GL-B3000, not this board. |
| [2299d07ea5](https://github.com/kuncy7/openwrt-nss-edma/commit/2299d07ea5) | Remove an RG-MA3063-specific PHY preset; does not change EX511 wiring. |
| [8f763c9430](https://github.com/kuncy7/openwrt-nss-edma/commit/8f763c9430), [865da78e2e](https://github.com/kuncy7/openwrt-nss-edma/commit/865da78e2e) | Add AX58 v2 and MX515v board support. Their calibration, flash layout and upgrade rules are not substituted for EX511 rules. |
| [ed1dea36df](https://github.com/kuncy7/openwrt-nss-edma/commit/ed1dea36df) | Document replacing basic wpad with mesh-capable wpad. No automatic package/configuration migration. |

## EX511 adaptations

The shared ipq5018 DTSI now offers an above-rated 1296 MHz operating point.
The EX511 base DTS removes it, inherited by all diagnostic/slot1/env-control
profiles. The compiled-tree validator follows the CPU OPP phandle and requires
exactly the rated 1008000000 Hz point. Enabling overclocking needs separate
board-specific thermal and stability evidence.

The new MX515v misc_ro preinit helper originally ran on any board with a
misc_data_ro partition. EX511 already has a serialized, validated read-only
factory-data path. Restrict the new helper to MX515v so it cannot attach/mount
EX511 factory data a second time. A shell fixture checks this boundary.

Resolve the image Makefile conflict by keeping both our three protected EX511
profiles and the new MX515v profile. Preserve EX511 MAC/calibration guards,
SGMII topology, partition offsets and slot1-only upgrade handling.
Feed pins and the Linux 6.18.55 kernel version remain unchanged in this update.

## Configuration and deployment boundary

This integration changes source only. No router commands, firmware writes,
reboots, boot-policy changes or UCI changes are performed. Existing PPPoE,
IPv6, Wi-Fi credentials, firewall settings and downstream topology remain on
the running firmware.

A later upgrade needs a matching protected slot1 image and a fresh external
configuration backup. Check sysupgrade's actual backup file list and validate
the image before any write. Do not use configuration-reset options such as
sysupgrade -n, or force incompatible images. Package installation and private
BDF provisioning are separate from UCI configuration: do not assume a saved
configuration archive includes them. Rebuild the private deployment image with
matching board data and verify it with --private-overlay as documented in
[the build guide](build-current.md). Public CI images omit that private data.

Source compatibility does not guarantee successful configuration migration or
hardware behavior. Installation is deliberately a separate controlled step;
this update does not install anything on the owner router.

## Validation

- Existing SSH preflight, factory MAC, calibration, slot1 upgrade and boot-policy fixtures pass locally; upgrade/boot-policy tests also use cached real host tools/ARM executables.
- New factory-hook fixture confirms EX511 and unrelated boards bypass the MX515v hook.
- All four EX511 DTS variants compile against an isolated copy of the prepared kernel with the three new clock patches applied. Compiled-tree checks verify rated frequency, radio settings, topology and all 17 partition protections.
- Upstream NSS status, topology-default and switch-init fixture suites pass locally.
- A fresh public CI build is required for this merged source. Its validation gates check actual kernel/modules, FIT/UBI/sysupgrade images and absence of private data before publishing a prerelease.
- No hardware test or upgrade of this revision has been performed. Repeat dual-band endurance, radio restarts, PPPoE/IPv6 renewals, NSS accounting and recovery tests after a separately reviewed installation.
