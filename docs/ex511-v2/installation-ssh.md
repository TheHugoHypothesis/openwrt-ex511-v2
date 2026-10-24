# Install EX511 V2 through stock root SSH

All host/network symbols such as $EX511_HOST, $OPENWRT_HOST, $PC_SOURCE,
$RECOVERY_HOST and $RECOVERY_PC must be independently established for the
reader's isolated setup. They intentionally replace private deployment
addresses. Source identifiers in historical reports are explained in
[source-provenance.md](source-provenance.md).

[Português](installation-ssh.pt-BR.md) · [Build](build-current.md) · [Recovery](recovery.md)

This is the **staged procedure demonstrated on one owner unit**, reorganized
for another experienced operator. It is not a universal automated installer.
The new parameterized RAM-transfer CLI is based on the historical mechanism;
its publication validation used the running OpenWrt shell, not a second stock
installation. Receive-only UART observed the original installation; the writes
and boot selection did not require UART input. A closed-case installation
without that observation channel has not been independently repeated.

## 0. Prerequisites and stop conditions

Proceed only if all are established:

- Exact EX511 **V2**, matching [17-partition layout](hardware.md), stock slot0
  active, rootfs_1 unattached, correct bootloader behavior. This guide does
  not cover stock running from slot1 or an already customized bootcmd.
- An existing authenticated **effective-root** stock SSH shell. `admin` was
  the login on the test unit; its name alone does not imply root. This project
  does not provide a stock web exploit, default password or root-unlock method.
- A verified SSH host key, private off-device backups, stable power and an
  understood recovery plan. No automated rollback from every kernel hang.
- Independently built diagnostic, protected-slot1 and environment-control
  artifacts, using your own matching BDF/calibration provenance.
- Linux workstation with Python 3/pexpect, OpenSSH and this repository.
  Keep the EX511 isolated from your production network during installation.
  Connect the PC to EX511 LAN1; a different connection can supply PC Internet.

**Stop on any mismatch, invalid CRC, unexpected bad blocks, transfer failure,
missing tool, attached target or ambiguous write result.** Do not substitute
AX55 MTD numbers/images, use sysupgrade from stock, unlock MTDs, or flash the
old generic slot0 profile. Never use `sysupgrade -F` to bypass refusal.

## 1. Establish and record stock access — workstation, then stock shell

Verify the router's address from your own network. The test unit used
$EX511_HOST. Pin its key only after independently identifying the isolated
device; `ssh-keyscan` alone does not authenticate a host. Keep a separate
known-hosts file for stock and OpenWrt because they use different keys.

```sh
# Workstation: inspect candidate fingerprint; verify it independently first.
mkdir -m 700 -p "$HOME/ex511-private"
ssh-keyscan -T 5 $EX511_HOST > "$HOME/ex511-private/stock-candidate.keys"
ssh-keygen -lf "$HOME/ex511-private/stock-candidate.keys"
# Only after verification:
cp "$HOME/ex511-private/stock-candidate.keys" "$HOME/ex511-private/stock.keys"
ssh -tt -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$HOME/ex511-private/stock.keys" admin@$EX511_HOST
```

Inside the stock shell, run read-only checks:

```sh
grep '^Uid:' /proc/self/status
uname -a
cat /proc/mtd
cat /proc/cmdline
cat /proc/boot_info/rootfs/primaryboot
cat /proc/boot_info/rootfs/upgradepartition
cat /etc/fw_env.config
fw_printenv bootcmd
fw_printenv tp_boot_idx
fw_printenv config_name
```

Expected on the tested original stock: effective UID 0, primaryboot 0,
upgradepartition rootfs_1, bootcmd=bootipq, tp_boot_idx undefined. FIT uses
config@mp03.3. The environment mapping was `/dev/mtd7 0x0 0x40000 0x20000 0x2`;
**resolve/check its label and geometry, do not copy mtd7 to another layout**.
Two erase sectors here are not proof of redundant environments.

Collect structured read-only metadata from the workstation:

