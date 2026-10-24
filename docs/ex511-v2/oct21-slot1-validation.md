# October 21 base and physical-slot-1 build validation

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

**Hardware follow-up:** the owner subsequently authorized the stock SSH
write and NAND-root trials. SquashFS/UBIFS boot, protection flags, return to
stock and overlay persistence have now been observed. See
[nand-root-hardware-trial.md](nand-root-hardware-trial.md) for those results.
The report below preserves the original pre-install build-validation scope.

## Result and provenance

The full OpenWrt build completed successfully for the updated protected
initramfs and slot1 SquashFS profiles. The **new images have not been booted
or flashed**. The older hardware observations in
[hardware-results.md](hardware-results.md) do not validate this updated build.

- Branch: `dev/ex511-v2-oct21-persistent-slot1`.
- Compiled firmware source: `a72260511bb9bb73d28a2f83f3e9ef7c191ae41d`.
- Merged release: `9caa35b4d718382ad882cb35c2372dbb569de901`
  (`ipq50xx-2026.10.21`).
- Image identification: **OpenWrt SNAPSHOT r37932-a72260511bb**, Linux
  **6.18.55**, AArch64, NSS firmware 12.5-210.
- Packages feed `baba60db0012a2a1a5fe5a079d58fc49e1b518be`, LuCI feed
  `580b6b1d9ec3a79edb8e2a5a9c4700b9c320ff6a`; NSS feed remains
  `5344fc35d79fc947b501e9feee5ced2b07c664fa`.

The merge conflict was limited to a test-summary string; the new WAX630E
test and our EX511 bound-Realtek DSA fixture were both retained. The source
then added the slot1 profile/upgrade guard and disabled the inherited EX511
BOOTCONFIG writer. Subsequent changes are documentation, offline validators
and comment corrections; the corrected DTS comments compile to the same DTB.

The original tested branch `dev/ex511-v2-hardware-validation` is preserved.
The running router was only queried read-only for its command line, slot
geometry and memory. No upgrade, environment update or reboot was performed.

## Final local images

These files contain the owner's privately provisioned board data and remain
local; they are not GitHub release assets.

| Image suffix after `openwrt-qualcommax-ipq50xx-` | Bytes | SHA256 |
| --- | ---: | --- |
| `tplink_ex511-v2-slot1-squashfs-factory.ubi` | 15,990,784 | `f4d4425657e6def4a3e20fcc9f4a4363d8d081399840c1998b54aadf0bf6f289` |
| `tplink_ex511-v2-slot1-squashfs-sysupgrade.bin` | 15,125,171 | `6cf4eb3f7cfef85f034964708b70bd2ccc3ef3ae0df0d0e2be27cd2926a0bfaf` |
| `tplink_ex511-v2-slot1-initramfs-uImage.itb` | 14,737,508 | `804f21d6d139e8e560263b72b6e629231eb8212535796358e13871ceaf6e93f6` |
| `tplink_ex511-v2-initramfs-test-initramfs-uImage.itb` | 14,737,476 | `0fa0cea3dca70ea760997ca55ce721414cedb984fb7c684c7d658e8e6cabe884` |

The candidate for the first NAND-root installation is the **slot1
squashfs-factory.ubi**, not either initramfs and not the ordinary release
sysupgrade image. That first operation would replace the diagnostic image
in slot 1, while preserving stock in slot 0.

The private bundle is at
`../ex511-v2-nss-build-artifacts/2026-10-21-oct21-slot1/` relative to this
checkout. It includes configs, feed pins, manifests, kernel-module packages,
build logs, hashes and validation JSON. Keep those modules with this build;
another snapshot's identically numbered kernel does not imply ABI compatibility.

## Confirmed by build and offline inspection

- Full `make -j6 V=s` returned success, including kernel, NSS/ECM, Ethernet,
  Realtek DSA, ath11k, updated hostapd, factory utilities and both profiles.
  Both device selections and LOW/256M/extra-NSS memory options survived defconfig.
