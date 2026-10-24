# TP-Link EX511 V2 — OpenWrt with NSS

[Português](README.pt-BR.md) · [Documentation](docs/ex511-v2/README.md) ·
[Install through stock root SSH](docs/ex511-v2/installation-ssh.md) ·
[Test results](docs/ex511-v2/results.md) · [Recovery](docs/ex511-v2/recovery.md)

An unofficial EX511 V2 development port and a documented **installation
through an already available stock root SSH shell, without UART input**.
One owner device has been installed, upgraded, cold-started and used as a
PPPoE/IPv6 gateway with both Wi-Fi bands. This is not an official OpenWrt
stable release or a universal installer for every EX511 firmware revision.

## What is working on the tested device

| Area | Evidence |
| --- | --- |
| Persistent installation | SquashFS + UBIFS in physical `rootfs_1`; stock `rootfs` preserved |
| Boot selection | OpenWrt saved as default; SSH selection of stock/OpenWrt tested |
| Ethernet | Four LAN jacks tested earlier; routed WAN and current downstream traffic pass |
| Wi-Fi | Both bands pass traffic; approximately 14-minute single-client 5 GHz integrity test |
| NSS | Wired/Wi-Fi acceleration observed; active IPv4/IPv6 ECM connections on the current gateway |
| PPPoE / IPv6 | Actual ISP PPPoE, native DHCPv6-PD /64 and downstream downstream router IPv6 relay pass |
| Factory data | Read-only UBIFS file lookup for MAC/calibration, avoiding physical UBIFS offsets |
| Recovery | Button-triggered failsafe SSH and bootloader recovery HTTP entry tested; recovery upload **not tested** |

Installed firmware: **Linux 6.18.55**, OpenWrt **SNAPSHOT
r0+37938-ff5b0529bb8**. The firmware build commit is
[`ff5b0529bb8`](docs/ex511-v2/source-provenance.md).
Later documentation/workstation-tool commits are not a new hardware-tested
firmware binary. See the [evidence matrix](docs/ex511-v2/results.md) for which
results belong to which image; the long Wi-Fi test used an earlier image.

## Start here

1. Read [hardware and UART findings](docs/ex511-v2/hardware.md), then
   [recovery limits](docs/ex511-v2/recovery.md).
2. Check the strict stock-layout/root-access prerequisites in the
   [SSH installation guide](docs/ex511-v2/installation-ssh.md).
3. [Build and validate your own images](docs/ex511-v2/build-current.md).
4. Follow the staged installation. Do not substitute AX55 images, MTD numbers
   or a generic upstream EX511 sysupgrade for the dedicated slot1 profiles.

**Root access is a prerequisite, not provided by this project.** An admin
login is not proof of UID 0. No stock web-interface exploit, shared password,
universal root unlock, signed stock installer or ready-to-flash binary is
published here. Private regional/FEM board data must be obtained and checked
for the reader's own device. Firmware/BDF redistribution rights are unresolved.

**Without UART input does not mean without risk.** RX input did not work on
the tested EX511. An interrupted RX trace is a hypothesis, not a physically
confirmed EX511 defect. The AX55 wiki describes such a gap on that model;
it is not an EX511 soldering guide. The installation retained receive-only
UART logs, so a completely unopened, unmonitored installation was not separately
validated. There is no automatic rollback for an arbitrary kernel hang.

## Current tested deployment

```text
ISP bridge -> EX511 WAN: PPPoE + native IPv6 /64
                 EX511 LAN / Wi-Fi: $GATEWAY_NETWORK/24
                    `-> downstream router WAN: DHCP
                         downstream router main clients: $DOWNSTREAM_NETWORK/24
                         IPv6: RA + DHCPv6 + NDP relay
```

The operator-specific [deployment report](docs/ex511-v2/post-cutover-cleanup.md)
is evidence, not a configuration everyone should import. Requests for /56
and /60 still returned /64 with the same DHCPv6 identity. See
[network operation and tuning](docs/ex511-v2/network-operation.md).

## Credits and scope of this fork

This work builds on [fl1ck3r's original EX511 port](https://github.com/fl1ck3r/openwrt/tree/tplink-ex511-v2),
[gusfm's EX511 work](https://github.com/gusfm/openwrt-nss-edma),
[kuncy7's IPQ5018 NSS integration](https://github.com/kuncy7/openwrt-nss-edma),
Julius Bairaktaris's NSS work, George Moussalem's upstream IPQ5018/ath11k
work, and the wider OpenWrt/Linux communities. Ethernet and NSS were not
invented in this fork. Our additions include factory-data validation,
protected slot1 image profiles, reviewed SSH boot-policy control and the
owner's installation/recovery/traffic validation.

See [attribution and provenance](docs/ex511-v2/credits.md). The inherited NSS
README is preserved as [README.nss-upstream.md](README.nss-upstream.md), and
[README.ipq50xx.md](README.ipq50xx.md) remains the upstream technical reference.
Its board-specific claims do not replace this fork's test reports.

The default branch is `ex511-v2`. EX511 changes are maintained as incremental commits on the upstream NSS
base; private session branches are not part of the maintained contribution.
The source tree retains its existing component licenses; this is not a
relicensing of OpenWrt or Qualcomm/TP-Link firmware.
