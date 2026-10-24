# Owner slot1 upgrade and durable boot selection — 22 October 2026

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

## Result

The owner authorized the controlled transition after image preparation.
The EX511 v2 now runs the environment-control image from physical slot1,
with **OpenWrt selected as the durable default** (`tp_boot_idx=1`).
The one-shot `ex511_trial` flag is absent and the pre-existing owner bootcmd
wrapper is unchanged. This is persistent NAND root, persistent UBIFS
configuration and persistent boot selection, rather than an initramfs trial.

Firmware remains the compiled source `ff5b0529bb8`, packaged as OpenWrt
SNAPSHOT `r0+37938-ff5b0529bb8`, Linux 6.18.55. Host-controller fixes and
this report do not change the installed firmware binary. Artifact hashes
are in [slot1-env-validation.md](slot1-env-validation.md).

## Authorized hardware sequence

1. Checked the old protected slot1 image, all 17 physical partition flags
   and geometry, saved stock policy, live LAN1 and disconnected WAN.
2. Saved fresh complete external backups of APPSBLENV, both BOOTCONFIG
   copies, APPSBL, stock rootfs and the running rootfs_1. Exact transfer
   lengths and independently calculated device/host SHA256 values matched.
   Stock/APPSBL/BOOTCONFIG matched the original preserved backups.
3. Paused both APs, wpad, uhttpd and rpcd without disabling services or
   changing UCI configuration. Pausing services alone did not free enough
   RAM. Unloading ath11k_ahb stopped the radios/Q6 and released about 40 MiB;
   Ethernet SSH remained usable. Before image staging MemAvailable was
   58,356 KiB and the OOM counter remained zero.
4. Copied the exact candidate into RAM, verified its length/SHA256 and
   read it back byte-for-byte. Actual `sysupgrade -T` accepted the image.
   Rechecked saved policy and protected-partition hashes before writing.
5. Ran standard `sysupgrade -c --no-provisioning` with no force flag.
   The old profile permitted writes only to physical rootfs_1. `-c` retained
   changed `/etc` files, including the existing persistence marker, and
   `--no-provisioning` retained the three-volume UBI layout. UART recorded
   `sysupgrade successful` and a return to stock Linux 4.4.60. The SSH call
   timed out across the upgrade/reboot; UART established the outcome and
   the firmware write was not repeated.
6. Verified the complete environment unchanged after that upgrade. Used
   the existing stock SSH one-shot mechanism to boot the new slot1 image.
7. Verified new revision, both DT markers, exactly APPSBLENV/rootfs_1
   writable, mounted SquashFS/UBIFS, byte-identical saved configuration,
   enabled APs, LAN connectivity and factory calibration validation.
8. Applied a fresh reviewed OpenWrt boot-policy plan, checked its CRC,
   exact variable map and unchanged reserved partition tail, then rebooted.
   UART and SSH confirmed a new OpenWrt boot without arming a one-shot flag.
9. Applied and verified the reverse stock policy using the controller and
   rebooted. Stock Linux 4.4.60 and its root SSH path worked. During this
   return stock LAN forwarding appeared around 93 seconds after kernel
   start, beyond the first bounded poll. A later read-only probe confirmed
   reachability; no configuration or flash workaround was required.
10. Used stock SSH one-shot selection again, verified the new OpenWrt, then
    applied the final reviewed durable OpenWrt policy. A second default
    warm reboot returned to the new OpenWrt and passed the same checks.

All four new-image boots in this sequence passed the host checks. On each,
the UBI kernel and SquashFS payload readbacks matched the uploaded sysupgrade
byte-for-byte. Stock rootfs, APPSBL and both BOOTCONFIG hashes remained
unchanged. All `/etc/config/*` files and the persistence marker matched
pre-upgrade hashes. Calibration verification passed; both APs were enabled,
LAN1 linked and five LAN pings succeeded. Recorded OOM counters were zero;
retained logs contained no firmware-crash/OOM/panic marker.

No stock image, bootloader, BOOTCONFIG, factory data or calibration partition
was programmed. The only firmware destination was rootfs_1. Boot selection
writes used the explicitly writable APPSBLENV and standard envtools; the
controller retained its before/after backups outside the router. UART was
receive-only. The workstation's production Internet default stayed on Wi-Fi;
the EX511 WAN was disconnected.

## Physical cold-start confirmation

After the warm-boot sequence, the owner confirmed the requested unplug/replug
power-cycle of the EX511. A fresh receive-only UART capture recorded PBL/SBL,
U-Boot and a new Linux 6.18.55 boot. SSH confirmed the same installed image
and durable OpenWrt selection without any one-shot flag.

This fifth checked new-image boot passed the same full layout, exact kernel/
rootfs readback, unchanged protected hashes/configuration, calibration,
two enabled APs, LAN1 and five-ping checks. OOM remained zero, with no retained
firmware-crash/panic marker. This is one physical cold start, not a repeated
power-cycle endurance test or an interrupted-write test.

## Controller cleanup defect found and fixed

The first real `apply` completed the NAND transaction, full readback and
`verified.json`, then exited with a generic SSH error during RAM cleanup.
The nested `fw_setenv -l` creates `fw_printenv.lock` in the private staging
directory; the initial cleanup omitted that file, so `rmdir` failed.

Work stopped for a read-only inspection. A fresh complete environment
readback exactly matched the saved successful post-write capture. CRC,
expected variables and the partition tail verified; no write was retried.
Only the known temporary RAM lock was then removed.

The host tool now removes its private lock file and records cleanup failure
separately instead of masking a verified transaction. Thirteen offline test
groups pass, including actual packaged ARM envtools/lock-file cleanup under
QEMU and an injected cleanup failure after successful verification. The
subsequent real stock-selection and final OpenWrt-selection transactions
both verified and cleaned up successfully. No firmware rebuild/reflash was
needed for this workstation-side correction.

## Limits and next tests

This establishes the controlled upgrade and bidirectional SSH boot-policy
path on this owner's unit. It is not automatic A/B rollback: a kernel that
hangs before usable Linux networking may still require bootloader recovery.
The earlier physical recovery test established Reset entry and HTTP page
access, not a completed firmware restoration. Environment power-loss
atomicity/redundancy is not established.

The earlier 13-minute-51-second 5 GHz load result belongs to the protected
NAND-root image. The new image retains its hardware/radio definitions and
APs start successfully, but that traffic test was not repeated in this
transition. Multi-client/dual-band long load, PPPoE/IPv6, broader firewall
isolation and repeated future sysupgrades remain separate tests.

Raw logs, full backups, config hashes and calibration evidence remain in
private local storage. No private firmware binary or device dump is published.

Two default warm reboots and one owner-confirmed physical cold start have
now passed. Repeated power cycles remain a future stress test.
