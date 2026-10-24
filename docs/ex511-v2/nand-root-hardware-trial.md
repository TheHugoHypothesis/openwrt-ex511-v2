# Owner NAND-root trial — 21–22 October 2026

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

## Scope and image

This records the owner's authorized SSH installation of the dedicated
physical-slot-1 candidate. It concerns this EX511 V2, its bootloader and its
privately provisioned board data. It is not a generic stock installer or
proof of production readiness.

- Compiled firmware: `a72260511bb9bb73d28a2f83f3e9ef7c191ae41d`.
- Running identification: OpenWrt SNAPSHOT `r37932-a72260511bb`, Linux 6.18.55,
  NSS firmware 12.5, with the extra 256 MiB ath11k/NSS allocation profile.
- Factory UBI SHA256:
  `f4d4425657e6def4a3e20fcc9f4a4363d8d081399840c1998b54aadf0bf6f289`.
- Matching sysupgrade SHA256:
  `6cf4eb3f7cfef85f034964708b70bd2ccc3ef3ae0df0d0e2be27cd2926a0bfaf`.

See [oct21-slot1-validation.md](oct21-slot1-validation.md) for the build and
image validation, and [persistent-slot1.md](persistent-slot1.md) for the
layout and upgrade design. Images, raw backups, serial logs and credentials
remain private.

## Write and readback

The previous read-only initramfs was rebooted to preserved stock in physical
slot 0. Stock UART output, root SSH, boot selection, labels, geometry,
inactive-slot attachment state and the disarmed one-shot wrapper were checked
again. The workstation kept its Internet default route on Wi-Fi through the
downstream router; EX511 used the separate directly cabled Ethernet link.

Fresh exact-length backups covered both firmware slots, APPSBLENV, APPSBL and
both BOOTCONFIG copies. Stock firmware and the bootloader/BOOTCONFIG hashes
matched the preserved original backups. The environment CRC was valid.

A preflight initially stopped without writing because stock's ramfs reports
zero capacity in `df`. The stock `/tmp` link and ramfs mount were then checked
explicitly; available RAM, rather than a nonexistent ramfs block quota, was
used as the capacity gate. The image was uploaded into stock RAM and compared
byte-for-byte before programming.

Only the label-resolved inactive `rootfs_1` was formatted/programmed. A complete
38,141,952-byte physical readback passed the UBI CRC/layout checks and
reconstructed every intended kernel and SquashFS byte. Fresh post-write reads
of stock `rootfs`, APPSBLENV, APPSBL and both BOOTCONFIG copies matched their
pre-write hashes. No factory/calibration partition was programmed.

The separate `ex511_trial` flag was then armed using the previously tested
wrapper. Its saved environment CRC and absence of a durable `tp_boot_idx`
override were checked before reboot. U-Boot cleared and saved the trial flag
before selecting slot 1 in RAM.

## First NAND-root boot

UART verified the FIT hashes and showed Linux attaching physical mtd14,
`rootfs_1`, as ubi0. The effective command line retained stock's earlier root
name but appended `root=/dev/ubiblock0_1`; the latter selected the OpenWrt root.

| Runtime observation | Result |
| --- | --- |
| UBI volumes | kernel ID 0: 36 LEBs; rootfs ID 1: 84; rootfs_data ID 2: 147 |
| First autoresize | U-Boot resized rootfs_data from 9 to 147 LEBs |
| NAND bad PEBs reported | 0; 20 PEBs reserved for bad-block handling |
| `/rom` | SquashFS, read-only |
| `/overlay` | UBIFS, read-write, `/dev/ubi0_2` |
| `/` | overlayfs using the UBIFS upper/work directories |
| Overlay space on first inspection | 14,908 KiB filesystem, 13,796 KiB available |
| Physical protection | Exactly 17 MTD partitions; only `rootfs_1` writable |
| Environment after handoff | CRC valid; `ex511_trial` and durable `tp_boot_idx` absent |
| LAN1 | 1000 Mb/s, full duplex; 5/5 PC pings |
| SSH | Source-bound root SSH on the direct LAN link |
| LuCI | Rendered its login page; unauthenticated HTTP 403 carried `x-luci-login-required: yes` |
| NSS | Core 0 booted and Ethernet selected the NSS firmware data plane |
| Both ath11k radios | Registered; both logged the extra 256 MiB NSS allocation profile |
| Upgrade validation | Actual matching archive passed `sysupgrade -T` with exit 0 |

