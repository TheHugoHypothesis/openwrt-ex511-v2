# Owner hardware tests — October 2026

> **Historical engineering record.** Statements below describe the recorded
> stage, which may predate successful installation or later tests. For the
> current procedure and evidence, use the [documentation index](README.md),
> [installation guide](installation-ssh.md) and [results matrix](results.md).

These observations concern this owner's EX511 V2 and its locally provisioned
factory data. They do not establish production readiness or compatibility with
every EX511 revision. Raw logs, credentials, addresses, calibration records and
firmware images remain private.

The subsequent [21–22 October NAND-root trial](nand-root-hardware-trial.md)
uses the updated October 21 base. It confirms SquashFS plus persistent UBIFS
overlay in physical slot 1, return to preserved stock, a second boot with
saved configuration and a later idle check after over three hours of uptime
with both APs enabled and no OOM kill. It does not repeat the older
traffic/performance results below.

On 22 October, the owner also entered [bootloader recovery without UART
input](recovery-without-uart-input.md). LAN1 served the recovery page at
$RECOVERY_HOST with HTTP 200; no firmware was uploaded. This establishes entry
and page access, not a completed factory restoration.

The later [failsafe test and boot-policy review](failsafe-and-boot-policy-review.md)
confirmed button-triggered root SSH on LAN1 with a read-only SquashFS root
and no mounted overlay. The owner called the button WPS; the kernel event
was `rfkill`. Normal NAND-root boot/configuration was restored afterward.
The proposed boot-policy writer was tested offline and was not enabled or
used for a NAND write on this unit.

Current follow-up: the [env-control hardware trial](slot1-env-hardware-trial.md)
completed a real configuration-preserving slot1 sysupgrade and tested the
SSH controller in both directions. OpenWrt is now the durable boot default,
with two default warm boots and one owner-confirmed physical cold start
verified. The review paragraph above describes
the earlier stage before the executor was used on NAND.

The [persistent 5 GHz phone load test](persistent-5ghz-load-test.md) also
completed 1,118 integrity-checked transfer cycles over approximately 14 minutes
on the earlier protected NAND-root image.

## Original read-only NSS initramfs trial

The first SSH trial used Linux 6.18.55 and NSS firmware 12.5. A kernel-only UBI
image was written to the inactive `rootfs_1` partition after verified backups,
an exact RAM-image round trip and label/geometry/attachment checks. Complete
slot readback reconstructed the intended FIT. Readback hashes of active stock,
both BOOTCONFIG partitions and APPSBL remained unchanged.

The one-shot boot wrapper cleared and saved its trial flag before selecting
slot 1 in RAM. All 17 Linux MTD partitions were read-only in the trial. The
subsequent reboot returned to stock Linux 4.4.60 in slot 0; SSH inspection
confirmed the trial flag and durable slot override were absent. This is one
observed return to stock, not recovery from every possible boot failure.

| Test | Observed result | Limit |
| --- | --- | --- |
| Switch probe | RTL8367S-VB; Realtek 802.1Q DSA | This fork's implementation; no inference about mainline support |
| LAN1 link | 1000 Mb/s, full duplex | Other jacks still need cable tests |
| TCP to router / from router | 595.68 / 571.65 Mb/s; no retransmissions | Router endpoint, not WAN routing or NSS acceleration proof |
| Simultaneous TCP directions | 388.53 / 393.58 Mb/s | 17 forward retransmissions; endpoint CPU contributes |
| UDP 100 Mb/s | 0.00576% loss | Five-second sample |
| UDP 500 Mb/s | 438.73 Mb/s received; 12.23% loss | UDP receive-buffer errors increased; Ethernet CRC/FCS errors remained zero |
| MTU 1500 | 1472-byte IPv4 DF ping payload passed | 1473-byte payload correctly rejected locally |
| DHCPv4 | Isolated PC test interface received a lease and pinged router | PC Internet default route preserved |
| IPv6 LAN | Test interface obtained an address and exchanged pings | No external IPv6 service tested |
| Factory data | MAC derivation and external calibration checksum verified | Does not prove RF calibration quality |
| 2.4 GHz phone traffic | 35.137 Mb/s download, 17.582 Mb/s upload | 16 MiB download / 8 MiB upload; payload integrity passed |
| 5 GHz phone traffic | 210.406 Mb/s download, 295.504 Mb/s upload | Same payload checks; initial association needed a retry |

