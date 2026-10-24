# SquashFS root on physical slot 1 — owner SSH installation candidate

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

Current owner state: the separate [slot1-env follow-up](slot1-env-hardware-trial.md)
is now installed and OpenWrt is the saved default. This document describes
the original protected slot1 profile, which still remains available.

## Purpose and current status

The `tplink_ex511-v2-slot1` profile is intended to run the root filesystem
from NAND instead of keeping the unpacked initramfs in RAM. It retains the
October 21 NSS base, the extra 256 MiB ath11k allocation profile and the
owner's factory-data provisioning. It is an installation candidate, not a
stock web image or a production-ready installation.

The owner's subsequent [NAND-root trial](nand-root-hardware-trial.md)
confirmed SquashFS/UBIFS boot, the protection flags, an actual return to stock
and saved configuration surviving a second slot1 boot. OpenWrt is still
selected through the one-shot policy; load stability and an actual in-place
sysupgrade remain unverified.

See [oct21-slot1-validation.md](oct21-slot1-validation.md) for the compiled
revision, final image hashes, completed checks and remaining hardware tests.

Our previous initramfs used approximately 34 MiB of shmem for its unpacked
filesystem. A SquashFS root can reclaim file-cache pages and stores writable
configuration in a UBIFS overlay. The linked hardware report records measured
Shmem and idle MemAvailable. Radio stability and OOM behavior under load still
require testing; they cannot be inferred directly from the SquashFS file size.

Build preparation did not write the router. The later authorized hardware
trial replaced the diagnostic image in slot 1 and used the existing one-shot
flag; stock slot 0 and the wrapper itself were preserved.

## Why physical slot 1 can work

The inherited EX511 upgrader assumed boot selection through the Qualcomm
BOOTCONFIG table. Its comments describe a bootloader partition-name swap:
Linux's fixed `rootfs` label would then still resolve to physical slot 0.
That led to an upgrader which pinned slot 0 and modified critical boot tables.

The owner-specific SSH work established a different route. Stock U-Boot's
`tp_boot_idx=1` selects physical `rootfs_1` without that BOOTCONFIG change.
A read-only SSH check on the running second trial confirmed:

```text
ubi.mtd=rootfs_1 root=mtd:ubi_rootfs rootfstype=squashfs rootwait ...
```

Sysfs independently reported `rootfs` at decimal 19136512 (`0x1240000`) and
`rootfs_1` at 57278464 (`0x36a0000`), each 38141952 bytes, erase size 131072.
This is observed on the owner's bootloader; do not generalize to every
EX511 revision or bootloader.

The persistent profile retains those physical labels and the base DTS's
appended `root=/dev/ubiblock0_1`. When only `ubi.mtd=rootfs_1` is attached,
UBI device 0 is physical slot 1. Its OpenWrt volumes are kernel ID 0,
SquashFS rootfs ID 1 and autoresizing rootfs_data ID 2. The appended root
argument overrides stock's earlier root name. This complete NAND-root handoff
was subsequently observed twice on the owner's unit.

## Protection and sysupgrade behavior

The new DTS adds a chosen marker identifying the slot1 layout. Only physical
`rootfs_1` is writable; all other 16 partitions, including stock `rootfs`,
APPSBLENV, both BOOTCONFIG copies and all factory/calibration data, are
read-only. Partition geometry, network topology and radio definitions are
unchanged. There is no partition renaming or raw factory-data offset.

The unsafe inherited EX511 BOOTCONFIG writer was removed. The new handler
checks before writing, including again in sysupgrade's RAM stage:

- The dedicated slot1 DT marker and exactly 17 physical MTDs.
- Expected sizes, erase sizes and offsets for both firmware slots.
- Only `rootfs_1` writable, all other effective flags read-only.
- Exactly one UBI command-line selection, `ubi.mtd=rootfs_1`.
- Firmware metadata compatibility version 2.0 and the explicit
  `tplink,ex511-v2-slot1` supported-device marker.

It assigns kernel, root and overlay upgrade targets exclusively to
`rootfs_1`. It never changes boot tables, bootcmd or environment variables.
The normal/read-only legacy profiles refuse this upgrade path. A generic
release image lacks the slot1 metadata and is refused even by the RAM-stage
handler. Do not try to bypass a refusal with `sysupgrade -F`.

The board retains its original compatible string, so factory helpers and
network defaults still apply. Fresh configuration on the marked profile
gets compatibility version 2.0. The extra slot1 supported-device marker
distinguishes its image from the ordinary physical-slot-0 image.

## Root persistence and boot persistence are different

| Bootloader policy | Root during a successful slot1 boot | Next reboot |
| --- | --- | --- |
| Existing one-shot wrapper, flag armed once, durable slot override absent | NAND SquashFS + writable slot1 overlay | Preserved stock slot 0 |
| One-shot wrapper disarmed, slot override absent | Stock | Stock |
| Durable `tp_boot_idx=1` with a compatible bootcmd | NAND SquashFS + slot1 overlay | Slot 1 again |

The **first** test used the existing one-shot wrapper. This gives a
real persistent root and persistent overlay while keeping the next reset's
selection at stock. It does not make OpenWrt the default boot target.

