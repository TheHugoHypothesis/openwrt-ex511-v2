# Controlled NSS/factory-data test plan

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

This is a staged test plan, not a checklist of passed tests. See
[hardware-results.md](hardware-results.md) for actual owner observations,
including a stock SSH trial, short traffic tests and unresolved memory and
authentication failures. WAN isolation has not been validated and must not
be trusted as a WAN boundary yet. Keep the production
router and Internet connection available while testing a disconnected EX511.

The subsequent [NAND-root trial](nand-root-hardware-trial.md) and
[recovery test without UART input](recovery-without-uart-input.md) record
the current installation and recovery evidence. Bootloader recovery entry
and its HTTP page were tested; a stock restoration upload was not.
The [failsafe follow-up](failsafe-and-boot-policy-review.md) also confirmed
actual root SSH without mounting the overlay. The new boot-policy writer
was initially a workstation-side review candidate. The subsequent
[env-control hardware trial](slot1-env-hardware-trial.md) installed the opt-in
image, tested both policy directions, two default warm boots and one
owner-confirmed physical cold start, and left OpenWrt as the saved default.
The plan below retains the earlier diagnostic steps; consult that report
for completed operations and remaining recovery limits.

1. Preserve the stock full NAND dump, extracted factory volumes, boot logs,
   partition table and a known recovery image. Keep private data outside
   public repositories. Verify backup checksums and store a second copy.
2. Establish the available recovery path first. Identify the owner's PCB revision and
   measure UART voltage/pinout; do not rely solely on another unit's labels.
   This owner has receive-only UART; retain adapter RX and ground, with
   adapter TX disconnected after the earlier feedback problem. Never connect
   adapter VCC. Record a complete normal boot at the verified baud. Do not
   treat readable UART as an interactive recovery console.
3. Inspect U-Boot's existing environment and RAM load addresses without
   saving changes. Confirm which commands support RAM-only kernel boot and
   which NAND/UBI recovery path applies. Review the exact FIT and memory map
   before preparing any load/boot command. This document intentionally does
   not prescribe an unverified installation or stock SSH flash command.
4. First boot the initramfs into RAM with all production uplinks unplugged.
   Capture serial output continuously. Do not invoke sysupgrade, firstboot,
   mtd write, ubiupdatevol, ubiformat, saveenv or recovery flashing.
5. Confirm the model and all 17 MTD partitions. `misc_data_ro`, ART, APPSBL
   and other protected partitions must be read-only. The diagnostic
   `tplink_ex511-v2-initramfs-test` profile makes all 17 partitions read-only.
   The dedicated NAND-root slot1 profile makes only physical `rootfs_1`
   writable. The separate owner `slot1-env` profile also permits APPSBLENV
   writes for the guarded host controller; all other physical partitions
   stay read-only. The legacy base layout is not the protected installation
   profile. Confirm `misc_data_ro` UBI attaches
   read-only and helper mounts/attachments are cleaned up. Check that the
   factory volume's contents and backup checksum remain unchanged.
6. Compare addresses privately against the stock observations: conduit,
   LAN and default 2.4 GHz AP use base; 5 GHz AP uses base +2. A WAN allocation
   of base +1 exists in board defaults. Check the runtime topology and
   ensure WAN remains outside br-lan under the expected DSA defaults. Verify guest/STA addresses remain unique. Repeat with
   an existing explicit Wi-Fi MAC override; it must remain intact.
7. Test one isolated LAN client, then each of the five jacks. Verify port
   label, 1000/full negotiation, ARP, DHCP, ping and bidirectional transfer.
   The CPU link must be SGMII 1000/full. A fixed-link carrier message alone
   is insufficient. Confirm traffic counters on the switch, GMAC and NSS.
8. Check NSS boot messages, `nss-status` and NSS/ECM counters before and
   during transfers. Wi-Fi and wired offload must be distinguished from
   simple connectivity. A successful association or speed test alone does
   not prove hardware offload. Do not change upstream topology during the
   initial comparison. Confirm the runtime tagger is rtl8365mb-8021q and
   test WAN/LAN isolation explicitly before relying on the WAN label.
9. Confirm both ath11k PHYs, factory/BDF country/FEM agreement and EEPROM
   validation. Check that external calibration is 128 KiB and only the RAM
   copy has its MAC/selection flag/checksum adjusted. Do not publish EEPROM
   bytes or MAC addresses in reports. Verify the private BDF hash against
   its provenance marker, regulatory country and allowed channel/power
   limits. Start with an allowed non-DFS channel; exercise DFS only through
   the normal regulatory mechanisms.
10. Test 2.4 and 5 GHz scanning, AP and client traffic separately, then
    together under NSS load. Capture failures, remoteproc restarts, memory
    availability, NSS buffer counts, drops and errors. Firmware 12.5 on this
    256 MB unit requires particular memory/stability validation. The upstream
    integrated-radio dummy calibration is still a limitation.
11. Record cold-power and warm-reboot results only when explicitly authorized
    to reboot during the hardware session. After a warm restart verify switch
    reset, SerDes lock, PHYs, both radios and NSS again. Run longer dual-radio
    tests and service restart tests before making this the production default.
12. Review installation separately. The dedicated slot1 handler updates only
    physical slot1 and leaves boot policy unchanged; the inherited EX511
    BOOTCONFIG writer was removed. A compiled sysupgrade image is not
    a stock-web/SSH factory installer. Establish a verified recovery procedure
    and inspect slot/UBI assumptions before authorizing any persistent write.

Stop testing if factory data cannot be read safely, addresses collide, the
switch/NSS topology differs, memory exhaustion occurs or firmware repeatedly
crashes. Preserve serial logs and return to the known recovery path rather
than guessing register values or flash offsets.