The two Wi-Fi transfers above used the original allocation profile. The phone
also reached LuCI. Neither result is a sustained-load or multi-client test.

## Blocking memory and authentication findings

The original image exhausted available memory with both APs enabled. Kernel
OOM handling killed hostapd and wpa_supplicant. Both radios passing short data
transfers therefore does **not** mean simultaneous AP operation is stable.

The inherited optional `ATH11K_NSS_MEM_PROFILE_256M` profile was compiled and
tried by replacing ath11k modules in RAM. Both radios logged the smaller NSS
allocation profile and available memory increased from approximately 3.4 MiB
to 11 MiB with both APs enabled. Subsequent phone authentication failed despite
the configured passphrase matching the original test network. Logs showed
association followed by disconnection without completing authentication.

This motivated a clean boot to distinguish a profile regression from residual
state after module replacement. Fresh-boot observations are below. Its
successful compilation alone was not hardware validation.

An earlier attempt to load an unstripped debug module also caused OOM. After
target `strip --strip-debug`, module loading succeeded. That deployment error
must be distinguished from the original image's runtime memory exhaustion.

## Smaller-profile clean boot — 21 October

The smaller-profile FIT (`da45dd7ecffef6b3d0910a46be392e52bb6acc32f2bdee428d5e52a0be8c2129`)
was subsequently written to the same inactive diagnostic slot. Full slot
readback reconstructed that FIT exactly; active stock, both BOOTCONFIG
partitions and APPSBL still matched their original backup hashes.

The fresh boot reached Linux 6.18.55 and root SSH over LAN1. All 17 MTD
partitions were read-only; raw environment CRC was valid and both the trial
flag and persistent slot override were absent. Both ath11k radios logged the
smaller profile. Both APs reached ENABLED with BR country settings, channel 1
HE20 and channel 36 HE80. LAN1 negotiated 1000/full and PC-to-router pings
passed. Available memory was approximately 24 MiB shortly after AP startup;
later samples declined, so startup headroom alone is not a stability result.

Phone authentication passed on both bands after the clean boot. The first
5 GHz attempt logged `did not acknowledge authentication response`; a retry
four seconds later completed the RSN four-way handshake. The owner likewise
reported an initial connection error followed by successful connection.
This establishes successful authentication on retry, not first-attempt
reliability. At approximately three minutes uptime, both APs remained enabled,
the 5 GHz station was authorized and available memory was about 15 MiB without
an OOM report.

Both bands subsequently passed the same short data-integrity test:

| Band | Download | Upload | Integrity |
| --- | ---: | ---: | --- |
| 5 GHz | 243.060 Mb/s | 292.796 Mb/s | Both directions passed |
| 2.4 GHz | 161.572 Mb/s | 88.313 Mb/s | Both directions passed |

Both APs remained enabled while one phone moved between bands. This is not
simultaneous client traffic on both radios. Available memory after both short
tests was approximately 11.6 MiB, with no OOM or firmware-crash message.
External-radio NSS wifili delivered/enqueued packet counters increased during
the 5 GHz transfer with zero corresponding RX-delivery/TX-enqueue drop counters.
This demonstrates activity through NSS Wi-Fi, not accelerated WAN routing.

The EX511 build seed selects the inherited smaller profile to reduce the
allocations implicated in the observed initramfs OOM. This remains a
development candidate; memory exhaustion is not considered resolved.
Initramfs also keeps its
unpacked filesystem in RAM (approximately 34 MiB of shmem in this trial);
its memory behavior must not be treated as a measurement of a permanent
SquashFS installation. No persistent-install stability result is available.

The owner then ran a bounded, repeated integrity test for one minute on each
band while both APs remained enabled:

| Band | Elapsed | Successful 16 MiB down / 8 MiB up cycles | Mean download / upload per transfer |
| --- | ---: | ---: | ---: |
| 2.4 GHz | 60.47 s | 37 / 37 | 173.21 / 87.26 Mb/s |
| 5 GHz | 60.42 s | 101 / 101 | 518.55 / 232.85 Mb/s |

