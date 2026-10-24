# Recovery: available paths and their limits

A preserved stock slot is valuable, but **not automatic A/B rollback**.
The bootloader may fall back if a kernel fails to load; it does not necessarily
recover when a loaded kernel hangs. UART on the owner unit receives logs only.

## 1. Working OpenWrt SSH: deliberately choose preserved stock

On the final slot1-env profile use the workstation controller with a fresh
snapshot and `plan --policy stock`, then reviewed apply; see
[installation step10](installation-ssh.md#10-select-openwrt-as-default-only-after-successful-trials).
This removes the durable tp_boot_idx override and preserves the exact wrapper.
Require verified.json/full readback before a separate reboot. The controller
refuses a different bootcmd, corrupt environment, unknown geometry or the
protected profile. Do not bypass those refusals with raw environment writes.

Stock root SSH can re-arm ex511_trial=1 using the already-verified wrapper;
that next boot selects slot1 only in RAM after clearing/saving the flag.
The controller cannot run when Linux/networking is dead. A successful policy
change is not proof of power-fail-atomic or redundant APPSBLENV.

## 2. Kernel/Ethernet work: button-triggered OpenWrt failsafe

This image has a four-second preinit failsafe window. The owner triggered
failsafe using the physical button identified as WPS; the kernel event was
rfkill. Confirm mapping/timing on another PCB. Failsafe root SSH was actually
reached on **LAN1 at $OPENWRT_HOST**, with the overlay unmounted.

Use an isolated PC at $PC_SOURCE/24 without a competing DHCP/default route.
Identify the host key deliberately and follow OpenWrt failsafe practices.
Do not run firstboot/factory-reset merely to test entry: it destroys saved
settings. Failsafe can repair configuration; it cannot fix a kernel that
never reaches preinit or a nonfunctional switch driver.

## 3. Bootloader Reset HTTP entry — no UART input

Physically tested without uploading firmware:

1. Isolate the EX511 and connect PC to LAN1 at $RECOVERY_PC/24.
2. Synchronize a working writable overlay before planned power-off.
3. Hold Reset while powering on.
4. At the rapid LED/release-and-press prompt, release and press again within
   five seconds, then release. Do not keep holding into ordinary Linux boot.
5. Receive-only logs, when available, showed `Enter firmware recovery mode!`
   and `Start web server.`. Wait for Ethernet negotiation/retries.
6. Open http://$RECOVERY_HOST/; the owner received HTTP 200.
7. To leave this **no-upload test**, power off/on without holding Reset.

The second press is important on this observed bootloader; do not replace it
with an AX55-specific ten-second instruction. See the
[bootloader investigation](recovery-without-uart-input.md) for evidence.

## Restoration upload is not validated

The recovery validator checks TP-Link signatures/checksums. It is not an
unsigned OpenWrt installation endpoint. Another model/region/ISP package is
not a safe substitute. The examined updater may also write the shared
bootloader when such payload is present. **No recovery image was uploaded
in our test**, so image acceptance, write and subsequent boot are unresolved.
Do not claim that web recovery "always works" for EX511 from an AX55 article.

If recovery is required, match the exact stock package and independently
review the validator/write path. Keep original off-device backups. Do not
erase a kernel to provoke fallback or blindly write raw NAND images with
different OOB/bad-block assumptions. RX-trace soldering has no tested EX511
location in this project; see [hardware findings](hardware.md).