The archive uploaded for `sysupgrade -T` was SHA256-checked on the router and
removed afterward. The command was validation only. **An actual in-place
OpenWrt-to-OpenWrt sysupgrade has not been exercised.**

## Memory observations

The pre-transition running initramfs reported Shmem 35,376 KiB. The first
NAND-root collection reported Shmem 232 KiB and MemAvailable 40,628 KiB, with
the APs disabled. This demonstrates removal of the large resident initramfs
filesystem; it is not a controlled before/after comparison of total available
memory under identical radio/client/load conditions.

The previous private test SSIDs/passphrase were restored to the slot1 overlay,
with BR country settings, channel 1 HE20 and channel 36 HE80. Both APs were up
through seven samples over approximately one minute. MemAvailable ranged from
29,236 to 33,096 KiB; Shmem ranged from 276 to 296 KiB and `oom_kill` remained
zero. Neither AP had a client at the explicit station-count check. These are
short idle measurements, not simultaneous traffic, authentication reliability
or an OOM-fix result.

## Persistence and return-to-stock cycle

A unique non-secret marker was written under `/etc`, synchronized and compared
with its file in `/overlay/upper/etc`. A controlled reboot then returned to
stock Linux 4.4.60. Stock SSH verified physical slot 0, valid environment CRC,
and absence of both the trial flag and a durable slot override.

The same image was then entered again through the one-shot stock SSH flag,
without reprogramming either firmware slot. Strict SSH verification accepted
the same OpenWrt host key. The unique `/etc` marker and both test AP SSIDs and
passphrases survived. Both APs returned to ENABLED without reapplying their
configuration. The root/overlay mounts, 17 partition flags and environment
CRC/cleared selection flags were checked again successfully.

On the 22 October continuation, this second boot had exceeded three hours of
uptime. Both APs were ENABLED, with zero clients at the explicit check;
MemAvailable was approximately 22 MiB, Shmem 276 KiB and `oom_kill` zero.
There was no deliberate client traffic load in this interval. This is
evidence of idle operation, not a sustained-load result or a continuous
three-hour serial capture. The external calibration file also passed the
EX511 EEPROM size/header/checksum verifier on the running system.

The unit is left running this second NAND-root boot, with the private test
AP configuration saved in its overlay. The saved environment still selects
stock after the next reboot; OpenWrt was not made the permanent default.

## Remaining hardware work

- Repeat phone association and byte-integrity traffic on both bands with this
  exact updated build; investigate the earlier first-association retry.
- Exercise sustained mixed traffic, multiple clients, recovery after load and
  longer memory sampling before treating memory exhaustion as resolved.
- Repeat all-port, routed NSS/ECM, isolation and throughput tests on this build.
  The older initramfs results do not automatically validate the new base.
- Test the dedicated in-place sysupgrade after preserving configuration/backups.
  Its handler writes only slot 1 and leaves boot policy unchanged.
- PPPoE, upstream IPv6, IPTV/voice integration, cold resets and recovery testing
  remain outside this trial.

No durable OpenWrt default was selected. During a one-shot boot, sysupgrade
would update slot 1 but its reboot would return to stock. A separate stock-SSH
arm is required to enter slot 1 again. Do not assume AX55 web recovery applies
to EX511 or that receive-only UART can issue recovery commands. Selecting
OpenWrt permanently needs a separate recovery/boot-policy decision.
