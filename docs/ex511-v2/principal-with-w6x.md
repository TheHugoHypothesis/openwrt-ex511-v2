# Two-router deployment: EX511 gateway and downstream routed Wi-Fi

This anonymized case study preserves the technical design and outcome. It is
not a configuration file or an installer for another household. Addresses,
subscriber credentials, device identifiers and local artifact paths are omitted.

## Final topology

```text
ISP bridge -> EX511 WAN (PPPoE + DHCPv6 prefix delegation)
                 EX511 LAN / Wi-Fi
                    `-> downstream router WAN (DHCP)
                           separate downstream IPv4 LAN
                           IPv6 RA + DHCPv6 + NDP relay
```

The downstream device retained its Wi-Fi, separate LAN/VLANs, DHCPv4,
custom DNS/adblock and isolation policies. IPv4 NAT runs on both routers.
Only its primary client network entered the IPv6 relay domain; its legacy
separate LAN did not receive the same delegated /64 as a routed prefix.
IPv6 relay is not a complete client-isolation boundary and may advertise
upstream DNS directly, so local DNS filtering must be reviewed separately.

## Transition design

EX511 originally operated as a bridged AP. During preparation, one unused
LAN port was separated from br-lan and became a temporary DHCP uplink to the
old gateway. Only the remaining LAN bridge served the new DHCP/RA settings,
preventing two DHCP servers from sharing the old client broadcast domain.
The temporary interface had a high route metric and a separate NAT/firewall
zone with scoped SSH/DHCP exceptions; unrelated inbound traffic was rejected.

PPPoE credentials, MTU/MRU and the existing ISP DHCPv6 identity were copied
privately to EX511; no guessed VLAN or unrelated credential was introduced.
The old gateway initially remained active to keep Internet during preparation.

The computer could not remain wired to EX511 for the final change. A local
Wi-Fi SSH path to the downstream router was therefore verified first. A
scoped temporary SSH exception allowed only that workstation. The operator
then moved ISP -> EX511 WAN and EX511 LAN -> downstream WAN. A detached
on-router script changed the downstream WAN to DHCP and activated IPv6 relay.
It retried gateway/Internet HTTPS checks before confirming the change; an
independent 300-second guard would restore the prior configuration otherwise.
No continuous Internet connection or UART input was needed by that script.

The scoped access exception was represented in the prepared configuration
and rollback checkpoint, keeping local recovery reachable during either
outcome. Before applying, the helper refused unexpected board identity,
pending UCI edits or config files changed since preparation. Its confirmation
checked actual EX511 gateway selection and Internet IPv4 HTTPS, not just link
carrier. IPv6 was validated separately after the successful transition.

The downstream client identity/MAC was no longer the old EX511 WAN clone,
avoiding accidental duplicate ISP identity after the role change. EX511
kept its own factory-derived WAN identity. Neither router's Wi-Fi passwords
were replaced by the migration. No flash, reboot or boot-policy change was
part of this network-role transition.

## Results and cleanup

The operator reported working Internet. Inspection confirmed EX511 PPPoE,
native IPv6 /64 and downstream DHCP WAN via EX511. Both routers passed IPv4
and IPv6 Internet ping, and a client behind the downstream router passed
HTTPS forced to IPv4 and separately IPv6. The temporary EX511 LAN uplink was
then removed; all four LAN ports returned to br-lan. Temporary management
rules and loose migration scripts were removed after private verified backups.

The operator-specific scripts and configuration exports are intentionally
not published. Their control flow is documented above so another developer
can implement a migration appropriate to their own topology rather than
execute hard-coded network settings. Full firewall/relay isolation, prefix
renewal endurance and prolonged multi-client stress remain separate tests.
