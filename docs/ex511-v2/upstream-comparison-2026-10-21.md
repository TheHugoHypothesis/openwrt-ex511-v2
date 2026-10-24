# EX511 source and release comparison — 21 October 2026

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

## Snapshots and scope

| Source | Inspected revision | Meaning |
| --- | --- | --- |
| Original fl1ck3r port | `9b36524beffd8ecf00215d3a2082266dfe3cb9d4` | Locally recorded `tplink-ex511-v2`; Linux 6.12, incomplete NSS-DP Ethernet path |
| gusfm default `ex511` | `5a26a4cca70435f2048699fbdd65f0d8b71fedec` | September 20 tip; Linux 6.18.44 |
| gusfm `ex511-nss` | `a84bb78f3e8bcb2e042e478faa39246678cf59e0` | September 15 memory/board contribution |
| Our original NSS baseline | `a915ef7f2d3f1500f455ed9e4721c0490349fe66` | October 20 fixes over OpenWrt main from October 18 |
| Our tested development tree | `62b66f17280c530502b4012da35ad84ad0c45d84` | Factory-data handling, protected trial and owner hardware results |
| kuncy7 latest release | `9caa35b4d718382ad882cb35c2372dbb569de901` | `ipq50xx-2026.10.21`; OpenWrt main from October 21 |

The gusfm default branch is `ex511`, despite its repository description naming
`ex511-nss`. Also inspected the tips of `ex511-generic` (`ad3fb423c20`),
`ex511-nctl` (`2bc82a7b099`) and `rtl8367d-nss-wip` (`c9519890fa7`).
Those alternatives are not later October updates. Raw commit-count distances
are misleading across the intervening rebases and cherry-picks.

This comparison fetched source refs and inspected a downloaded release image
offline. It did not update, reboot, configure or flash a router, or replace our
working branch. The release image was not booted or rebuilt locally.

## What is already inherited from gusfm

The EX511 board/NSS contribution, 8 MiB NSS reservation, `coherent_pool=512K`,
both radios' firmware memory mode 2, IPQ5018 MP_256 pbuf values and LOW/256M
profile defaults already exist in our original NSS baseline. They are not
new fixes to import from the September fork.

The pbuf payload settings are still `extra_pbuf_core0=800000`,
`n2h_high_water_core0=16336`, `n2h_wifi_pool_buf=0` on IPQ5018. The pbuf init
script is byte-identical between our tree and the October 21 release.
Compared with gusfm, later upstream changes mainly allow longer host queues
on larger-memory boards; the 256 MB default remains 256 packets.

The older `0828` GFP_KERNEL patch addresses the then-current MPD firmware
loader. Our prepared kernel uses the newer remoteproc arrangement and no
longer contains that `mdt_load_split_segment_dma()` implementation. Copying
that patch just because its old filename is absent would be incorrect.

## Ethernet and switch differences

gusfm retains the earlier family-D Realtek implementation and headerless
CPU-port/VLAN patches `946`–`950`. It contains useful contributor measurements
of VLAN access ports, trunk VLANs and NSS traffic, but these are measurements
of that implementation and another unit.

Our base and the latest release instead use the later family-D SDS13 PCS
series `777-01`–`777-09`, delayed SerDes initialization and the Realtek
802.1Q DSA tagger (`762`). Our owner hardware actually probes as RTL8367S-VB
and has passed all four LAN jack checks and an isolated accelerated WAN/NAT
test. See [hardware-results.md](hardware-results.md).

gusfm's `6491538b110` removes a questionable NCTL enable write at register
`0x612f`: the older driver enabled a microprogram controller without loading
its program. Our different driver series has no corresponding NCTL enable
write. That commit is useful hardware history, not an immediately applicable
fix for our working Ethernet stack. Do not replace the current PCS/tagger
with the older headerless implementation.

## Memory: the most useful configuration difference

All current variants have the ordinary `ATH11K_MEM_PROFILE_256M` and
`NSS_MEM_PROFILE_LOW` choices. There is also a separate, optional
`ATH11K_NSS_MEM_PROFILE_256M` implemented by patches `999-991`–`999-995`:

| Item | gusfm September branch | Our tested candidate | October 21 release |
| --- | --- | --- | --- |
| Kernel | 6.18.44 | 6.18.55 | 6.18.55 |
| NSS firmware | README recommends 12.2-156 | 12.5-210 | 12.5-210 |
| Ordinary LOW/256M tuning | Present | Selected | Selected |
| Extra NSS host-TX/CE5/fragment tuning | Absent | Explicitly selected | Code present; option defaults off and is not selected |
| Test root filesystem | Contributor reports flashed installation | Unpacked initramfs in RAM | SquashFS sysupgrade image |
| LuCI in inspected image | Not established | Present in owner trial | Absent |

The release's published `config-256m.buildinfo` does not select the extra
NSS profile, whose Kconfig default is `n`. Its actual ath11k module also lacks
the profile's `NSS 256 MiB: active` diagnostic string. The source for the
optional profile itself is identical to ours. This is a build-selection
difference, not missing driver code in the release.

gusfm reports roughly 20 MB available after load in a flashed build. Our
initramfs holds about 34 MiB of shmem for its unpacked filesystem and includes
different userspace. These are not comparable memory experiments. Our extra
profile passed the bounded owner traffic tests without an OOM kill, but
MemAvailable still reached zero; it is not a demonstrated complete OOM fix.

