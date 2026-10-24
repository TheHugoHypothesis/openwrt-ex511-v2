# Owner slot1 image with explicit boot-policy control

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

## Scope

The `tplink_ex511-v2-slot1-env` profile inherits the hardware-tested NAND-root
slot1 image and adds deliberate APPSBLENV writability. Installing or booting
it does not change any bootloader variable. The separate workstation tool
`scripts/ex511-v2/boot-policy.py` selects stock or OpenWrt over pinned-key SSH;
there is no startup service, web endpoint or automatic environment write.
Python runs on the workstation, not the router.

Only `rootfs_1` at 0x36a0000 and `0:APPSBLENV` at 0x300000 are writable.
The other 15 physical partitions retain read-only flags, including stock
slot0, APPSBL, both BOOTCONFIG copies and all factory/calibration partitions.
The inherited partition offsets, network, radio, firmware, calibration and
NSS definitions are unchanged. The original protected slot1 profile remains
available separately and does not gain environment writability.

The DT has both `openwrt,ex511-slot1-layout` and
`openwrt,ex511-env-control`. The host executor checks the latter plus every
physical partition's geometry/flags, root identity and UBI boot argument.
Read [the controller review](failsafe-and-boot-policy-review.md) for CRC,
exact-wrapper, reviewed-plan, standard-tool lock, private backup and readback
checks. A root process can still bypass the controller using raw flash tools:
writable APPSBLENV is a capability, not access control against root.

The observed environment occupies one 256 KiB region in a 512 KiB partition,
across two 128 KiB eraseblocks. Redundant environments and power-loss-atomic
updates have **not** been established. Stable power and an external backup
are required for a later authorized write. An ambiguous write result must
be inspected before any reboot; do not retry or restore it automatically.

## Compatibility and upgrade behavior

The new profile keeps compatibility version 2.0, the existing
`tplink,ex511-v2-slot1` supported-device marker and the archive board identity
`tplink_ex511-v2-slot1`. It adds `tplink,ex511-v2-slot1-env` to image metadata.
This lets the already-installed protected 2.0 slot1 updater recognize its
archive without force flags or a generic board-image override.

On the new env-control profile the upgraded handler expects exactly two
writable partitions, verifies APPSBLENV geometry, and requires both image
markers. It refuses accidental upgrades to a profile without environment
control. On the protected profile it still expects exactly one writable
partition and permits a reviewed transition to this opt-in image. Both
handlers write firmware only to `rootfs_1`; neither changes the environment.
The host executor additionally refuses an APPSBLENV with reported bad blocks.

The stock image is preserved, but this is **not automatic A/B rollback**.
Once `tp_boot_idx=1` is durable, a kernel that starts and later hangs may
continue to be selected. Failsafe needs a working kernel and Ethernet.
Bootloader Reset recovery entry/HTTP GET have been tested, but actual vendor
firmware restoration through that form has not. UART currently receives
output only. Preserve these limitations when deciding to activate a policy.

## Build result

The candidate compiled successfully. See [slot1-env-validation.md](slot1-env-validation.md)
for exact source/revision, artifact hashes, warnings and offline test results.
The subsequent [owner hardware trial](slot1-env-hardware-trial.md) completed
the actual slot1 sysupgrade, bidirectional policy selection, two default
OpenWrt warm boots and one owner-confirmed physical cold start. OpenWrt is now the owner unit's saved default.

## Reproduce the image

Use the pinned feeds and private owner BDF import from [build.md](build.md).
Do not publish the private overlay or generated firmware until redistribution
rights are established. From a clean checkout in a path without spaces:

```sh
./scripts/feeds update -a
./scripts/feeds install -a
cp configs/ex511-v2-slot1-env.config .config
make defconfig
make download -j6
make -j6 V=s
python3 scripts/ex511-v2/test-slot1-upgrade.py --host-tools staging_dir/host
python3 scripts/ex511-v2/validate-nss-build.py --slot1-env \
  --dtb build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/image-ipq5018-tplink-ex511-v2-slot1-env.dtb \
  --rootfs build_dir/target-aarch64_cortex-a53_musl/root-qualcommax \
  --private-overlay
python3 scripts/ex511-v2/check-slot1-image.py --env-control \
  --sysupgrade bin/targets/qualcommax/ipq50xx/openwrt-qualcommax-ipq50xx-tplink_ex511-v2-slot1-env-squashfs-sysupgrade.bin \
  --ubi bin/targets/qualcommax/ipq50xx/openwrt-qualcommax-ipq50xx-tplink_ex511-v2-slot1-env-squashfs-factory.ubi \
  --kernel-config build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/linux-6.18.55/.config.set \
  --fwtool staging_dir/host/bin/fwtool
```

## Staged hardware validation, separately authorized

1. Save fresh external backups and keep stock selection unchanged. Verify
   the proposed image and existing current-profile `sysupgrade -T` result.
   The first controlled in-place sysupgrade passed on the owner unit; neither
   `-T` nor a compiled image proves that operation safe under interruption.
2. Upgrade slot1 while stock remains the durable default. Sysupgrade's reboot
   returns to stock under the current one-shot wrapper. Use the established
   stock SSH one-shot mechanism to boot the updated slot1 once.
3. Verify new revision, persistent configuration, both DT markers, exactly
   the two intended writable partitions, all offsets, unarmed wrapper,
   valid environment CRC, Ethernet, both APs and memory. No policy write is
   required for these checks. Do not proceed on a mismatch.
4. Use a private fresh 512 KiB APPSBLENV readback, after checking layout with
   the host controller, to generate a reviewed offline plan. The original
   protected profile must continue to refuse the controller's apply path.
5. Only with explicit authorization apply a plan and check `verified.json`
   and the complete post-write readback. Reboot is a separate operation.
   Test OpenWrt warm/cold starts, then an explicitly selected stock return
   and the established one-shot path back. Record each policy and outcome.

Example host workflow **after** the new image is installed and verified;
use fresh paths and a new reviewed plan for each later authorized change:

```sh
# Obtain a protected snapshot through the controller's layout checks.
python3 scripts/ex511-v2/boot-policy.py snapshot \
  --host "$OPENWRT_HOST" --source "$PC_SOURCE" \
  --known-hosts /private/verified-known-hosts --output /private/fresh-env.bin
python3 scripts/ex511-v2/boot-policy.py plan \
  --before /private/fresh-env.bin --policy openwrt --output /private/new-plan
# Inspect new-plan/plan.json before a separately authorized apply:
python3 scripts/ex511-v2/boot-policy.py apply \
  --host "$OPENWRT_HOST" --source "$PC_SOURCE" \
  --reviewed-plan /private/new-plan/plan.json \
  --backup-dir /private/new-apply-backup --known-hosts /private/verified-known-hosts
```

Host and workstation source are required explicit arguments. Set
OPENWRT_HOST and PC_SOURCE for the isolated management link. `--policy stock` generates the reverse
plan, deleting `tp_boot_idx`; both policies require `ex511_trial` disarmed
and preserve the exact existing bootcmd wrapper. `apply` never reboots.
