# EX511 V2 NSS baseline and factory data

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

This branch starts at kuncy7/openwrt-nss-edma `c3po-tag-8021q`, commit
`a915ef7f2d3f1500f455ed9e4721c0490349fe66` (20 October 2026).
The previous fl1ck3r-based work is preserved separately; this is a deliberate
move to the existing EX511 hardware-tested implementation, not a new port.
The original EX511 contribution is PR 3, commit
`fee402cdf729cce626938dafab277472e4d12465`.

## What is retained

The 6.18 target, upstream DWMAC/UNIPHY integration, Realtek family 0x6642
(RTL8367S-VB/RTL8367D), 1 Gbit/s SGMII CPU connection, reset sequence,
partition geometry, boot integration and both radios' firmware memory mode 2
are unchanged. NSS Ethernet and ath11k offload, NSS firmware 12.5 and LOW/256M
memory profiles follow the baseline CI configuration. Feeds are pinned in
`feeds.conf.default`; `configs/ex511-v2-nss.config` selects only this board.

Correction after tracing the compiled driver and startup code: this
baseline already includes the C-3PO DSA/802.1Q path for Realtek switches.
When `rtl8365mb-mdio` is bound, first-boot defaults select `topology=dsa`
before reaching the older EX511 flat-AP table. The service switches to
`rtl8365mb-8021q`, retaining separate WAN/LAN ports while NSS uses VLAN
interfaces. The tagger is built into our validated kernel.

The DTS still contains the legacy `realtek,headerless-cpu-port` property,
but the compiled current driver has no consumer for it. Its presence does
not establish flat-AP operation. Older EX511 notes in `README.ipq50xx.md`
and our initial report described the legacy fallback and were misleading
when applied to the current default path. A mock Realtek-bound EX511 test
now confirms that the DSA defaults preserve WAN/LAN configuration.

This establishes code/configuration coverage, not working separation on the
owner's hardware. The remaining tests must confirm driver binding, runtime
tagger switching, VLAN isolation, PPPoE and NSS counters. Firmware 12.5 also
still needs validation on this 256 MB unit. Existing installations with a
saved legacy topology require separate migration review.

## Factory-data changes

The baseline's raw NAND offset `0x113830` inside `misc_data_ro` is removed.
This partition holds UBI/UBIFS and physical file locations can move.
Read-only stock inspection on the owner's EX511 established these records:

| UBIFS filename in `misc_ro` | Content | Use |
| --- | --- | --- |
| `0x0434F100` | Six raw MAC octets | LAN/conduit and 2.4 GHz base; WAN +1, 5 GHz +2 |
| `0x0434F700` | 256-byte country/FEM record | Check locally selected external-radio BDF |
| `0x043A0000` | 128 KiB external-radio EEPROM | Validate then copy into RAM for ath11k |

These are filenames, not flash offsets. The helper refuses writable MTD or
writable UBI, attaches without formatting, mounts read-only, serializes
readers with flock and only detaches its own attachment. MAC parsing rejects
missing, malformed, multicast, all-zero and known placeholder values.

Preinit sets GMAC1's conduit MAC before NSS starts, with an OF-node identity
check. Board defaults also assign Ethernet and per-radio address bases. A
small wifi-detect extension passes the optional validated `macaddr_base`
from board metadata into newly generated radio configuration; existing user
radio configuration is preserved. This uses netifd's existing MAC allocator.

External-radio calibration must match the BDF's country/FEM marker, exact
length, EEPROM header and full XOR checksum. Only a RAM copy's MAC and checksum
are changed. The integrated radio retains the baseline's dummy-calibration
fallback: its factory record has not been validated. No partition is written.

## Private provisioning

No per-unit MAC, EEPROM, credentials or newly extracted stock BDF is committed.
The local importer `scripts/ex511-v2/import-stock-bdf.py` creates a private
`files/` overlay with a scoped QCN6122 board-2.bin and country/FEM marker.
Run its `--help` for the required stock directory, country, FEM and output.
The external radio fails calibration provisioning when this marker is absent
or mismatched, rather than silently substituting blank owner calibration.
A different unit's factory contents and BDF must be checked independently.

## Initial build recipe

Use a Linux build directory without spaces, with normal OpenWrt host
prerequisites installed. Keep all generated files and private overlays out
of public Git:

```sh
./scripts/feeds update -a
./scripts/feeds install -a
cp configs/ex511-v2-nss.config .config
make defconfig
# If locally provisioned, copy the private overlay into ./files here.
make download -j8
make -j6 V=s
```

Both initramfs and sysupgrade are requested. Generated images are for future
controlled testing only. Do not assume a sysupgrade file can be flashed from
stock, or that a successful compile establishes hardware operation.

## Validation and next steps

Local factory-MAC, EEPROM/BDF and provisioning tests pass. The complete NSS
build succeeds, both image formats were inspected and the packaged utility
was exercised under QEMU. See [validation.md](validation.md) for exact evidence
and image hashes. No image
from this branch has been booted on the owner's hardware. First testing
should use verified UART voltage/pinout and recovery access, a RAM-booted
initramfs, factory partition checks, MAC verification, port mapping, cold/warm
boots, dual-radio load and NSS counters. Do not rely on untested WAN isolation as an Internet boundary. The existing stock NAND backup and bootloader must
remain available; flashing requires a separately reviewed installation plan.

## Comparison with the previous branch

| Area | Previous fl1ck3r-derived work | This NSS baseline |
| --- | --- | --- |
| Kernel | 6.12.87 with Ethernet/radio backports | 6.18.55 and the baseline's existing patch series |
| CPU/switch link | Untested 2.5G assumption | Contributor-tested SGMII 1G retained |
| Switch | Earlier RTL8367S assumptions | Existing family-D/SDS13 support retained |
| Fast path | Mainline-style host DWMAC path | Downstream qca-dwmac-nss + NSS driver/ECM and ath11k NSS |
| Network roles | Proposed DSA LAN/WAN split | C-3PO DSA/802.1Q present; EX511 runtime unverified |
| Factory MAC | Read-only UBIFS lookup | Same reader; apply conduit before NSS and per-radio netifd bases |
| External calibration | Validated stock factory record + local BDF | Same data validation, integrated with the NSS firmware hook |
| Integrated calibration | Earlier experimental fallback | Preserve this baseline's demonstrated zero-cal fallback |

The inherited Ethernet path includes
`target/linux/qualcommax/patches-6.18/0954-net-stmmac-Introduce-Qualcomm-IPQ5018-DWMAC-driver.patch`,
the QCA UNIPHY PCS, Realtek family-D patches in
`target/linux/generic/pending-6.18/777-*`, the `qca-dwmac-nss` package and the
pinned NSS feed. The George Moussalem MultiPD/ath11k series and subsequent
recovery/regulatory/memory fixes are already in this baseline. None of the
older branch's kernel patches are layered on top. NSS is downstream support;
its presence does not imply that upstream Linux provides or validates NSS
acceleration on this board.

See [build.md](build.md) for exact commands and [hardware-test-plan.md](hardware-test-plan.md)
for the remaining physical checks. The owner has not yet booted either branch.
