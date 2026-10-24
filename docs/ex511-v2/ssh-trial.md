# Owner-specific SSH initramfs trial

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

This is a development-session record, not a generic stock installer. The
AX55 wiki's inactive-slot initramfs method is a useful reference, but its
MTD numbers, slot sizes, factory-data volume and recovery claims do not
establish those properties for an EX511. Reference supplied by the owner:
https://openwrt.org/toh/tp-link/archer_ax55_v1

## Diagnostic image

The NSS `tplink_ex511-v2-initramfs-test` profile inherits the existing board,
packages, NSS stack and radio definitions. It adds read-only flags to all six
previously writable partitions: both BOOTCONFIG copies, APPSBLENV,
`misc_data_rw` and both firmware slots. The other eleven partitions were
already read-only. Geometry and factory provisioning remain unchanged.
It removes the persistent-root addition from `bootargs-append` and emits
only an initramfs FIT, with no factory or sysupgrade image.

The cached OpenWrt `make -j4 target/linux/install V=s` completed for this
profile, using Linux 6.18.55. The resulting FIT is 14,698,264 bytes, SHA256
`e49afc0f5d07b5eec802bf5765ea92130205d48d34ab5c8727aec774231a4b2e`.
Its compressed kernel is byte-identical to the previously validated NSS
image. The embedded DTB differs only in the six protection flags and chosen
bootargs. The compressed CPIO was located inside the actual FIT kernel;
its `/init` exports `INITRAMFS=1` and its preinit skips persistent root
mounting. Command-line partition replacement and writable parent-MTD
exposure are disabled in the compiled kernel.

These are Linux-side protections. They do not prevent bootloader writes or
establish effective runtime flags until the image actually boots.

## Stock prerequisites observed on this owner unit

Root access works through an interactive SSH shell request. SSH command
execution requests are rejected. A shell request without a PTY supports
binary transfer; no password is saved in scripts or logs. Host keys are
saved per boot and checked strictly after identifying the directly cabled
unit. The workstation's Internet route remains on Wi-Fi.

At the preflight, stock Linux 4.4.60 ran from `rootfs`, slot 0, and
`rootfs_1`, slot 1, was unattached. Each is 38,141,952 bytes (291 128-KiB
PEBs). Resolve MTD indices from labels again before any operation; virtual
MTDs representing UBI volumes are not physical firmware slots.

The stock `kernel` volume reserves 50 LEBs, only 6,348,800 bytes. It cannot
hold our FIT. A separate kernel-only UBI was prepared with 116 LEBs reserved
for volume 0, `kernel`. Including its two layout PEBs, the image is
15,466,496 bytes, SHA256
`0a9b9f3d8667a25bebf3f0435cdba8a853eac449a4948eb6b89c622fec8929ac`.
Both layout copies, every EC/VID/table CRC and exact FIT reconstruction
passed local checks. Extra physical space is left for UBI allocation and
bad-block handling; the inactive NAND readback still needs checking after
any write. Do not replace only the existing kernel volume.

The owner's bootloader was previously read and matched the extracted
U-Boot 2016.01 binary. `tp_boot_idx=1` selects slot 1; undefined selects
slot 0. `config@mp03.3` is selected for this machine. Load-error fallback
is not a Linux health check. The inherited OpenWrt sysupgrade handler pins
physical slot 0 and is not used as a stock installer.

## One-shot selection and actual stock-only dry run

The owner authorized flashing after the earlier read-only investigation.
Before any firmware-slot write, private exact-length backups were captured
for both firmware slots, APPSBLENV, both BOOTCONFIG copies and APPSBL. Host
checksums were recorded and the original environment CRC verified. Backups
and BDF-containing images stay outside Git.

A stock-only dry run installed a persistent conditional `bootcmd`. It
checks a separate `ex511_trial` environment flag using `printenv`, clears
that flag, and requires successful `saveenv` before selecting a temporary
slot in RAM and calling `bootipq`. The dry run selected slot 0. Serial
output showed the environment save and stock kernel boot. Subsequent SSH
reads confirmed that the flag was durably absent, `tp_boot_idx` remained
undefined in flash and the environment CRC was valid.

Keeping the conditional bootcmd itself unchanged while it executes avoids
relying on self-modification of the interpreter's current command string.
When unarmed it calls stock `bootipq` without changing the slot. The later
trial substitutes RAM slot 1 after persisting the cleared flag. Thus a
subsequent reset is intended to boot the preserved stock slot. This was
exercised on stock; successful OpenWrt handoff and return still require
hardware observation. Power failure during environment updates remains a
risk. This does not establish a vendor recovery procedure.

## Reproduction and checks

Follow [build.md](build.md) for feed pins, dependencies and private BDF
provisioning. In a space-free build checkout of this branch:

