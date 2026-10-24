# Hardware and UART findings

These findings describe one EX511 V2 owner unit. Verify your label, PCB,
bootloader and stock layout before applying installation instructions.
An Archer AX55, EX511 V1 or another similarly named TP-Link is not equivalent.

| Item | Evidence |
| --- | --- |
| SoC | Qualcomm IPQ5018; stock logs sometimes spell it IPQ0518; 2 Cortex-A53 cores |
| RAM | 256 MiB physical; substantially less available to Linux after reserved regions |
| NAND | 128 MiB GigaDevice F50D1G41LB SPI NAND, QPIC; 2048-byte pages, 128-KiB eraseblocks |
| Switch | Driver on owner hardware reports RTL8367S-VB, family-D/RTL8367D path; earlier RTL8367S naming was incomplete |
| CPU/switch link | Current baseline uses 1-Gbit SGMII; do not copy AX55 2.5-Gbit HSGMII settings |
| 2.4 GHz | Integrated IPQ5018 ath11k radio |
| 5 GHz | QCN6102 community PCB identification; stock/OpenWrt use the QCN6122-compatible firmware path, which passed traffic here |
| Stock | Linux 4.4.60; captured U-Boot 2016.01 dated 15 August 2025; FIT configuration config@mp03.3 |

The radio's compatible software identity does not prove that the silicon
marking is QCN6122. Use the firmware/calibration path tested by this tree;
do not substitute blobs solely on a chip-name guess.

## Physical partition layout checked in this project

| Label | Offset | Bytes |
| --- | ---: | ---: |
| 0:SBL1 | 0x0000000 | 0x0080000 |
| 0:MIBIB | 0x0080000 | 0x0080000 |
| 0:BOOTCONFIG | 0x0100000 | 0x0040000 |
| 0:BOOTCONFIG1 | 0x0140000 | 0x0040000 |
| 0:QSEE | 0x0180000 | 0x0100000 |
| 0:DEVCFG | 0x0280000 | 0x0040000 |
| 0:CDT | 0x02c0000 | 0x0040000 |
| 0:APPSBLENV | 0x0300000 | 0x0080000 |
| 0:APPSBL | 0x0380000 | 0x0140000 |
| 0:ART | 0x04c0000 | 0x0100000 |
| 0:TRAINING | 0x05c0000 | 0x0080000 |
| misc_data_ro | 0x0640000 | 0x0600000 |
| misc_data_rw | 0x0c40000 | 0x0600000 |
| rootfs (slot 0) | 0x1240000 | 0x2460000 |
| rootfs_1 (slot 1) | 0x36a0000 | 0x2460000 |
| misc_data_rwbak | 0x5b00000 | 0x0600000 |
| misc_data_isp | 0x6100000 | 0x0600000 |

These are partition labels, not stable MTD indices. Extra virtual MTDs in
stock are not independent physical partitions. This layout is different
from AX55's. Stop if your offsets/sizes/boot selection differ.

## UART: what was and was not established

Owner measurements, in the reported left-to-right orientation:

| Pad | Observation |
| --- | --- |
| 1 | Emits readable boot logs; approximately 1.8 V measured |
| 2 | Candidate router RX; approximately 0 V measured; adapter TX had been connected |
| 3 | Ground |
| 4 | Approximately 3.3 V measured; not connected to adapter power |

This is an observation log, not an orientation-independent pinout or a
schematic. Log reception worked at 115200 8N1 with a 1.8-V adapter. Router
power came from its own supply. Do not connect adapter VCC or drive a
candidate 1.8-V RX from a 3.3/5-V transmitter.

TX-to-RX loopback tested the USB adapter, not the complete board input path.
Continuity to a header pad and resistance to ground did not establish
continuity to the SoC. A feedback stream appeared with the candidate RX
wire attached; disconnecting adapter TX stopped abnormal serial input.

The owner supplied an AX55 wiki describing a factory gap in that model's
RX trace. The EX511 receive-only symptom is compatible with this hypothesis,
but no microscope/trace measurement or successful bridge confirmed it.
**There is no tested EX511 RX-gap location or soldering recipe here.**

The demonstrated workaround is installation/control over root SSH, retaining
UART only for observation. It is not evidence that TX/RX were correctly
identified throughout every earlier wiring attempt. See [recovery](recovery.md).
