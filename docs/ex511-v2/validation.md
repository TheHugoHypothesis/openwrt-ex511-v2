# NSS factory-data validation report — 20 October 2026

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

This report records the earlier offline migration/build validation. Subsequent
owner testing, including successful short Ethernet/Wi-Fi transfers and blocking
OOM/authentication findings, is recorded in [hardware-results.md](hardware-results.md).
Statements below about hardware not being tested refer to that earlier build
validation stage.

## Source and scope

Baseline: `kuncy7/openwrt-nss-edma`, branch `c3po-tag-8021q`, commit
`a915ef7f2d3f1500f455ed9e4721c0490349fe66`.
The validated images build from `5110b3c9868317337feb1289afe37dcc92cfa0d0`
plus the feed revisions in
`feeds.conf.default`. Later documentation/test corrections do not change
firmware contents. The previous branch at `0b926270fc2a` is preserved.

No router was accessed, rebooted, configured, flashed or supplied an image
during this migration. Owner stock observations referenced here were
collected read-only in earlier work. GitHub contains source and fixtures;
private BDF provisioning and generated images remain local.

## Confirmed by source inspection

- Linux 6.18.55 target; DWMAC IPQ5018, STMMAC, IPQ MDIO, QCA UNIPHY PCS,
  UBI and UBIFS are built in. Realtek DSA support is modular. The new board
  package explicitly depends on flock and ubi-utils.
- NSS firmware/driver/ECM, DWMAC glue, NSS Wi-Fi support and the 256M/LOW
  profiles are selected. All 34 requested non-metadata seed assignments
  survive `make defconfig` exactly.
- The switch remains family-D capable, CPU port 6, MDIO address 29,
  GPIO33 active-low reset and fixed SGMII 1000/full at both ends.
- Correction: C-3PO DSA/802.1Q support is already present in the inherited
  code and compiled kernel. A bound Realtek switch selects DSA defaults
  before the legacy EX511 flat-AP table. The current driver ignores the
  leftover headerless DTS property. WAN/LAN isolation is unverified on the
  owner's hardware, rather than absent from the code. A new fixture with
  only the Realtek driver bound confirms preservation of WAN/LAN defaults.
- Factory data is read by UBIFS filename, never a physical file offset.
  Attach has no format/recovery path. The MTD and UBI must be read-only.
  External EEPROM preparation only changes a RAM copy after validation.
- The integrated-radio zero-cal fallback, radio memory modes, reserved
  memory, boot arguments, recovery/upgrade code and partition flags are
  retained from the NSS baseline.

## Local execution and compilation evidence

- An EX511-specific addition to the NSS defaults suite passes with only
  `rtl8365mb-mdio` bound in fixture sysfs: DSA is selected and the separate
  WAN/LAN/IPv6 settings survive. No real sysfs or network configuration is
  modified by this test. This does not exercise switch hardware.
- 12 factory-MAC test groups pass under Bash and BusyBox ash: exact record
  format, rejection cases, read-only attachment/mount, ownership-aware
  cleanup, concurrent readers and Ethernet/radio address derivation.
- Six EEPROM/BDF groups pass under both shells. The C utility compiles
  with `-std=c11 -O2 -Wall -Wextra -Werror`. Tests cover corrupted/blank/
  truncated records, symlinks, bounded region/FEM parsing, atomic publication,
  preserving input/unrelated bytes/checksum and matching BDF provisioning.
- Six MAC provisioning groups pass with real AArch64 ucode under QEMU and
  BusyBox ash: expected conduit identity, no changes on unrelated boards or
  wrong devices, per-radio allocation, preservation of explicit settings,
  rejection of unsafe field strings and lookup independent of PHY order.
- A separate fixture using the actual ucidef/jshn implementation confirms
  both path arrays and MAC bases are serialized correctly to board JSON.
- The full board DTS compiles against the prepared target kernel. The DTB
  validator confirms the CPU link, switch topology, both firmware memory
  modes, removal of raw NVMEM MAC consumers and all 17 partition definitions.
- A separately compiled unmodified baseline DTB has identical partition
  labels, geometry and read-only flags. Both DTBs emit the same six warnings:
  three inherited NSS unit-address/simple-bus warnings and three duplicate
  qfprom cell unit-address warnings. No new DTS warning was introduced.

The full `make -j8 V=s` build completed successfully. The resulting images are:

| Image | Size | SHA256 |
| --- | ---: | --- |
| `openwrt-qualcommax-ipq50xx-tplink_ex511-v2-initramfs-uImage.itb` | 14,698,180 bytes | `59055bfd49bab0697143e0b472153a0e773aee9979e2f2dc564222efb33bc5e5` |
| `openwrt-qualcommax-ipq50xx-tplink_ex511-v2-squashfs-sysupgrade.bin` | 15,083,794 bytes | `bd17608a54b2cabe3260c6d3ecaae9d0d7eae51ba48f6af71fcb71aedb38cee8` |