```sh
sed 's/DEVICE_tplink_ex511-v2=y/DEVICE_tplink_ex511-v2-initramfs-test=y/' \
  configs/ex511-v2-nss.config > .config
make defconfig
make -j8 V=s
python3 scripts/ex511-v2/test-ssh-preflight.py
python3 scripts/ex511-v2/validate-nss-build.py \
  --dtb build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/image-ipq5018-tplink-ex511-v2-initramfs-test.dtb \
  --readonly-trial \
  --rootfs build_dir/target-aarch64_cortex-a53_musl/root-qualcommax
```

The assessment helper accepts a private capture produced by
`collect-stock-ssh.py`, a FIT and its kernel configuration. It verifies root
and slot metadata, FIT hashes, all physical partition geometry, protection
flags, a basic RAM/input-buffer overlap check and volume capacity. A zero
exit status is an offline check result, not approval or proof of bootability.
`check-trial-ubi.py --ubi FILE --fit FILE` also accepts a raw inactive-slot
readback and reconstructs the exact kernel through validated UBI metadata.
Seven assessment fixture tests pass; additional actual-image mutation
checks reject damaged EC/layout/payload data, truncation and the wrong FIT.

## UART limitation

RX input has not worked. The owner-provided AX55 wiki describes a factory
gap in that board's RX trace. The EX511's matching receive-only symptom and
stock serial break counters make this a hardware hypothesis, not proof of
an identical layout or a location to bridge. Do not solder unidentified
points. UART reception can observe a failed trial but cannot issue recovery
commands. Recovery web behavior from AX55 must not be assumed for EX511.

## Authorized hardware result — 20 October 2026

The kernel-only diagnostic UBI was transferred to a private stock RAM path
through a non-PTY SSH shell. Its bytes were read back and compared exactly
before invoking `ubiformat` on the label-resolved inactive `rootfs_1`.
The formatter completed successfully. A complete physical readback passed
EC/VID/layout checks and reconstructed the original FIT exactly. New reads
of active `rootfs`, APPSBL and both BOOTCONFIG partitions matched their
pre-write backup hashes. No factory or calibration partition was written.

The trial was then armed for RAM slot 1 and the router rebooted. UART
confirmed both FIT hashes, AArch64 handoff and Linux 6.18.55 startup.
A source-bound wired connection to $OPENWRT_HOST established authenticated
root SSH and identified the expected OpenWrt SNAPSHOT
`r37776-5110b3c9868`. That build ID is inherited from the reused kernel;
the separate diagnostic DTB/protection changes are described above.

Confirmed on this unit:

- LAN1 negotiated 1000/full; ping and an SSH session transferred data in
  both directions. Other jacks, routing performance and isolation remain
  untested.
- The Realtek driver reported **RTL8367S-VB**, refining the earlier generic
  RTL8367S hypothesis. The current fork's driver registered all five user
  ports and LAN1 passed traffic. This does not prove support in another
  kernel or in the official AX55 image described by the wiki.
- Conduit/br-lan/LAN1 used the expected owner factory MAC; WAN used base +1.
  Owner addresses are kept private.
- All 17 effective physical MTD flags lacked MTD_WRITEABLE. The trial slot
  and `misc_data_ro` attached read-only; the factory UBIFS mount was R/O and
  its temporary mount/attachment was cleaned up.
- NSS core 0 reported successful firmware boot. Both ath11k PHYs registered,
  including the external QCN6122-compatible path. This is **not** proof of
  NAT/Wi-Fi offload, AP association, RF performance or stability. No AP was
  enabled or scanned during this collection.
- A raw read of APPSBLENV after OpenWrt handoff had a valid environment CRC,
  no persistent `ex511_trial` flag and no persistent `tp_boot_idx`. Thus the
  saved selection remains stock slot 0. A subsequent reboot returned from
  the actual OpenWrt trial to stock Linux 4.4.60 in slot 0. SSH confirmed
  both trial/slot variables remained undefined.

The running system is an **initramfs diagnostic boot**, not a permanent
writable OpenWrt installation. Its configuration lives in RAM. The inactive
slot now contains the diagnostic image, while the stock active slot remains
intact. The conditional bootcmd remains installed but unarmed after the
trial. Do not call sysupgrade from this read-only profile or assume that
stock has been permanently replaced.

Serial inspection additionally found a large RX/TX feedback stream: console
output was being interpreted as shell input, with RX/TX counters both above
1.5 million and repeated syntax errors. The owner was instructed to remove
only the adapter-TX-to-candidate-board-RX wire, retaining ground and log
reception. The electrical cause and any factory RX gap remain unconfirmed.
After removing that wire, serial counters stopped increasing abnormally;
the clean second boot recorded only two RX bytes. Subsequent Ethernet and
Wi-Fi traffic tests, the original image's OOM and the smaller NSS profile
trial are recorded in [hardware-results.md](hardware-results.md). Longer
dual-radio/256-MiB memory testing remains necessary.

Private execution scripts, original backups, post-write readbacks, full
serial capture and SSH reports are retained outside the repository. No
firmware, factory contents, password or private capture is published.
