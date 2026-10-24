# What was tested, on which image

All owner measurements concern one physical EX511 V2. Contributor results
are credited separately. Logs/dumps/identifiers remain private; the repository
contains sanitized reports, not every raw capture. A configuration that works
for this owner is not proof of every regional/ISP hardware variant.

## Firmware and installation

| Item | Evidence | Limit |
| --- | --- | --- |
| Firmware identity | Linux 6.18.55, SNAPSHOT r0+37938-ff5b0529bb8 | This is the deployed build, not a stable OpenWrt release |
| Stock SSH installation | Kernel-only UBI to inactive rootfs_1, exact FIT reconstructed from NAND readback | Root already available; observed with receive-only UART |
| Persistent root | SquashFS /rom and writable UBIFS /overlay in physical slot1 | Original read-only initramfs had no persistent overlay |
| Controlled upgrade | Protected slot1 -> slot1-env sysupgrade retained configuration | One controlled transition, not repeated upgrade/power-loss testing |
| Default selection | Guarded SSH controller tested in both directions; OpenWrt saved default | No automatic recovery from arbitrary kernel hang |
| Reboots | Two default warm boots and one owner-confirmed physical cold start on final profile | Not endurance testing |
| Protected data | Stock, APPSBL and BOOTCONFIG hashes preserved across recorded writes; factory partitions untouched | APPSBLENV is intentionally writable in final profile |
| Recovery | Button-triggered failsafe SSH; Reset bootloader HTTP page returned 200 | Actual stock upload/restoration untested |

Details: [initial SSH trial](ssh-trial.md), [persistent trial](nand-root-hardware-trial.md),
[final firmware validation](slot1-env-validation.md), [actual controller/upgrade tests](slot1-env-hardware-trial.md).

## Ethernet, radios and NSS

| Test | Observed result | Correct interpretation |
| --- | --- | --- |
| LAN1–4 | Each negotiated 1000/full and passed 5/5 pings in earlier tests | Physical port mapping/traffic; not sustained throughput on every jack |
| Isolated routed IPv4 NAT, earlier initramfs | Phone -> WAN-side PC, integrity passed; 395.69 / 289.51 Mbit/s down/up | Matching ECM flow reported accelerated; not PPPoE line-rate benchmark |
| 2.4 GHz earlier bounded integrity loop | 37 successful cycles in 60.47 s; mean directional rates 173.21 / 87.26 Mbit/s | One client; arithmetic per-transfer means |
| 5 GHz earlier bounded integrity loop | 101 successful cycles in 60.42 s; mean directional rates 518.55 / 232.85 Mbit/s | Initramfs memory headroom subsequently reached zero; not a stability result |
| 5 GHz persistent protected image | 1,118 integrity-checked 16-MiB down / 8-MiB up cycles over 830.9 s | Approx. 14 minutes, one phone; test interrupted before planned finish |
| Same persistent 5-GHz test | Mean per-cycle down/up 481.0 / 167.4 Mbit/s; 17,888 / 8,944 MiB validated | Not whole-session sustained rate; pauses/validation not included |
| Current gateway, 24 October | Active accelerated ECM IPv4 and IPv6 connections; NSS plane up | Does not prove all protocols/flows accelerated or quantify speedup |

The long phone test used **r37932-a72260511bb**, the earlier protected NAND-root
image, not a repeated 14-minute load on the final environment-control image.
The final image retains the radio/memory definitions; do not merge those two
facts into an unperformed test. [Original measurements](hardware-results.md)
and [persistent phone report](persistent-5ghz-load-test.md) retain the details.

Initial 5-GHz association sometimes failed on the first attempt and succeeded
on retry. This is a known observation, not proven fixed. The first initramfs
allocation profile OOM-killed hostapd/wpa_supplicant. The additional NSS 256-MiB
profile and NAND root improved the measured headroom; they do not establish
unlimited multi-client stability. Persistent load monitoring covered 412.7 s
of the 830.9-s traffic window; full-session continuous monitoring is not claimed.

## Real gateway deployment and IPv6

The owner completed EX511-as-main-router cabling on 24 October:

```text
ISP bridge -> EX511 PPPoE / native DHCPv6-PD /64
                 EX511 LAN -> downstream router DHCP WAN
                                downstream router main LAN: IPv6 relay
```

After removing temporary management/uplink rules and archiving migration files:

- Both routers passed Internet IPv4 and IPv6 ping, 3/3 each.
- A workstation on downstream router main LAN fetched HTTPS forced to IPv4 and separately
  forced to IPv6, both HTTP 200. This validates a real downstream relay path.
- EX511 LAN1–4 returned to br-lan. Only the actual WAN terminates PPPoE.
- fw4 check passed on both; configuration cleanup did not reflash/reboot them.
- DHCPv6 explicit prefix hints /56 and /60 were separately tested; the client
  ran with each requested length, but received /64. Automatic requests were
  restored and IPv6 ping passed 2/2 after each experiment. No DHCPv6 identity
  rotation or deliberate PPPoE redial was used to seek a larger prefix.

The /64 result establishes these negotiations, not a universal ISP policy or
proof that the subscriber can never obtain a larger prefix. Details:
[deployment/cleanup](post-cutover-cleanup.md), [operation](network-operation.md).

## Remaining work

- Repeated cold boots, future sysupgrades and renewal/reconnect endurance.
- Multi-client simultaneous dual-band load and prolonged memory monitoring.
- Full WAN/LAN/VLAN/IPv6-relay isolation and all-port throughput tests.
- Controlled NSS on/off comparison, PPPoE performance and more protocol coverage.
- Actual vendor recovery restoration; environment power-loss behavior.
- Another owner's independent stock-to-OpenWrt installation with sanitized evidence.
- Physical confirmation or rejection of the RX-gap hypothesis.