- The normal FIT kernel is 4,511,368 bytes; its CRC/SHA hashes, AArch64/LZMA
  format, config@mp03.3, load/entry addresses and input-buffer separation pass.
  Its expanded Image is 14,905,352 bytes.
- Actual embedded DTB: all 17 labels/geometries preserved, GPIO33 reset and
  1G SGMII topology retained, firmware memory mode 2 on both radios, and
  **only physical rootfs_1 writable** in the slot1 profile. The diagnostic
  profile remains all-read-only.
- Actual factory UBI: two identical valid layout tables; kernel ID 0 uses
  36 LEBs, rootfs ID 1 uses 84, rootfs_data ID 2 initially reserves 9 with
  autoresize. No overlay LEB is initialized. There are 160 remaining physical
  PEBs before UBI/bad-block reservations, not 160 guaranteed usable overlay PEBs.
- Every kernel and SquashFS filesystem byte reconstructs from UBI exactly.
  The known zero-padding in the sysupgrade tar and erased UBI padding are
  checked separately. UBI EC, VID and every volume-table record CRC pass.
- Normal kernel configuration has an empty built-in initramfs source;
  UBI block, SquashFS and UBIFS are built in. Command-line partition
  replacement, writable master MTD exposure and UBI gluebi MTDs are disabled.
- The actual SquashFS contains the exact reviewed upgrade helper, jshn,
  fwtool, UBI tools, factory provisioning, LuCI, NSS/ath11k/Realtek modules
  and firmware. Private BDF provenance/region/FEM checks pass. Unprivileged
  host extraction cannot create `/dev/console`; the original SquashFS has
  that device entry, and all regular files were extracted and checked.
- The actual diagnostic FIT contains a parsed 1,538-entry initramfs. Its
  factory helper, BDF/provenance, release ID and extra-profile ath11k match
  the SquashFS. Its `/init` sets INITRAMFS=1. The normal kernel does not
  contain that diagnostic rootfs CPIO.
- Eight upgrade-guard test groups pass in Bash and BusyBox ash, including
  every protected partition's writability, wrong offsets/sizes, wrong or
  duplicate UBI arguments, legacy/wrong-profile metadata and corrupted metadata.
  Fixture NAND calls only record destinations; no device writes occur.
- Nine actual-image mutations are refused: EC, VID, layout CRC, kernel data,
  SquashFS data, erased padding, tar padding, truncation, and wrong volume
  names even with recomputed valid table CRCs. The ordinary October 21 release
  image is also refused as the wrong image class.
- Factory MAC (12 groups in Bash/ash), calibration (6 groups), MAC provisioning
  with native ucode (6 groups), existing SSH preflight (7 groups) and the
  merged NSS DSA defaults tests pass.

This is not a warning-free upstream build. Logs retain host-tool configure/
compiler warnings and inherited missing MODULE_DESCRIPTION modpost warnings
in networking modules. The new DTS retains the six known NSS/qfprom warnings;
the slot1 additions introduce no new DTB warning in the standalone comparison.

## Hardware and installation work still required

The read-only owner check confirmed that the already-tested environment-based
slot1 boot passes `ubi.mtd=rootfs_1`, rather than the BOOTCONFIG-based partition
swap described by the old upgrader. This supports the design; a normal
kernel booting the new SquashFS/overlay is still untested.

Follow [persistent-slot1.md](persistent-slot1.md) for the controlled stock SSH
transition. It requires another deliberate write to the diagnostic slot and
one reboot after fresh backups, RAM round-trip and raw-slot readback checks.
The first trial should keep the verified one-shot return-to-stock policy.

After boot, verify `/rom`, `/overlay`, actual root UBI/MTD mapping, all
protection flags, first boot/config persistence and measured memory. Repeat
Wi-Fi association and integrity tests, all ports and NSS/ECM routed counters.
The original first-association failure, mixed-load stability, PPPoE, IPv6,
cold resets and recovery limitations remain open. Do not infer a measured
RAM gain or an OOM fix from successful image generation.
