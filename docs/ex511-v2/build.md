# Historical build record

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

For the owner image that permits explicit default-boot selection, use
[slot1-env-control.md](slot1-env-control.md) and its separate build config.
Preparing that image does not activate a boot-policy change.

The October 21 integration and NAND-root candidate live on
`dev/ex511-v2-oct21-persistent-slot1`. Use
[persistent-slot1.md](persistent-slot1.md) for that profile's build, protection,
validation and stock SSH transition plan. The pinned October 20 reproduction
below intentionally retains its historical commit and validation results.

For runnable commands on the maintained branch use [build-current.md](build-current.md).
Historical commit IDs below are provenance and may not exist in this new repository.

Use a Linux account without root privileges for the build, a case-sensitive
filesystem, a source path without spaces and enough disk for a complete
OpenWrt toolchain/kernel build. The local build started with 76 GiB free.
The tree checks prerequisites through `include/prereq-build.mk`.

On Ubuntu, install the usual build prerequisites before cloning, for example:

```sh
sudo apt-get update
sudo apt-get install build-essential bzip2 gawk git libncurses-dev rsync \
  python3 python3-dev python3-setuptools swig unzip file wget curl \
  zlib1g-dev libssl-dev gettext perl time patch xz-utils
```

Build this branch (the original fl1ck3r-derived branch remains separate):

```sh
git clone --branch ex511-v2 \
  https://github.com/TheHugoHypothesis/openwrt-ex511-v2.git ex511-nss-build
cd ex511-nss-build
# Pin the source used for the validated 20 October images:
git switch -c reproduce-ex511-nss 5110b3c9868317337feb1289afe37dcc92cfa0d0
git branch --set-upstream-to=origin/dev/ex511-v2-nss-factory
./scripts/feeds update -a
./scripts/feeds install -a
cp configs/ex511-v2-nss.config .config
make defconfig
./scripts/diffconfig.sh > ex511-nss.diffconfig
make download -j8
```

The feed pins are in `feeds.conf.default`; do not run a feed upgrade to a
different revision while reproducing a build. Confirm that `make defconfig`
kept `nss-tools-dwmac`, `kmod-qca-dwmac-nss`, `kmod-qca-nss-drv`,
`kmod-qca-nss-ecm`, `ATH11K_NSS_SUPPORT`, `MAC80211_NSS_SUPPORT`,
`NSS_MEM_PROFILE_LOW`, `ATH11K_MEM_PROFILE_256M`,
`NSS_FIRMWARE_VERSION_12_5` and `ex511-v2-factory` selected.

Before building, import a BDF from this unit's stock extraction into a
private directory **outside the checkout**. Country/FEM below are this
owner's observed values, not values to substitute on an unknown unit:

```sh
python3 scripts/ex511-v2/import-stock-bdf.py \
  --stock-rootfs /absolute/path/to/private-stock-rootfs \
  --country BR --fem-mask-5g 10 \
  --output-dir /absolute/path/to/private-ex511-files
mkdir -p files
rsync -a /absolute/path/to/private-ex511-files/ files/
make -j8 V=s
```

Do not commit `files/`, factory captures, stock EEPROM or generated images.
The importer provides the BDF at its final path and in `rootfs-overlay/`,
matching ipq-wifi's post-install overlay stage; otherwise that package
overrides a plain `files/lib/firmware/` copy. The final image validator
checks the installed BDF against its provenance hash.

The overlay contains a regional/FEM BDF and a marker, not the owner's MAC
or calibration record. Per-unit calibration is read from protected UBIFS at
boot. Without a matching marker the external-radio provisioning refuses to
proceed. Firmware and BDF redistribution rights are not established by this
import tool; the owner build stays local.

Outputs are under `bin/targets/qualcommax/ipq50xx/`. Keep the complete
`.config`, manifest, feed pins, source commit and sha256sums with them. A
kernel module from official snapshots or another build may have a different
ABI; retain this build's package repository. These commands do not deploy
anything. A sysupgrade output is not a stock factory installer.

## Historical host-toolchain constraints

The original cached build needed a space-free checkout and a compatible host
compiler/Perl environment. Host tools were reused with GCC 13 and complete
Perl modules to avoid a newer compiler/incomplete-module host issue. A normal
Linux build environment should install complete prerequisites instead of
copying another operator's temporary tool paths. This was not a separately
verified clean-from-scratch build on a second machine.

## Offline validation commands

```sh
python3 scripts/ex511-v2/test-factory-mac.py
python3 scripts/ex511-v2/test-wifi-caldata.py
python3 scripts/ex511-v2/test-mac-provisioning.py --ucode ucode
# Also exercise shell fixtures with BusyBox ash when installed:
python3 scripts/ex511-v2/test-factory-mac.py --shell 'busybox ash'
EX511_TEST_SHELL='busybox ash' python3 scripts/ex511-v2/test-wifi-caldata.py
```

`test-mac-provisioning.py --ucode` accepts a complete QEMU + target-ucode
command if there is no host interpreter. It substitutes fixture inputs,
without touching `/etc`, sysfs, MTD, UBI or a real interface.

After preparing/building the kernel:

```sh
python3 scripts/ex511-v2/compile-dtb.py \
  --kernel-dir build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/linux-6.18.55 \
  --dtc build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/linux-6.18.55/scripts/dtc/dtc \
  --output /tmp/ex511-nss.dtb
python3 scripts/ex511-v2/validate-nss-build.py --dtb /tmp/ex511-nss.dtb \
  --rootfs build_dir/target-aarch64_cortex-a53_musl/root-qualcommax \
  --private-overlay
```

The validator checks the compiled topology, radio memory mode, preserved
17-partition geometry and rootfs contents. It does not establish Ethernet,
RF, NSS throughput, factory reads on hardware or a safe installation path.

## Read-only NSS diagnostic profile

See [ssh-trial.md](ssh-trial.md) for the initramfs-only profile, local
validation and the owner-specific installation investigation. It retains
NSS and both radio definitions while protecting all 17 NAND partitions.
This is separate from the writable persistent-install profile above.
