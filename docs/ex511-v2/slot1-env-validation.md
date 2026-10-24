# Slot1 environment-control image: offline validation — 22 October 2026

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

Subsequent [hardware validation](slot1-env-hardware-trial.md) installed this
exact image and tested bidirectional durable selection. The offline report
below records its preparation stage; it is not the current router state.

## Build identity and artifacts

Source: `ff5b0529bb8beffdcfb4f54d453799f4423d6f1f`, branch
`dev/ex511-v2-slot1-env-control`. Later commits containing this report and
additional host-side tests do not change the built firmware sources.

- OpenWrt SNAPSHOT `r0+37938-ff5b0529bb8` (literal packaged revision).
- Linux 6.18.55, AArch64 Cortex-A53; October 21 NSS baseline retained.
- NSS feed `5344fc35d79fc947b501e9feee5ced2b07c664fa`.
- Packages feed `baba60db0012a2a1a5fe5a079d58fc49e1b518be`.
- LuCI feed `580b6b1d9ec3a79edb8e2a5a9c4700b9c320ff6a`.
- Profile `tplink_ex511-v2-slot1-env`, compatibility 2.0.
- Extra ath11k NSS 256 MiB and low NSS allocation profiles retained.

`make defconfig` and `make -j6 V=s` completed successfully in the existing
space-free build checkout `<BUILD_DIR>`. This reused the
prepared toolchain/download/package caches; it was not a clean-from-scratch
build. The two unrelated pre-existing untracked Realtek target patches in
that checkout were preserved; they do not apply to qualcommax/ipq50xx.
Local host compiler/Perl environment is documented in [build.md](build.md).

Owner-specific artifacts remain local under
`ex511-v2-nss-build-artifacts/2026-10-22-slot1-env-control/` beside the source
tree, with complete config, kernel config, manifest, feed/build metadata,
build log and checksums. Private BDF redistribution is not established; no
firmware binary or factory capture was pushed to GitHub.

| Artifact suffix after `openwrt-qualcommax-ipq50xx-tplink_ex511-v2-slot1-env-` | Bytes | SHA256 |
| --- | ---: | --- |
| `squashfs-sysupgrade.bin` | 15125241 | `55f8f08b201bcf3c9b269ee665e0227e18ced2af8ae6ac984e567816ecd708ed` |
| `squashfs-factory.ubi` | 15990784 | `1a70398ef4744e40cb7f594c6ea270bbfbba266476b04b1d567e275081247f0c` |
| `initramfs-uImage.itb` | 14738316 | `5e5b694538b12e3ac53931e44394d74c5196a1b9137af938b95718ccf7b5c5a4` |

The factory UBI is not a signed stock-web installer. The initramfs uses the
same explicit writable-env DT; it must not be confused with the separate
all-read-only diagnostic profile.

## Confirmed offline

- The compiled DT has exactly the same hardware/partition definitions as the
  protected slot1 DT except for two properties: adding the env-control chosen
  marker and deleting APPSBLENV's read-only flag. All 17 offsets/sizes remain
  identical. Only APPSBLENV and rootfs_1 are writable.
- The final normal FIT uses `config@mp03.3`, with verified hashes. Its kernel
  expands to 14,905,352 bytes at 0x41000000, without overlapping the stock
  0x44000000 FIT input buffer. The normal kernel has no built-in initramfs.
- SquashFS and UBIFS/UBI block support are built in. Command-line MTD
  partitioning, a writable partitioned master and UBI gluebi are disabled.
- Factory UBI headers/table CRCs and LEB mappings pass. Kernel/root contents
  reconstruct exactly from the sysupgrade inputs, including format-specific
  padding. Initial volumes use 36/84/9 LEBs for kernel/rootfs/rootfs_data,
  leaving 160 physical PEBs before UBI's own reserves/autoresize accounting.
- Final assembled rootfs and the rootfs extracted from the actual sysupgrade
  archive contain expected Realtek, NSS, ath11k modules/firmware, matching
  private BDF provenance, factory helpers, flock, jshn, fwtool and envtools.
  The packaged upgrade guard matches its reviewed source byte-for-byte.
  Non-root host extraction excludes `/dev/console`; its character-device
  entry exists in SquashFS, but is not needed for offline executable tests.
- Ten upgrade test groups pass with host Bash and with the final packaged
  AArch64 BusyBox ash under QEMU. They cover both protection profiles,
  env geometry, metadata downgrade refusal, malformed image/boot arguments
  and routing every firmware target to rootfs_1 without boot metadata writes.
- The exact upgrade helper from the previously installed October 21 rootfs
  also accepts the new profile's transition metadata in a local fixture.
  The new archive retains the old board directory required by that helper.
- Twelve host controller test groups pass. Two run the final packaged ARM
  `fw_setenv` against temporary regular files under QEMU, verifying both
  policies, CRC/map preservation, lock contention and nested lock behavior.
  The added snapshot CLI test confirms private/exclusive read-only backup
  creation and refusal of an unmarked profile. No NAND device is used.
- Python syntax, shell syntax and `git diff --check` pass.

Build warnings retained from the baseline include missing module-description
metadata and DT unit-address/duplicate-unit-address warnings. There were no
fatal build errors. Two ignored Error 1 messages occurred in autoremove
cleanup (`touch -r` for already removed linux/nat46 build directories), not
compiler failures; the target and all three image outputs completed.

## Not performed in this preparation

No SSH upload, `sysupgrade -T` on the live router, flash, environment write,
reboot or default-policy change was performed. The current running image is
still the earlier hardware-tested protected slot1 build and stock remains
the saved boot default.

This new image has not booted on hardware. Actual in-place sysupgrade,
new-controller NAND writes/readback, selecting/reverting durable OpenWrt
policy and repeated cold/warm boot behavior still require separately
controlled hardware tests. There is no claim of power-fail-safe environment
updates or automatic rollback from a hanging kernel. Follow
[slot1-env-control.md](slot1-env-control.md) for the staged test procedure.