Useful remaining diagnostics from gusfm's work are `drv_nss_skb_count` in
`/sys/kernel/debug/qca-nss-drv/stats/drv`, pbuf occupancy, DMA pools and
allocation tracing. Slab and MemFree alone cannot attribute every NSS packet
buffer. `CONFIG_PAGE_OWNER` would require a separate diagnostic kernel and
additional memory; do not enable it indiscriminately on this 256 MB unit.
Do not lower `vm.min_free_kbytes` merely to make MemAvailable look larger.

## What our factory-data work adds

Both the gusfm fork and the latest kuncy7 EX511 DTS still read the MAC from
raw offset `0x113830` inside a UBI/UBIFS partition. Their own comments warn
that this relies on a particular PEB/node layout. Our helper instead reads
the six-byte `0x0434F100` record by filename from read-only UBIFS, validates it
and provisions Ethernet/radio MACs before use.

The baseline's external radio uses packaged reference board data and a dummy
external calibration path. Our owner's candidate supplies the private
country/FEM-matched board data and validates/prepares the actual external
calibration record `0x043A0000` in RAM. These owner observations do not prove
RF calibration quality or compatibility with every EX511 regional variant.

Our protected initramfs profile, all-17-partitions read-only policy, one-shot
stock-return workflow, integrity checks and owner test evidence are additional
local work. Replacing the tree or flashing a release image would not preserve
these additions automatically.

The latest release does **not** fix the EX511 permanent-install slot issue:
its EX511 sysupgrade helper still targets physical slot 0. The change to
`platform.sh` since our baseline concerns other boards. The release's general
sysupgrade instructions are not authorization or validation for preserving
our owner's stock slot, nor an EX511 stock-SSH installer.

## What is actually newer in the release

The inspected EX511 image identifies itself as OpenWrt **SNAPSHOT
r37918-9caa35b4d7**, still Linux 6.18.55. Its tag is a project build release,
not an official stable OpenWrt release. It uses the **same NSS feed revision**
as our pinned build: `5344fc35d79fc947b501e9feee5ced2b07c664fa`.
The packages and LuCI feeds have newer pins; routing/telephony/video are the
same revisions in the published feed manifest.

The release notes compare against October 19. The five advertised locking
fixes should not be counted as five missing fixes in our tree: our October 20
base already contains the mac80211 queue/RCU and bridge RCU fixes, and the
NSS feed revision is identical.

New work worth reviewing is the October 21 OpenWrt merge, including hostapd
patches/ucode changes, plus `9caa35b4d718`, which corrects NSS ath11k RX hook
placement after IPQ9574 support was merged. That repair belongs with the new
base; it does not establish an IPQ5018 fix for the owner's first-connection
failure. Hostapd's source revision string is unchanged, but its downstream
patches and ucode differ. A version-string-only comparison would miss this.

No EX511-specific memory fix, factory-data improvement or A/B upgrade repair
was found between our original NSS base and the release. The maintainer
explicitly lists the 256 MB group among devices not tested by them.

## Recommended engineering sequence

1. Preserve the tested source, private factory provisioning and explicit extra
   memory-profile selection. Retain the original slot and diagnostic guardrails.
2. Prepare a separate candidate incorporating the October 21 base and its
   matching ath11k adjustments, rather than reverting to the September fork.
   Re-pin feeds and rerun factory/DTB/package checks after integration.
3. First compare like-for-like protected initramfs builds with identical
   packages, board data, calibration and memory profile. Repeat initial Wi-Fi
   association, both load tests, all ports and routed NSS counters.
4. Attribute residual memory use before changing pool counts or watermarks.
   Test idle recovery, more clients and sustained mixed traffic.
5. Review permanent root/slot selection separately before trying to obtain
   SquashFS memory measurements on the owner's device. A promising release
   does not remove this installation prerequisite.

## Evidence and reproducibility

Release image inspected offline:
`openwrt-qualcommax-ipq50xx-tplink_ex511-v2-squashfs-sysupgrade.bin`,
14,653,713 bytes, SHA256
`52a81f2c59b1ac1a889725d88e6e9474e86855289bd514c8244255575e4532fd`.
The hash matched the release API digest. The tar contains a kernel and
SquashFS root; neither was executed. Downloaded metadata, file listings and
selected extracted files remain under `/var/tmp/ex511-comparison-20261021`.

Fetched comparison refs are under `refs/remotes/compare-gusfm/`,
`refs/remotes/compare-kuncy/` and tag `compare-ipq50xx-2026.10.21`.
Useful commands in this checkout:

```sh
git diff a915ef7f2d3f compare-ipq50xx-2026.10.21 -- package/kernel/mac80211
git diff compare-gusfm/ex511 62b66f17280 -- target/linux/qualcommax/dts/ipq5018-tplink-ex511-v2.dts
git show compare-gusfm/ex511:README.ipq50xx.md
git show compare-ipq50xx-2026.10.21:package/kernel/mac80211/patches/nss-extra/ath11k/999-991-ath11k-nss-256m-host-tx-allocations.patch
```

Primary sources: [gusfm snapshot](https://github.com/gusfm/openwrt-nss-edma/tree/5a26a4cca70435f2048699fbdd65f0d8b71fedec),
[NCTL change](https://github.com/gusfm/openwrt-nss-edma/commit/6491538b11061747d647c8e556114fce33992b53),
[October 21 release](https://github.com/kuncy7/openwrt-nss-edma/releases/tag/ipq50xx-2026.10.21),
[RX-hook repair](https://github.com/kuncy7/openwrt-nss-edma/commit/9caa35b4d718382ad882cb35c2372dbb569de901).
