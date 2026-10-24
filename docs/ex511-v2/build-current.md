# Build EX511 V2 firmware

Build on Linux as a non-root user, on a case-sensitive filesystem in a path
without spaces. Install normal OpenWrt host prerequisites and follow the
build system's prerequisite checks. Python 3 and pexpect are also needed for
the stock shell-transfer helper, not for the router runtime.

```sh
git clone --branch ex511-v2 https://github.com/TheHugoHypothesis/openwrt-ex511-v2.git
cd openwrt-ex511-v2
./scripts/feeds update -a
./scripts/feeds install -a
```

Keep the feed revisions in feeds.conf.default fixed while reproducing a
build. Do not mix kernel modules or firmware packages from incompatible builds.

## Linux prerequisites

Example Debian/Ubuntu host packages (the build prerequisite checks remain authoritative):

```sh
sudo apt-get update
sudo apt-get install build-essential bzip2 gawk git libncurses-dev rsync \
  python3 python3-dev python3-setuptools python3-pexpect swig unzip file \
  wget curl zlib1g-dev libssl-dev gettext perl time patch xz-utils
```

Use enough disk space for a full toolchain/kernel build. A clean rebuild on
another host can expose host-toolchain issues not covered by cached builds.

## Profiles

| Configuration | Purpose |
| --- | --- |
| configs/ex511-v2-nss.config | Baseline build seed; not the protected slot1 installation |
| Diagnostic variant of that seed | Initramfs with all physical NAND partitions read-only |
| configs/ex511-v2-slot1.config | Persistent SquashFS/UBIFS in rootfs_1; only that slot writable |
| configs/ex511-v2-slot1-env.config | Slot1 plus explicit APPSBLENV write capability for the guarded controller |

The generic/legacy profile is not interchangeable with the dedicated slot1
profiles. An env-control profile makes environment writing possible; it does
not select a different boot default by itself.

Diagnostic seed:

```sh
sed 's/DEVICE_tplink_ex511-v2=y/DEVICE_tplink_ex511-v2-initramfs-test=y/' \
  configs/ex511-v2-nss.config > .config
```

For protected persistent or env-control builds, copy the corresponding config
to .config instead. Build each separately and save its outputs separately.

For example, to select the final explicit environment-control profile:

```sh
cp configs/ex511-v2-slot1-env.config .config
```

Use configs/ex511-v2-slot1.config for the protected persistent stage instead.
Do not compile all three into one unlabeled output directory and then guess
which image belongs to which profile.

## Private board data

Establish the device's factory country/FEM selection independently. Extract a
matching stock root filesystem and run the importer using your own values:

```sh
python3 scripts/ex511-v2/import-stock-bdf.py \
  --stock-rootfs "$STOCK_ROOTFS" --country "$FACTORY_COUNTRY" \
  --fem-mask-5g "$FACTORY_FEM" --output-dir "$PRIVATE_OVERLAY"
mkdir -p files
rsync -a "$PRIVATE_OVERLAY/" files/
make defconfig
make download -j4
make -j4 V=s
```

PRIVATE_OVERLAY must be an absolute path outside the checkout. Neither factory
payloads nor generated firmware should be committed. A missing/mismatched
BDF marker is not a valid shortcut to a working external radio.

## Check before deployment

Run factory/calibration and upgrade-guard tests. Validate the compiled DTB
and assembled rootfs with validate-nss-build.py; use --readonly-trial,
--slot1 or --slot1-env as appropriate and --private-overlay to check matching
regional/FEM provenance. For persistent images use check-slot1-image.py with
--env-control only for the env-control profile. All tools expose --help.

The diagnostic FIT needs a kernel-only UBI with 2048-byte minimum I/O,
128-KiB PEBs, VID offset 2048, one dynamic kernel volume, and exactly
ceil(FIT-size / 126976) reserved LEBs. Do not add autoresize to that volume.
Validate the result with check-trial-ubi.py. A factory.ubi filename does not
imply compatibility with the signed stock web upgrader.

A successful build/check does not establish operation or recovery on another
hardware revision. See [installation](installation-ssh.md) before any write.

## Exact validation command example

For an environment-control build, use the build's corresponding artifacts:

```sh
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

For a diagnostic image use --readonly-trial; for protected slot1 use --slot1
and omit --env-control on the image checker. A different kernel version may
change build-directory names. The historical private image hashes are
identifiers for those images, not expected hashes of this new source snapshot.

## Generate the diagnostic UBI

After building the diagnostic FIT, use the build's host ubinize tool:

```sh
LEBS=$(python3 -c 'import os,sys; print((os.path.getsize(sys.argv[1])+126975)//126976)' "$DIAGNOSTIC_FIT")
cat > "$PRIVATE_TRIAL_DIR/ubinize.ini" <<INI
[kernel]
mode=ubi
image=$DIAGNOSTIC_FIT
vol_id=0
vol_type=dynamic
vol_name=kernel
vol_size=$((LEBS * 126976))
INI
staging_dir/host/bin/ubinize -m 2048 -p 128KiB -s 2048 -O 2048 \
  -o "$PRIVATE_TRIAL_DIR/trial.ubi" "$PRIVATE_TRIAL_DIR/ubinize.ini"
python3 scripts/ex511-v2/check-trial-ubi.py \
  --ubi "$PRIVATE_TRIAL_DIR/trial.ubi" --fit "$DIAGNOSTIC_FIT"
```

Use absolute private paths, create PRIVATE_TRIAL_DIR first and keep all
three profiles' outputs separate. This wraps a diagnostic kernel; it is
not a signed stock installer or the persistent factory UBI.