Every cycle passed its payload checks. Reported rates are arithmetic means
of the individual directional measurements, not aggregate full-test rates.
No OOM kill or firmware-crash marker was recorded after either test. However,
MemAvailable reached **0 KiB** after the 5 GHz load, despite about 21 MiB
MemFree and `vm.min_free_kbytes=16384`. Available memory accounts for kernel
watermarks/reserves; MemFree alone is not a sufficient health measure. The
limited headroom blocks a stability claim. Longer idle recovery, repeat-load,
multi-client and restart tests remain necessary before permanent installation.

## Physical LAN jacks

After the smaller-profile radio tests, the owner moved the PC cable through
the labelled LAN jacks in order. All four matched their expected DSA names:

| Physical label / DSA interface | Link | PC-to-router ping |
| --- | --- | --- |
| LAN1 / lan1 | 1000 Mb/s, full duplex | 5/5 replies |
| LAN2 / lan2 | 1000 Mb/s, full duplex | 5/5 replies |
| LAN3 / lan3 | 1000 Mb/s, full duplex | 5/5 replies |
| LAN4 / lan4 | 1000 Mb/s, full duplex | 5/5 replies |

This verifies port identity, negotiation and request/reply traffic. Only LAN1
has the earlier full throughput measurements; per-port sustained throughput
and LAN-to-LAN hardware switching have not been measured.

## Isolated WAN, IPv4 NAT and NSS

The owner moved the PC from LAN4 to the EX511 WAN jack, keeping the phone on
the 5 GHz LAN AP. A temporary private static subnet and a source-restricted
SSH exception were configured entirely in RAM. No production uplink was
connected to the EX511; the PC retained Internet through its separate Wi-Fi
connection. The physical WAN jack matched `wan` and negotiated 1000/full.

Phone-to-PC traffic across the LAN/WAN boundary passed 16 MiB download and
8 MiB upload payload checks at 395.69 / 289.51 Mb/s. The PC server observed
the router's synthetic lab WAN address as the source, confirming IPv4 NAT.

The matching ECM TCP flow used the test HTTP port and the expected lab
destination/translated addresses. Its state reported `is_routed=1`,
`nss_v4.ported.can_accel=1` and `nss_v4.ported.accel_mode=2`. The cached source
for the built qca-nss-ecm version defines mode 2 as
`ECM_FRONT_END_ACCELERATION_MODE_ACCEL`. The flow accounted for approximately
8.9 MB / 17.4 MB in the two directions, seven slow-path packets, and no recorded
driver failures, engine NACKs or source mismatches. The IPv4 NSS counters
increased and ECM reported an accelerated TCP connection.

This is hardware evidence of NSS acceleration for this routed IPv4 NAT flow.
It does not measure its speedup versus a disabled-NSS baseline, validate every
traffic type, or establish PPPoE/IPv6 acceleration. Router-local HTTP/HTTPS
ports were rejected from the lab WAN; SSH was reachable through the explicit
source-restricted test exception. Full firewall and L2 isolation testing is
still required. As a basic L2 boundary check, with the PC on the WAN jack the
phone could reach its routed lab address but the owner reported the PC's old
same-LAN HTTP address unreachable. This is one positive/negative test pair,
not exhaustive VLAN/firewall validation.

No OOM kill or firmware-crash marker was recorded after the WAN transfer;
available memory was still low (about 1.6 MiB in the post-transfer snapshot).

The owner returned the cable to LAN1 after the test. Carrier checks confirmed
LAN1 up and WAN down. The temporary WAN address and source-restricted SSH
exception were removed; the WAN configuration returned to DHCP and was brought
down. The final kernel `oom_kill` counter was zero, with about 2.4 MiB
MemAvailable. Changes to the running router's network/AP configuration existed
only in its initramfs RAM filesystem. The permanent stock slot was not replaced.

## Still unverified

- WAN/LAN L2 and full firewall isolation; sustained traffic on every LAN jack.
- PPPoE, external IPv6 and acceleration for additional flow types. Only the
  isolated IPv4 TCP/NAT flow above has direct routed-acceleration evidence.
- Simultaneous client traffic on both radios and sustained memory stability.
- Repeated warm resets, cold power cycles, long load and multiple clients.
- Permanent installation, safe sysupgrade slot behavior and recovery from a
  kernel that loads but fails before usable networking.

The inherited sysupgrade path must not be used during this trial: its slot
handling can overwrite the preserved stock image. UART reception works, but
reliable UART input has not been established. Do not assume the AX55's RX
trace modification identifies the corresponding location on the EX511 PCB.
