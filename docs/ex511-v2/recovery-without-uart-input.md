# Recovery without UART input — owner EX511 V2

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

## Result and boundaries

On 22 October 2026 the owner physically entered the EX511 bootloader's
recovery using Reset. Receive-only UART recorded the recovery message and
web-server startup. A source-bound HTTP **GET** from the directly cabled PC
received **HTTP/1.0 200 OK**, `Server: uIP/1.0`, and the firmware-upgrade form
at **$RECOVERY_HOST**, through **LAN1**. The page was 4,208 bytes.

No firmware upload, POST, flash operation, factory reset or default-slot
change was performed in this recovery test. Entry and page access are now
hardware-tested on this unit. A complete signed-stock restoration is not.
Keep those claims separate.

Leaving recovery by an ordinary power cycle returned to stock Linux 4.4.60
in slot 0; root SSH and the disarmed wrapper were verified. One more stock
SSH arm then restored the existing slot1 OpenWrt without reflashing. The same
OpenWrt SSH key, persistent marker and both APs were verified afterward.
Environment CRC was valid, with no durable slot override or armed trial flag.
The temporary PC recovery address was removed; the Wi-Fi Internet route was
preserved. The unit was left in its normal one-shot OpenWrt state.

The recovery binary is independent of the OpenWrt kernel and overlay. It can
therefore offer a route when Linux or its SSH server cannot start, provided
the bootloader, required board data and hardware still work. It is not a
universal guarantee against NAND/bootloader damage.

## Exact board evidence

The extracted stock U-Boot ELF is an exact prefix of the private APPSBL
readback from this unit (690,754 ELF bytes within the 1,310,720-byte partition).
Its SHA256 is
`bdd58c2187ed7debb4bfe10f41f65ececcd683aab46ab49e90a29f79bbfc2168`.
This ties the static analysis to the owner's actual bootloader rather than
assuming AX55 instructions apply.

Independent Thumb disassembly established:

| Address | Observed purpose |
| --- | --- |
| `0x4a9259a0` | Reads active-low GPIO 25, the Reset input also described by our DTS |
| `0x4a991a44` | Requires Reset already pressed, then a release followed by a press; 500 iterations with 10 ms delay provide the stated 5,000 ms window |
| `0x4a92b0ac` | Calls that button detector in the autoboot path, before the saved bootcmd |
| `0x4a92b0b2`–`0x4a92b0c6` | Prints the recovery message, initializes Ethernet and invokes the literal `httpd` command |
| command-table entry at `0x4a9b5fa0` | Maps `httpd` to Thumb handler `0x4a98d3d0` |
| `0x4a98d3d0` | Prints web-server startup and enters the recovery network loop |
| `0x4a98d328` | Loads the hardcoded recovery address `$RECOVERY_HOST` |
| `0x4a9907d8` | Upload callback calls the firmware validator/upgrader at `0x4a9922d4` |

A previous decompilation report incorrectly named `0x4a98c398` as the HTTP
handler. Its body actually initializes/enumerates Ethernet devices. Also,
the examined `do_bootipq` branch after two loader failures initializes
Ethernet and returns failure; that call alone does not prove automatic HTTP
startup. The physically tested button route does invoke `httpd` explicitly.

## Tested entry procedure

Keep the production Internet router separate. Connect the PC to EX511 LAN1.
Use PC **$RECOVERY_PC/24**, no Ethernet default gateway or DNS override. Keep
other management subnets if needed; preserve the PC's Wi-Fi default route.

1. Synchronize a running writable OpenWrt overlay before the planned power-off.
2. Power off only the EX511.
3. Hold Reset while powering it on.
4. When LEDs blink rapidly / UART prints the release-and-press prompt,
   release Reset and press it again immediately, within five seconds; release
   it again. Do not keep holding Reset into an ordinary Linux boot.
5. Verify `Enter firmware recovery mode!` and `Start web server.` on receive-only
   UART when available. UART input is not required.
