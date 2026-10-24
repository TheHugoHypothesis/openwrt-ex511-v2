# Failsafe hardware test and boot-policy writer review — 22 October 2026

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

Current follow-up: [slot1-env-control.md](slot1-env-control.md) describes the
separate opt-in firmware, now compiled and checked offline. The historical
review below predates that image. The subsequent [hardware trial](slot1-env-hardware-trial.md)
validated real environment writes and both boot policies.

## Failsafe result

The owner assisted with a real button-triggered failsafe boot of the existing
NAND-root image, OpenWrt SNAPSHOT r37932-a72260511bb / Linux 6.18.55. The
ordinary stock-to-slot1 one-shot mechanism was used to start that image.
The new boot-policy writer described below was **not used**.

The owner identified the chosen button as WPS. Actual UART/hotplug output
reported **`rfkill`**, followed by entry to failsafe. Record this distinction:
the physical button labeling/mapping still needs inspection. The result does
not prove that the DTS's separate GPIO38 WPS definition matches the pressed
button. The `rfkill` DTS definition currently refers to GPIO31. No GPIO or
button definition was changed based on this one observation.

Confirmed on the actual router:

- The failsafe hook accepted the button event and entered `OpenWrt-failsafe`.
- Root SSH worked over the directly cabled LAN1 at $OPENWRT_HOST.
- Root was SquashFS, read-only; the UBIFS overlay was **not mounted**.
- APPSBLENV CRC was valid; both the one-shot flag and durable slot override
  were absent after bootloader handoff.
- No `mount_root`, `firstboot`, `jffs2reset`, firmware write or configuration
  reset was performed inside failsafe.
- A synchronized forced reboot (`sync; reboot -f`, appropriate to early
  failsafe without normal service startup) returned to stock Linux 4.4.60.
  The SSH command timed out as the device reset; UART confirmed the reboot,
  rather than interpreting that connection loss as a failed reset.
- The established stock SSH one-shot flag then returned the same NAND image
  to normal OpenWrt. Its original host key, `/etc` persistence marker, mounted
  overlay and both enabled APs survived. The saved default remains stock.

This validates access to repair a bad writable configuration, not a kernel
or Ethernet failure before preinit. Unlike [bootloader web recovery](recovery-without-uart-input.md),
failsafe still needs a working Linux kernel and basic Ethernet drivers.
Do not mistake entering failsafe for a reset of the configuration.

For reproducing this owner test, use the same observed button, not Reset.
Brief press/release repetitions around the early OpenWrt preinit window
triggered failsafe. Timing depends on the bootloader and firmware. Release
it once failsafe is observed; do not treat a normal-boot rfkill/WPS action as
the same operation. The test PC used a static management IP and kept its
Internet default route on Wi-Fi.

## Review candidate: host-side boot-policy tool

`scripts/ex511-v2/boot-policy.py` is a **review candidate**, not an enabled
feature of the installed firmware. No DTS permissions, image profile,
upgrade compatibility rules or on-router programs were changed to activate
it. The running protected profile still makes APPSBLENV read-only.

The tool has offline `plan` and `verify` commands, plus a guarded future
`apply` backend using root SSH and standard `fw_setenv` batch mode. It only
supports the owner's exact already-observed bootcmd wrapper. It never
changes that wrapper or reboots automatically.

The only planned variable changes are:

| Desired durable policy | `tp_boot_idx` | `ex511_trial` |
| --- | --- | --- |
| Stock | Delete | Delete |
| OpenWrt slot1 | `1` | Delete |

Planning requires the exact 512 KiB partition readback, valid CRC for the
first 256 KiB, a terminated environment without duplicate keys, an unarmed
trial and the known wrapper/slot states. Unrelated environment values are
kept opaque. Plans expose hashes, layout and the two allowed changes rather
than printing other values. The backup itself must stay private.

The future executor refuses unless all of these agree:

- Root, EX511 board identity and a new DT opt-in marker,
  `openwrt,ex511-env-control`, absent from **every current profile**.
- Exactly the 17 physical partitions, each expected offset/size, 128 KiB
  erase size and 2048-byte write size; no duplicate labels/indices.