```sh
python3 scripts/ex511-v2/collect-stock-ssh.py \
  --host $EX511_HOST --user admin \
  --known-hosts "$HOME/ex511-private/stock.keys" \
  --output "$HOME/ex511-private/stock-capture"
```

This collector expects the observed stock shell/prompt. A refusal on another
version is a reason to inspect, not change guards to force it through.

## 2. Private backups before any write

Resolve every physical MTD label from the fresh capture, including offsets
from sysfs. Save both firmware slots, APPSBLENV, APPSBL, both BOOTCONFIG copies
and factory/calibration partitions before altering the device. Keep a full
NAND backup if available, recording whether it includes OOB/ECC/bad-block
metadata. A normal `/dev/mtdN` read below is a logical data read, not an OOB
image or a portable complete NAND restoration recipe.

The stock SSH server tested here rejected `ssh host command` execution
requests. Use the shell-request transfer helper for binary reads. Example
**with N and BYTES taken from the verified physical partition**, not copied:

```sh
python3 scripts/ex511-v2/stock-transfer.py \
  --host $EX511_HOST --user admin \
  --known-hosts "$HOME/ex511-private/stock.keys" \
  get --remote /dev/mtdN --bytes BYTES \
  --output "$HOME/ex511-private/PARTITION-before.bin"
```

Repeat for the reviewed labels; record exact lengths and SHA256. The helper
refuses to overwrite existing outputs. Obtain two independent reads or
compare a trustworthy device-side checksum. Do not publish dumps: they may
contain credentials and per-device factory data.

Verify APPSBLENV locally before changing it (this geometry only):

```sh
python3 - "$HOME/ex511-private/APPSBLENV-before.bin" <<'PY'
import pathlib, struct, sys, zlib
raw = pathlib.Path(sys.argv[1]).read_bytes()
assert len(raw) == 0x80000
assert struct.unpack_from('<I', raw)[0] == zlib.crc32(raw[4:0x40000])
print('Observed environment CRC/size valid; this does not prove power-fail safety.')
PY
```

## 3. Build/check the three profile artifacts

Follow [build-current.md](build-current.md). Keep their exact names/hashes
separate: diagnostic `trial.ubi` + initramfs FIT; protected-slot1 persistent
`factory.ubi` + sysupgrade; final slot1-env sysupgrade. Require successful
image checkers and fresh metadata assessment before moving on.

## 4. Exercise a stock-only one-shot boot first — stock shell

This changes APPSBLENV, not a firmware slot. Stable power is essential.
Use only after original bootcmd/slot state and environment backup match step1.
The wrapper clears the trial flag and successfully saves that cleared state
**before** changing the boot slot in RAM. First select stock slot0 as a dry run:

```sh
set -e
EXPECTED_WRAPPER='if printenv ex511_trial; then setenv ex511_trial; if saveenv; then setenv tp_boot_idx 0; fi; fi; bootipq'
fw_setenv bootcmd "$EXPECTED_WRAPPER"
[ "$(fw_printenv bootcmd)" = "bootcmd=$EXPECTED_WRAPPER" ] || exit 1
fw_setenv ex511_trial 1
[ "$(fw_printenv ex511_trial)" = 'ex511_trial=1' ] || exit 1
sync
```

Before rebooting, save a complete armed-environment readback and verify its CRC; then issue `reboot` separately.


Check each setter's success and exact readback before rebooting. Reconnect to
stock and confirm primaryboot 0, tp_boot_idx undefined, ex511_trial undefined,
and a new full valid-CRC APPSBLENV readback. If flag clearing/save behavior is
not proven, stop. Do not replace the wrapper while it is executing in U-Boot.

## 5. Transfer the diagnostic UBI into stock RAM — workstation

Check stock MemAvailable and `/tmp` capacity before transfer; the historical
formatter stage required more than 40 MiB MemAvailable. Pause optional stock
services only with device-specific understanding. Do not stage to flash.

```sh
python3 scripts/ex511-v2/stock-transfer.py \
  --host $EX511_HOST --user admin \
  --known-hosts "$HOME/ex511-private/stock.keys" \
  put --remote /tmp/ex511-install/trial.ubi \
  --input /absolute/path/to/verified/trial.ubi
```

