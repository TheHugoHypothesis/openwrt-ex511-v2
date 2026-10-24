# EX511 v2 owner port status — 22 October 2026

Current network role: **EX511 terminates ISP PPPoE and native IPv6; downstream router
receives DHCP WAN and relays IPv6 to its googlespecs clients.** The physical
cutover succeeded. Router IPv4/IPv6 ping and workstation IPv4/IPv6 HTTPS
passed after [post-cutover cleanup](post-cutover-cleanup.md). EX511 LAN1–4
are restored; migration scripts are archived and temporary management rules
removed. Firmware and boot policy are unchanged.

The owner unit now runs OpenWrt persistently from physical NAND slot1 and
selects it by default. Preserved stock remains in slot0. See the
[hardware transition report](slot1-env-hardware-trial.md) for the actual
upgrade, readbacks, configuration preservation and boot-policy tests.

| Component | Evidence and limits |
| --- | --- |
| Current firmware | SNAPSHOT r0+37938-ff5b0529bb8, Linux 6.18.55, October 21 NSS baseline |
| Persistent root | SquashFS `/rom`, UBIFS `/overlay`, configuration hashes preserved across upgrade/reboots |
| Boot policy | Guarded SSH writes/readbacks tested for both stock and OpenWrt; OpenWrt is the saved default; two default warm boots and one owner-confirmed physical cold start verified |
| NAND protection | Only physical rootfs_1 and APPSBLENV writable in the owner env-control profile; other 15 partitions read-only |
| Ethernet | All jacks mapped/tested earlier; current image LAN1/SSH/ping tests pass; repeat full-port/performance tests for broader validation |
| NSS | Routed IPv4 NAT acceleration demonstrated on the earlier initramfs; no new routed performance result from this transition |
| 2.4 GHz | Earlier client traffic passed; AP starts on the current image |
| 5 GHz | Approximately 14 minutes of integrity-checked phone traffic passed on the protected NAND-root image; AP starts on the current image |
| Factory data | Per-unit MAC/calibration provisioning retained; current calibration validation passes; factory partitions protected |
| Recovery | Button-triggered failsafe SSH and bootloader recovery HTTP entry tested earlier; actual recovery firmware upload untested |

Still required: repeated cold-power cycles, prolonged simultaneous
multi-client/dual-band traffic, PPPoE reconnect/prefix-renewal endurance, broader
firewall/isolation tests and repeated future sysupgrades. Actual routed NSS
proof is limited to the earlier isolated IPv4 TCP/NAT flow. Do not infer
production WAN security or every accelerated protocol from it.

There is no automatic A/B fallback for an arbitrary kernel/network hang.
UART currently receives only. Boot-policy changes use a single observed
non-redundant environment; power-loss atomicity has not been established.

The controller runs on the workstation and never reboots automatically.
Use [slot1-env-control.md](slot1-env-control.md) for build/profile details and
fresh-plan selection commands. Images and factory records remain private.
