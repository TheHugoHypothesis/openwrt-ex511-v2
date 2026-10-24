# Persistent-image 5 GHz phone load test — 2026-10-22

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

The EX511 v2 ran the physical slot1 SquashFS/UBIFS image, OpenWrt
r37932-a72260511bb, Linux 6.18.55, with the extra 256 MiB ath11k NSS
memory profile. The phone used the 5 GHz AP on channel 36, 80 MHz;
the PC test server was connected through LAN1. This measures local
Wi-Fi/LAN transfers, not Internet, PPPoE or routed NAT throughput.

The owner interrupted the browser test before its planned 15-minute end.
The server nevertheless received 1,118 completed transfer-cycle reports over
830.9 seconds (13 minutes 50.9 seconds between first and last reports).
Each cycle downloaded 16 MiB and uploaded 8 MiB with payload validation.
All 1,118 cycles passed both integrity checks: 17,888 MiB downloaded and
8,944 MiB uploaded. Mean per-cycle rates were 481.0 Mbit/s download and
167.4 Mbit/s upload; individual rates ranged from 268.9–692.6 and
63.8–337.2 Mbit/s respectively. These are arithmetic means of browser
transfer rates, not whole-session throughput including pauses/validation.
There was no final browser completion summary; an interrupted final
unreported request is not included in these totals.

The bounded periodic monitor expired during the test. Its samples overlap
412.7 seconds of actual traffic, so continuous memory coverage for the
whole session cannot be claimed. The 81 samples surrounding/overlapping
that window showed MemAvailable 16,216–23,376 KiB, Shmem 360 KiB,
zero OOM kills and no SSH monitoring failures. The post-test snapshot
showed MemAvailable 18,356 KiB, Shmem 360 KiB and oom_kill 0.
Retained kernel/system logs showed no firmware-crash, panic or OOM marker.

The phone remained associated at the final check, with a reported connected
time of 1,016 seconds and signal -48 dBm. Hostapd recorded a successful
RSN handshake; retained logs contained no subsequent disconnect event.
Station counters showed four TX failures, zero miscellaneous RX drops;
this is not a claim of zero wireless packet loss. No boot, flash, network
configuration or boot-default change was performed for this test.

This supports sustained single-client 5 GHz operation on the NAND-root
image and shows better memory headroom than the earlier initramfs trial.
It does not establish multi-client/dual-band stability, repeated initial
association reliability, long-duration stability or safe actual sysupgrade.
Raw client identifiers and logs remain in private local evidence storage.