- Kernel, IPQ5018 DWMAC, QCA UNIPHY, Realtek DSA, NSS DWMAC glue,
  qca-nss-drv, ECM, NSS clients and ath11k compile successfully.
- The NSS service is enabled at S19, before network S20; the EX511 MAC hook
  is registered before preinit networking. This confirms the intended order
  in the assembled filesystem, not probe/initialization timing on hardware.
- The manifest and assembled rootfs include `ex511-v2-factory`, flock,
  ubi-utils, `nss-tools-dwmac`, NSS firmware, NSS/ath11k/Realtek modules,
  the preinit hook and the radio/board helpers. The ath11k module contains
  its `nss_offload` parameter. This proves inclusion, not runtime offload.
- Rootfs validation follows absolute alternatives symlinks inside the
  image rather than against the host (flock -> util-linux-flock).
- The actual initramfs FIT DTB passes the same topology/partition checks;
  its default configuration is `config@mp03.3`.
- The private external-radio BDF's provenance hash matches the assembled
  rootfs, the initramfs CPIO and the sysupgrade SquashFS contents.
- The packaged AArch64 calibration utility runs under QEMU: valid checksum
  verification, RAM-copy preparation, source preservation and rejection of
  blank input/overwriting an existing output all pass. The final image's
  AArch64 ucode also passes all six provisioning fixture groups.

The first compiled image failed the BDF provenance check: ipq-wifi uses
`install-overlay`, whose post-install stage replaced a plain `files/` BDF
with the packaged reference BDF. The importer now provisions both the final
path and the `rootfs-overlay/` staging path, and its tests exercise that
ordering. Both images were rebuilt; only the passing rebuilt hashes above
are retained as test candidates.

Local artifacts, manifests, package repository, source/feed state, complete
configuration and logs are saved in `../ex511-v2-nss-build-artifacts/2026-10-20/`
relative to this checkout. They are not uploaded to GitHub. The firmware
contains a locally extracted BDF and has not been granted redistribution
rights or tested on physical hardware.

## Build environment findings

The first build stopped while quilt 0.69 generated a manual page:
`/usr/bin/pod2man` used Perl 5.44 with inherited modules for Perl 5.36.
A local pod2man wrapper invoking the cached compatible interpreter resolved
it. This required no target or firmware patch. Host GCC 13.2 was used;
the separately built target toolchain is GCC 14.4.0 with musl 1.2.6.

`make defconfig` emits inherited recursive-dependency diagnostics from
unselected feed packages and NSS metadata, returns success and retains
all requested symbols. These diagnostics are not a clean Kconfig report;
configuration selection was independently checked. Build logs retain the
messages. Some upstream host-tool configure probes and optional documentation
clean/install steps also emit ignored diagnostics; fatal errors must be
distinguished from these probes.

## Previously demonstrated by contributors

The [original EX511 contribution](https://github.com/kuncy7/openwrt-nss-edma/pull/3)
and this baseline's `README.ipq50xx.md`/DTS document Ethernet traffic at
SGMII 1G, port mapping, both radios, memory tuning, NAND boot and NSS AP
operation on another EX511. These are contributor reports, not tests on the
owner's unit or this factory-data build. Their earlier firmware 12.2 results
do not validate the selected firmware 12.5 on a 256 MB board.

## Requires physical validation / unresolved

- Boot and cleanup timing of read-only factory attachment on this unit;
  conduit MAC assignment before NSS; actual AP/guest/STA addresses.
- Full bidirectional wired traffic, all jacks, cold/warm reset behavior,
  error counters and NSS firmware/ECM counters proving offload.
- Owner BDF/EEPROM combination, QMI board-ID match, scan/RX/TX quality,
  country/channel/power behavior, simultaneous radios and long load tests.
- Integrated-radio factory calibration has not been validated; the tested
  baseline fallback is retained instead of inventing an EEPROM layout.
- Firmware 12.5 memory behavior and stability with NSS on 256 MB.
- Hardware validation of C-3PO WAN/VLAN isolation under NSS, including
  bidirectional routing and PPPoE. The legacy flat fallback and any saved
  old topology must be distinguished from fresh DSA defaults.
- 2.5G CPU link; LED details.
- A reviewed installation path from stock, slot-selection metadata and UART
  recovery. No generated file is approved for stock-web or SSH flashing.

Follow [hardware-test-plan.md](hardware-test-plan.md). Compilation cannot
verify Ethernet, Wi-Fi, hardware acceleration or flashing safety.

## Later authorized SSH trial

The earlier no-device-access statement describes the baseline migration
above. Subsequent owner-authorized stock inspection, backup, boot-selection
dry run and inactive-slot work are recorded separately in
[ssh-trial.md](ssh-trial.md). Do not infer hardware success from the earlier
build results.