- Only APPSBLENV and physical slot1 writable, with all other flags read-only.
- No bad blocks reported in APPSBLENV and exactly one UBI boot selection,
  `ubi.mtd=rootfs_1`.
- The live environment is byte-identical to the reviewed plan's input.

It creates an exclusive private backup directory, fsyncs the input and plan,
stages the two-key transaction/config in RAM and checks their SHA256 values.
It checks the live layout and environment again immediately before invoking
**one** standard `fw_setenv` batch. The final full-partition hash check, batch
and readback hold the standard OpenWrt `/var/lock/fw_printenv.lock` flock;
the nested tool uses a private RAM lock directory to avoid self-deadlock.
This cooperates with normal default-lock envtools users; arbitrary root code
using another lock or raw flash access is outside that guarantee.
A durable write-intent record precedes the
call, so an interrupted host process leaves evidence of a possibly started
write. Post-readback must have a valid CRC, exactly the expected variable
map, and an unchanged reserved second half of APPSBLENV.

An ambiguous write result is recorded for inspection. There is no automatic
retry, rollback, raw NAND programming, MTD unlock, bootloader fallback trick
or reboot. This does not make NAND writes power-fail atomic: the observed
configuration is one 256 KiB environment across two erase sectors, not a
verified redundant pair.

## Offline use and validation

On the Linux workstation, with a private raw readback (not a file published
to GitHub):

```sh
python3 scripts/ex511-v2/boot-policy.py plan \
  --before /private/environment.bin --policy openwrt \
  --output /private/new-review-directory
python3 scripts/ex511-v2/boot-policy.py verify \
  --before /private/environment-before.bin \
  --after /private/environment-after.bin --policy openwrt
python3 scripts/ex511-v2/test-boot-policy.py
```

The plan directory contains a backup, a deterministic JSON plan and a
standard-tool transaction. Generating these files does not execute it.
Both stock/OpenWrt plans were generated locally from the owner's read-only
failsafe capture, without using the new write backend on the router.

Nine simulated test groups cover both policies, malformed/duplicate/armed
states, CRC and length failures, exact variable/tail preservation, current
profile refusal, protected partition flags, geometry/bad blocks, a no-op,
stale/concurrent changes and interrupted/unexpected write results. Two optional groups run the **actual packaged AArch64 fw_setenv** under QEMU,
using only temporary regular files on the workstation:

```sh
python3 scripts/ex511-v2/test-boot-policy.py \
  --packaged-rootfs /path/to/extracted-exact-build-rootfs \
  --qemu /usr/bin/qemu-aarch64-static
```

All eleven groups passed. The packaged tool successfully applied both batches
on temporary environment-region files, preserving CRC and the exact expected
variables. The additional lock test confirmed that an occupied outer lock
prevents the write, and that the nested private tool lock does not deadlock. Its regular-file backend replaces the configured region; this is
not an MTD erase, NAND tail-preservation or power-loss test. Tail validation
is separately covered by the simulated readbacks and reviewed source.
The existing eight slot1-upgrade test groups also still pass.

The new read-only preflight was checked against the actual failsafe image:
it refused the absent opt-in marker. No `apply` write was attempted on the
router. No new firmware build is claimed: this change is workstation Python,
tests and documentation; the installed firmware remains unchanged.

## Work before enabling the writer

Update: the separate [slot1-env profile](slot1-env-control.md) now implements
the opt-in DTS and upgrade rules described below. The installed image and
default remain unchanged; the executor still has no real NAND apply test.
The earlier sections record the state at the original review commit.

A future firmware/profile change must deliberately permit APPSBLENV writes,
add the opt-in marker, update the slot1 sysupgrade guard/compatibility rules
(which currently demand exactly one writable partition), and be compiled
and reviewed. Only afterward can a separately authorized hardware write of
the new controller be evaluated with fresh backups and a stable power supply.

The earlier test's known one-shot environment flags must not be confused
with validating this new executor. Its real NAND apply path remains untested.
The root and overlay can already be persistent while durable selection still
returns to stock on reboot; nothing in this review changed that policy.