Success means a **byte-for-byte RAM round-trip**, not a flash/boot guarantee.
A failed transfer must not be followed by formatting. The helper only writes
new files under `/tmp/ex511-install/` and never flashes/reboots itself.

## 6. Format only the verified inactive physical slot — stock shell

Recheck primaryboot, upgradepartition, environment state and UBI attachments
immediately before this operation. Stock must still run from slot0. Resolve
rootfs_1 dynamically; the checks below deliberately apply to this layout only:

```sh
TARGET=$(awk -F '[:"]' '$3 == "rootfs_1" { print $1 }' /proc/mtd)
case "$TARGET" in mtd[0-9]*) ;; *) echo 'STOP: target unresolved'; exit 1;; esac
[ "$(cat /sys/class/mtd/$TARGET/name)" = rootfs_1 ] || exit 1
[ "$(cat /sys/class/mtd/$TARGET/size)" = 38141952 ] || exit 1
[ "$(cat /sys/class/mtd/$TARGET/offset)" = 57278464 ] || exit 1
[ "$(cat /sys/class/mtd/$TARGET/erasesize)" = 131072 ] || exit 1
[ "$(cat /proc/boot_info/rootfs/primaryboot)" = 0 ] || exit 1
[ "$(cat /proc/boot_info/rootfs/upgradepartition)" = rootfs_1 ] || exit 1
for path in /sys/class/ubi/ubi[0-9]*/mtd_num; do
  [ ! -r "$path" ] || [ "$(cat "$path")" != "${TARGET#mtd}" ] || exit 1
done
# DESTRUCTIVE: only after all preceding checks, backups and RAM verification.
ubiformat "/dev/$TARGET" -y -s 2048 -O 2048 -f /tmp/ex511-install/trial.ubi
```

Never format rootfs, factory partitions, BOOTCONFIG or APPSBL. Capture success;
on an SSH timeout do not infer failure and repeat a write. Read the entire
inactive slot privately with stock-transfer.py and validate it:

```sh
python3 scripts/ex511-v2/check-trial-ubi.py \
  --ubi /private/rootfs_1-after.bin --fit /private/diagnostic-initramfs.itb
```

Read/hash active rootfs, APPSBL and both BOOTCONFIG again; they must match the
originals. The image checker reconstructs the exact FIT through UBI headers
and CRCs; a raw input/output whole-image hash need not match after formatting.

## 7. Boot the diagnostic image once — stock shell

Only after validated slot readback and protected hashes:

```sh
set -e
EXPECTED_WRAPPER='if printenv ex511_trial; then setenv ex511_trial; if saveenv; then setenv tp_boot_idx 1; fi; fi; bootipq'
fw_setenv bootcmd "$EXPECTED_WRAPPER"
[ "$(fw_printenv bootcmd)" = "bootcmd=$EXPECTED_WRAPPER" ] || exit 1
fw_setenv ex511_trial 1
[ "$(fw_printenv ex511_trial)" = 'ex511_trial=1' ] || exit 1
sync
```

Before rebooting, save a complete armed-environment readback and verify its CRC; then issue `reboot` separately.


OpenWrt starts at $OPENWRT_HOST by default. Put the isolated PC Ethernet on
$PC_SOURCE/24 without replacing another interface's Internet default.
Identify/pin the **new OpenWrt host key**, log in as root and set a strong
password. Confirm board/revision, switch/ports, effective MTD protections,
factory MAC and calibration status, Ethernet and memory. This diagnostic
kernel must leave all 17 physical partitions read-only. Do not run sysupgrade
or unlock MTDs from it. Wi-Fi is off by default; use Ethernet initially.

Check a fresh environment readback: valid CRC, trial flag absent and durable
tp_boot_idx absent. A controlled `sync; reboot` was shown to return to stock.
Re-identify stock, its original key and active slot0. If this return is not
proven on your unit, do not proceed to permanent selection.

## 8. Install the protected persistent slot1 image, still as a trial

