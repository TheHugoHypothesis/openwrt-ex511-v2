# Operation, IPv6 and performance

This is an observed deployment example, not a network config bundled into
firmware defaults. Set your own passwords, SSIDs, country/FEM data, LAN
addresses and ISP credentials. Never publish an exported config unredacted.

## Current roles

EX511 terminates untagged ISP PPPoE on WAN, at the validated MTU/MRU 1480.
The IPv6 client is explicit wan6 on @wan, reqaddress=try, reqprefix=auto;
wan.ipv6=1 enables IPv6CP. The delegated /64 is assigned to EX511 LAN,
ip6assign=64, RA/DHCPv6 server with SLAAC enabled and NDP relay off.

downstream router is a separate IPv4 NAT router, DHCP WAN from EX511. Its main client
network uses odhcpd RA/DHCPv6/NDP relay with wan6 as master, reqprefix=no.
It does not pretend to route independent /64s from a single /64 delegation.
This is IPv4 double NAT and IPv6 relay, not an Ethernet bridge and not a
complete IPv6 isolation boundary. The workstation's IPv4/IPv6 HTTPS passed.

Temporary LAN2 management routing, SSH exception and deployment scripts were
removed/archived after cutover. All EX511 LAN1–4 are again on the LAN bridge.
The operator's migration scripts are historical tools, not a general gateway
setup wizard. See [cleanup](post-cutover-cleanup.md).

## Prefix-size investigation

| DHCPv6-PD request | Received |
| --- | --- |
| auto | /64 |
| explicit /56 | /64 |
| explicit /60 | /64 |

For each explicit test the running odhcp6c argument confirmed the requested
length before the fresh prefix status was recorded. The client identity was
retained. Request length is a hint, not an entitlement to a routed prefix.
No forceprefix, fake static /56, arbitrary DUID rotation or deliberate PPPoE
redial was used. `auto` was restored and IPv6 Internet ping rechecked.
These results do not distinguish subscriber provisioning from retained server
lease policy. A provider may need to change the subscriber's PD profile;
we have no evidence that a local router option can force that change.

## NSS and IRQ placement

The actual EX511 has nss-irq-affinity, with nss_queue0 on CPU0 and queue1 /
both radios' copy engines on CPU1. This is deliberate per-baseline placement.
Firmware RPS and ordinary Linux packet steering are different mechanisms;
packet_steering=0 does not mean NSS queue fan-out is disabled.

Do not add irqbalance or generic rc.local IRQ pinning without a measured
reason; it could replace this placement. Ordinary kernel software/hardware
flow offloading stays off with this vendor NSS/ECM path: the baseline documents
that nft flowtables can bypass the hooks ECM uses to accelerate flows.
Read the inherited [IRQ helper](../../package/nss/nss-tools/files/nss-irq-affinity)
and [NSS integration](../../README.ipq50xx.md).

At a 24 October snapshot the NSS data plane was up, accelerated IPv4/IPv6
connections existed and oom_kill was zero. Available memory was roughly
17–21 MiB across samples, with thermal readings around 58–60 C. These are
snapshots, not temperature limits or evidence of full-load capacity.

Measure wired throughput, CPU/softirq and NSS counters first. Measure latency
while saturating upload/download before considering QoS compatible with NSS.
Avoid adding memory-heavy router services without budget/testing. Keep 2.4-GHz
width at 20 MHz and evaluate 5-GHz width/channel using local conditions rather
than assuming 160 MHz or more transmit power improves service.

Read-only diagnostics on this image include:

```sh
cat /sys/kernel/debug/qca-dwmac-nss/status
cat /sys/kernel/debug/ecm/ecm_nss_ipv4/tcp_accelerated_count
cat /sys/kernel/debug/ecm/ecm_nss_ipv6/tcp_accelerated_count
cat /proc/interrupts
cat /proc/softirqs
grep -E 'MemAvailable|Shmem' /proc/meminfo
grep oom_kill /proc/vmstat
ubus call network.interface.wan status
ubus call network.interface.wan6 status
```

Redact public addresses, DUIDs, MACs and identifiers before posting logs.
Counter activity is not a substitute for a controlled performance test.