Sysupgrade leaves that policy unchanged: if used during a one-shot slot1
boot, it updates slot 1 but its reboot returns to stock. Slot 1 must then be
armed again from stock SSH. Automatic boot to OpenWrt requires a separate,
reviewed environment change after successful root and recovery tests.

The owner still lacks reliable UART input. An intact stock image is not by
itself proof that it can be selected after an arbitrary kernel hang when
OpenWrt has been made the default. Do not enable permanent slot selection
or claim a fully working A/B rollback system based on these source changes.

The subsequent [22 October recovery investigation](recovery-without-uart-input.md)
hardware-tested Reset entry and the bootloader HTTP page without UART input.
An actual stock restoration upload and a slot-switch interface from the
protected OpenWrt profile remain untested/unimplemented respectively.

## Build and offline validation

Use a path without spaces and import the owner's private BDF as described
in [build.md](build.md). The updated source pins the packages/LuCI revisions
from the October 21 release and keeps the same NSS feed revision.

```sh
cp configs/ex511-v2-slot1.config .config
./scripts/feeds update -a
./scripts/feeds install -a
make defconfig
make -j6 V=s
python3 scripts/ex511-v2/test-slot1-upgrade.py --host-tools staging_dir/host
python3 scripts/ex511-v2/validate-nss-build.py \
  --slot1 \
  --dtb build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/image-ipq5018-tplink-ex511-v2-slot1.dtb \
  --rootfs build_dir/target-aarch64_cortex-a53_musl/root-qualcommax \
  --private-overlay
python3 scripts/ex511-v2/check-slot1-image.py \
  --sysupgrade bin/targets/qualcommax/ipq50xx/openwrt-qualcommax-ipq50xx-tplink_ex511-v2-slot1-squashfs-sysupgrade.bin \
  --ubi bin/targets/qualcommax/ipq50xx/openwrt-qualcommax-ipq50xx-tplink_ex511-v2-slot1-squashfs-factory.ubi \
  --kernel-config build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/linux-6.18.55/.config.set \
  --fwtool staging_dir/host/bin/fwtool
```

The factory UBI and sysupgrade both contain the **normal kernel**, not the
built-in-rootfs initramfs kernel. The standalone initramfs output is a
different artifact. The offline checker verifies metadata, FIT hashes and
load addresses, the embedded protection DTB, SquashFS superblock, required
kernel options, all UBI header/table CRCs, volume geometry and exact kernel/
rootfs reconstruction. It also accepts a pre-boot raw slot readback with
empty formatted PEBs. After first boot the overlay/resizing changes are
expected, so it is not a post-boot filesystem-consistency checker.

The comparison accounts strictly for the build scripts' different padding:
sysupgrade-tar.sh zero-pads SquashFS to 1 KiB, while factory UBI stores its
unpadded filesystem and fills the remaining LEB space with erased `0xff`.
Every byte through the SquashFS superblock's bytes_used must match; both
padding regions are checked separately.

## Controlled first installation plan through stock SSH

The original all-read-only initramfs cannot perform this write. Do not unlock
its MTDs or run the old sysupgrade handler. The reviewed transition must:

1. Keep the production downstream router/Internet unchanged and the PC cabled to EX511 LAN1.
   Record UART reception and preserve the original private backups.
2. Return to stock using the already-observed one-shot reversion. Re-identify
   the directly connected unit and its new SSH host key; verify root, slot 0,
   all geometry and an unattached inactive `rootfs_1` again.
3. Capture fresh exact-length backups and checksums, retaining the first
   originals. Inspect the environment CRC and unchanged disarmed wrapper.
4. Transfer the verified **slot1 factory UBI** into stock RAM and round-trip
   it byte-for-byte before any write. Check available memory and free RAM
   filesystem space first.
5. Format/write only the label-resolved inactive `rootfs_1`, with the
   observed 2048-byte minimum I/O/VID offset and 128 KiB erase geometry.
   Read back the complete physical slot and reconstruct its exact FIT/root.
   Compare fresh active-stock, APPSBL and both BOOTCONFIG hashes unchanged.
6. Only after every readback passes, arm the already-tested one-shot flag.
   Recheck the environment CRC, synchronize and reboot once.
7. Observe FIT verification, the physical-slot-1 UBI attachment and SSH/LAN.
   Confirm `/rom` is SquashFS, `/overlay` is UBIFS on the slot1 rootfs_data
   volume and `/` uses overlayfs. Verify the marker, all effective MTD flags,
   UBI backing MTD, the factory/calibration checks and configuration persistence.
8. Measure idle and dual-AP memory, repeating the same byte-integrity tests,
   all jacks and routed NSS counters. Do not call a successful mount an OOM fix.
9. Reboot to confirm stock return before discussing automatic OpenWrt boot.

This is a review plan; the commands that erase/program NAND are deliberately
not an automatically executable public installer. The image hashes and build
validation are recorded in the accompanying build report. The owner later
authorized and completed this transition; see the linked hardware report
for the observed outcome and remaining limits. No direct stock-web flashing
is assumed.