6. Wait for LAN negotiation, then GET `http://$RECOVERY_HOST/`.
7. To leave this no-upload test, power off/on without holding Reset.

The successful capture showed the prompt followed by recovery entry roughly
two seconds later. The server initially reported all LAN PHYs down; it retried
and selected the connected switch port once negotiation completed. That
startup delay was not a failure to enter recovery. Do not infer that other
jacks were tested.

## Stock upload is a different, untested action

The existing stock-firmware analysis and validator call chain show global
checksum and TP-Link RSA signature validation before programming. This is
not an unsigned OpenWrt installation endpoint. An original, correct regional/
ISP/hardware stock package must be checked before using the form.

The examined upgrader can also program the shared APPSBL bootloader when a
package contains a bootloader payload. It writes the opposite firmware bank
according to the slot selector and saves a changed selector afterward.
Uploading stock is consequently more invasive than selecting the already
preserved stock bank. Do not use it merely to test whether the web page works.
A successful GET does not validate the image acceptance, write, reboot or
subsequent boot-policy behavior.

## SSH return and the current protection limit

**Current one-shot profile:** a normal SSH `sync; reboot` returns to stock
slot 0, because U-Boot already cleared/saved the one-shot flag before Linux
started. This return has been hardware-tested. Stock root SSH can then arm
one more slot1 boot using the established owner-specific wrapper.

**If slot1 were made the durable default:** merely rebooting would select
slot1 again. The present slot1 profile deliberately makes APPSBLENV read-only
(`mtd7` flags `0x0`) and has no generated `/etc/fw_env.config`. The binaries
`fw_printenv`/`fw_setenv` exist, but their presence is not a working slot-switch
interface. Stock reports `/dev/mtd7 0x0 0x40000 0x00020000 0x2`;
the two erase sectors describe one 256 KiB environment area, not proof of
a second redundant environment. Do not recommend plain `fw_setenv tp_boot_idx ...` on this build,
weaken MTD flags through an ad-hoc module, or erase the custom kernel to force
fallback.

A maintainable future SSH slot-control profile would need a deliberate DTS
permission change for APPSBLENV, the observed environment geometry,
validated CRC/backup handling and an explicit boot-policy helper. The upgrade
guard currently requires exactly one writable partition and would need
corresponding review. Such a change would be a new build/protection decision,
not something silently enabled during this investigation. Even a correct
slot-switch helper cannot run when the kernel/SSH is dead.

The subsequent [boot-policy review candidate](failsafe-and-boot-policy-review.md)
provides offline planning/verification and a future opt-in SSH executor.
It was not activated in an image or used for a NAND write. Current MTD
protections and boot policy are unchanged.

## OpenWrt failsafe over SSH

The actual image includes the normal four-second failsafe wait, GPIO button
handling, the failsafe Dropbear hook and the default $OPENWRT_HOST address.
Kernel config builds MDIO, STMMAC and IPQ5018 DWMAC in. The Realtek DSA module
is in `modules-boot.d` and the hardware log showed switch setup completed
before preinit; LAN1 came up during preinit before NSS initialization. Thus
network recovery does not inherently require the later NSS services.

The upstream preinit code selects the first LAN DSA port (`lan1` in our board
definition) and starts failsafe SSH before mounting the writable overlay.
The subsequent [22 October failsafe test](failsafe-and-boot-policy-review.md)
confirmed actual button entry and root SSH on LAN1, with the overlay unmounted.
The owner identified the button as WPS, while hotplug reported `rfkill`;
physical labeling/mapping remains to be checked. This can help repair a bad
network/firewall/overlay configuration without UART input. It cannot repair
a kernel that fails before preinit or guarantee recovery from a broken
Ethernet driver.

Generic documentation, subordinate to the owner-specific evidence above:
[OpenWrt failsafe](https://openwrt.org/docs/guide-user/troubleshooting/failsafe_and_factory_reset)
and [TP-Link firmware recovery](https://www.tp-link.com/us/support/faq/1482/).
The vendor FAQ is general guidance, not EX511-specific proof.
