# Owner AP configuration behind downstream router — 22 October 2026

> **Anonymized deployment case study.** Addresses and local checkpoint paths
> are placeholders, not usable configuration. Operator-specific automation
> is not published; this report preserves topology, observations and limits.

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

The owner chose to keep downstream router as the production PPPoE router and use EX511 as
a wired bridged access point. These are saved runtime UCI settings in the
slot1 UBIFS overlay, not new board defaults or a rebuilt firmware image.
The firmware, factory provisioning, NSS setup and durable boot policy were
not changed by this configuration task.

## Topology and settings

```text
ISP bridge -> downstream router PPPoE/router -> downstream router LAN -> EX511 LAN2
                                             |-- Wi-Fi 2.4 GHz
                                             |-- Wi-Fi 5 GHz
                                             `-- EX511 LAN1/3/4 clients
```

- EX511 retains `br-lan` with lan1–lan4 and both APs. WAN is not a bridge
  member and its old wan/wan6 interfaces have protocol `none`, auto-start off.
- `network.lan` is a DHCP client, hostname `ex511-ap`. downstream router assigned
  **$AP_LEASE_HOST/24**, gateway/DNS **$SECOND_ROUTER_HOST**, lease 43200 seconds.
  This is a DHCP lease, not a static address or a downstream router reservation.
- downstream router DNS resolved **ex511-ap.lan** to the current lease. Normal management
  is `http://$AP_LEASE_HOST/`; clients using downstream router DNS can also use the hostname.
- A separate `ex511_mgmt` static interface retains **$OPENWRT_HOST/24** on
  br-lan, with no default route or delegation. This is for direct maintenance
  with a PC configured as $PC_SOURCE/24; do not assume that address is
  reachable from an ordinary downstream router DHCP client.
- The EX511 LAN DHCP server is ignored/disabled. RA, DHCPv6 server and NDP
  relay are disabled; odhcpd is stopped and disabled. UDP server ports 67
  and 547 were checked absent before connecting the upstream cable.
- dnsmasq remains enabled for the EX511's own local DNS cache, forwarding
  through the downstream router DNS learned by DHCP. It does not provide DHCP leases.
  Clients receive gateway/DNS configuration from downstream router.
- `lan6` is a DHCPv6 client on `@lan`, with `reqaddress=try`, `reqprefix=no`
  and delegation off. Client IPv6 frames cross the LAN/Wi-Fi bridge;
  the AP does not need a relay service to extend this shared network.
- Firewall remains enabled; lan, lan6 and ex511_mgmt belong to the trusted
  LAN zone. There is no active routed WAN on EX511. The maintenance address
  is not a security boundary against other devices on this same LAN.
- Wireless configuration SHA256 was unchanged. Both original test SSIDs,
  credentials, channels and radio settings were retained.

The initial AP setup did not modify downstream router. A subsequent
[native IPv6 activation](w6x-native-ipv6.md) changed its IPv6 settings. The
PC's diagnostic static Ethernet addresses and production IPv4 default
through its existing downstream router Wi-Fi were left unchanged.

## Observed results

1. Saved network/dhcp/firewall backups both externally and in a private
   `/root/ex511-router-backup-<timestamp>/` checkpoint on EX511. No firmware,
   bootloader or environment write was needed. The full environment readback
   remained byte-identical to the preceding cold-boot verification.
2. Applied settings and verified direct maintenance SSH, both APs and absence
   of DHCP server sockets before permitting the upstream connection. The
   guarded rollback was confirmed before connection so it could not later
   restore a competing DHCP server onto the downstream router LAN.
3. The owner reported a possible accidental Reset press while cabling. A
   reboot was observed, but network/dhcp/firewall files and wireless hash
   remained identical to the saved AP settings; this was not a factory reset.
   The upstream cable was temporarily removed until checks completed.
4. After reconnection LAN2 linked and EX511 obtained its lease from downstream router.
5. From EX511: downstream router gateway ping 3/3, Internet IPv4 ping 3/3, DNS resolution
   and an HTTPS fetch from openwrt.org passed.
6. From the PC's downstream router Wi-Fi: pinned-key SSH reached EX511's DHCP address and
   HTTP administration returned 200. This was not tested only through the
   direct maintenance cable.
7. The owner reconnected the phone to EX511's 5 GHz AP, was asked to disable
   cellular data, and confirmed that openwrt.org opened over that Wi-Fi.
   An authorized associated 5 GHz station was also recorded. The phone's
   exact DHCP address was not independently captured.
8. Both APs remained enabled and the OOM counter was zero at the final check.
   No new long-duration throughput or multi-client stress test is claimed.

Initially Internet IPv6 was unavailable: downstream router still used the temporary IPv4-only
migration profile. The subsequent [IPv6 activation](w6x-native-ipv6.md)
obtained a native ISP /64 delegation, distributed it on the shared LAN,
and gave EX511 a global IPv6 address and default route. EX511 Internet IPv6
ping passed 3/3; PC HTTPS forced to IPv6 returned HTTP 200 through downstream router Wi-Fi.
A phone IPv6-specific test through EX511 Wi-Fi remains unperformed.

The first RAM watchdog launch used `nohup`, absent from this image. It did
not run; direct maintenance SSH still worked. A replacement shell watcher
with ignored HUP was started, its live process verified, and confirmed after
local AP checks. No automatic rollback was allowed to remain armed when the
routers were connected. The saved persistent checkpoint also permits manual
restoration. Raw settings, identifiers and logs remain in private storage.

## Manual return to the preceding router configuration

First disconnect EX511 LAN2 from downstream router, retaining direct PC–EX511 cabling.
Restoring the old router settings re-enables EX511 DHCP and must not be done
while it shares the production LAN. Choose and review the appropriate
checkpoint; restoring it replaces later network/dhcp/firewall edits.

On EX511 root SSH, substituting the actual saved checkpoint directory:

```sh
set -e
backup=/root/ex511-router-backup-YYYYMMDD-HHMMSS
test -r "$backup/network" && test -r "$backup/dhcp" && test -r "$backup/firewall"
cp "$backup/network" /etc/config/network
cp "$backup/dhcp" /etc/config/dhcp
cp "$backup/firewall" /etc/config/firewall
/etc/init.d/odhcpd enable
/etc/init.d/odhcpd restart
/etc/init.d/dnsmasq restart
/etc/init.d/network reload
/etc/init.d/firewall reload
```

That restores the previous router-mode UCI settings; it does not change
firmware slots, boot policy or wireless credentials. Firmware recovery and
stock selection are different procedures described elsewhere in this folder.
