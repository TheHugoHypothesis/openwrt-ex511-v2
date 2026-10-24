# Native IPv6 behind downstream router — 22 October 2026

> **Anonymized deployment case study.** Addresses and local checkpoint paths
> are placeholders, not usable configuration. Operator-specific automation
> is not published; this report preserves topology, observations and limits.

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

downstream router remains the production PPPoE router. EX511 remains a bridged access
point connected through LAN2. The previous migration troubleshooting profile
explicitly disabled PPP IPv6, wan6, and downstream RA/DHCPv6. This was a
configuration omission in the production topology, not evidence of an EX511
driver failure.

## Saved changes

Only these UCI options changed on downstream router:

```text
network.wan.ipv6=1
network.wan6.disabled=0
network.googlespecs.ip6assign=64
dhcp.googlespecs.ra=server
dhcp.googlespecs.dhcpv6=server
dhcp.googlespecs.ra_slaac=1
dhcp.googlespecs.ra_flags=[other-config]
```

The existing explicit wan6 DHCPv6 client on @wan, prefix request, DHCPv6
identity and vendor class were retained. SLAAC remains enabled for clients
that do not use stateful DHCPv6. NDP relay remains disabled. The existing
RA MTU of 1480 matches the PPP configuration.

ISP actually delegated one /64 in this session. It is assigned to the
$DOWNSTREAM_NETWORK/24 googlespecs network shared by downstream router, EX511 and clients. The
separate legacy downstream router LAN was not assigned this same routed /64.

PPPoE credentials, cloned WAN MAC, MTU, IPv4 addressing/DHCP, custom DNS and
adblock settings were preserved. Firewall configuration was byte-identical;
existing WAN DHCPv6 and ICMPv6 rules were sufficient. No NAT66 was added.
No firmware, boot environment, EX511 network configuration or wireless
credentials were changed. Configuration files were saved persistently;
there was no deliberate router reboot or post-change cold-boot test.

## Validation

- downstream router wan and wan6 are up. A public WAN IPv6 address, delegated /64 and
  IPv6 default routes were observed. The /64 is assigned to googlespecs.
- downstream router IPv4 Internet ping: 3/3. IPv6 Internet ping: 3/3.
- downstream router HTTPS forced to IPv6: HTTP 200 from openwrt.org.
- Existing downstream router local DNS returns an AAAA answer for openwrt.org.
- EX511 lan6 is up, has global IPv6 addresses and a default route through
  downstream router. EX511 Internet IPv6 ping: 3/3. Its odhcpd remains disabled, as intended
  for this bridged AP; clients use downstream router advertisements directly.
- The workstation acquired an IPv6 route through downstream router Wi-Fi and successfully
  fetched HTTPS forced to IPv6 (HTTP 200). Its IPv4 default was retained.
- Comparing parsed before/after UCI files found precisely the seven options
  listed above; no other network/DHCP option changed. Firewall was unchanged.

No phone IPv6-only test through EX511 Wi-Fi, prolonged IPv6 transfer,
renewal/reconnect endurance or IPv6 NSS acceleration test is claimed.
This also does not validate EX511 as a routed PPPoE gateway.

## Backup and recovery

Raw configurations and network observations are private because they contain
ISP credentials and per-device identifiers. downstream router has a root-only checkpoint
at <PRIVATE_CHECKPOINT>, including network, dhcp and firewall backups,
a manual rollback script and a bounded IPv4 guard. The guard observed IPv4
up and kept the new configuration; the successful checks were also marked
confirmed. It is not an ongoing monitoring service.

To revert on downstream router, first review that checkpoint against any later edits,
then run its rollback.sh through root SSH. It restores network/dhcp and
reloads services, potentially interrupting Internet access briefly. It does
not restore the EX511 router role or change the saved firmware slot.

The supported explicit PPP wan6 and downstream RA/SLAAC configuration is
described in the [OpenWrt IPv6 documentation](https://openwrt.org/docs/guide-user/network/ipv6/configuration).