From stock, repeat the RAM upload, inactive-slot guards and **whole-slot**
ubiformat using the verified protected `tplink_ex511-v2-slot1` factory UBI.
Do not use its sysupgrade tar as a UBI. Read the entire inactive slot and run
check-slot1-image.py with the matching sysupgrade, this readback as `--ubi`,
kernel config and fwtool; require success. Again compare protected hashes.

The final wrapper from step7 is already installed and must match exactly.
Arm only `ex511_trial=1`, verify, sync and reboot. In OpenWrt confirm
`ubi.mtd=rootfs_1`, SquashFS `/rom`, UBIFS `/overlay`, saved configuration and
only rootfs_1 writable. Reboot to stock and arm a second trial to verify
persistence. This stage frees RAM compared with an unpacked initramfs.

## 9. Upgrade to the environment-control image — running protected OpenWrt

Save configuration off-device first. On this 256-MiB unit, RAM staging while
both radios run can OOM. The tested upgrade paused Wi-Fi/services and unloaded
ath11k_ahb, freeing about 40 MiB while wired SSH stayed up; do not assume your
installed modules/services match. Monitor memory, use wired access and do not
load unstripped debug modules. Preserve the original boot policy.

Transfer the verified slot1-env sysupgrade into `/tmp`. Conventional scp may
need `scp -O`; the shell-transfer helper also works with `--user root` and the
OpenWrt key. Check length/hash and byte-for-byte readback, then:

```sh
sysupgrade -T /tmp/slot1-env-sysupgrade.bin
# Only after acceptance, backups, memory and current-profile checks:
sysupgrade -c --no-provisioning /tmp/slot1-env-sysupgrade.bin
```

These exact options were used on this branch: `-c` retains changed /etc files;
`--no-provisioning` retains the three-volume layout. They are not generic
advice for another OpenWrt version. The updater targets rootfs_1 only and
leaves boot policy unchanged, so reboot still returns to stock. Re-arm one
trial from stock, then verify the new env-control profile's two writable
partitions, both DT markers, preserved settings, factory data and networking.

## 10. Select OpenWrt as default only after successful trials

The controller uses BatchMode SSH. First authorize the workstation public key
in OpenWrt /etc/dropbear/authorized_keys (mode 0600, root-owned) and verify
passwordless pinned-key login. Never copy the private key to the router.

Use the **current workstation** boot-policy.py, not an old copied controller.
It requires the exact step7 wrapper, env-control DT marker, all geometry/
protections, a fresh valid environment and an unarmed trial. It refuses an
unknown installation and never reboots automatically:

```sh
python3 scripts/ex511-v2/boot-policy.py snapshot \
  --host $OPENWRT_HOST --source $PC_SOURCE \
  --known-hosts /private/openwrt.keys --output /private/fresh-env.bin
python3 scripts/ex511-v2/boot-policy.py plan \
  --before /private/fresh-env.bin --policy openwrt --output /private/new-plan
# Read new-plan/plan.json. Use a new directory/plan for each transaction.
python3 scripts/ex511-v2/boot-policy.py apply \
  --host $OPENWRT_HOST --source $PC_SOURCE \
  --known-hosts /private/openwrt.keys \
  --reviewed-plan /private/new-plan/plan.json --backup-dir /private/new-write
```

Require the verified full readback/verified.json before a separately issued
`sync; reboot`. Test a default warm boot, deliberate stock return using a
fresh `--policy stock` plan, and a physical cold boot. Do not claim automatic
A/B rollback: a hung kernel cannot run this SSH controller.

## 11. Normal configuration and later upgrades

Use LuCI or UCI to set your own passwords, country, channels, LAN, PPPoE and
IPv6. Do not import the owner's downstream router/ISP scripts as generic defaults. Keep
ordinary kernel flow offloading disabled with this NSS implementation;
it already supplies its own fast path/IRQ placement. See [operation](network-operation.md).

Later upgrades must pass the slot1-env checker and on-device `sysupgrade -T`.
The boot policy remains unchanged; this handler updates the same physical
slot1, not an automatic inactive-bank A/B upgrade. Back up current settings
and preserve stock slot0. Recovery entry is documented in [recovery.md](recovery.md).
