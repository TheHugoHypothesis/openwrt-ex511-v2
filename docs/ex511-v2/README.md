# EX511 V2 documentation

The maintained user guides below supersede the present-tense status in older
engineering notes. Historical reports are retained as dated evidence, not
silently rewritten as if later results had already existed.

| Read first | Purpose |
| --- | --- |
| [Installation through stock root SSH](installation-ssh.md) | English staged procedure and stop conditions |
| [Instalação por root SSH](installation-ssh.pt-BR.md) | Portuguese installation procedure |
| [Current build recipe](build-current.md) | Exact profiles, private BDF, verification and image distinctions |
| [Hardware / UART](hardware.md) | Observed device, layout and unresolved RX hypothesis |
| [Recovery](recovery.md) | Stock selection, failsafe, Reset HTTP and limits |
| [Results](results.md) | Evidence matrix with image/test boundaries |
| [Network operation](network-operation.md) | Current PPPoE/IPv6 deployment, prefix tests and tuning |
| [Credits](credits.md) | Original work, inherited baseline and this fork's changes |
| [Publication notes](publication.md) | What is public, private and not independently reproduced |

[Source snapshot and historical build identifiers](source-provenance.md).

[Public CI build policy and limitations](public-builds.md).

## Source and build evidence

- [Original NSS/factory-data integration](nss-baseline.md), historical source comparison.
- [21 October comparison](upstream-comparison-2026-10-21.md), pinned refs, not a claim about today's latest upstream release.
- [Original build](build.md) and [validation](validation.md), historical reproducibility logs.
- [Protected NAND-root profile](persistent-slot1.md) and [offline checks](oct21-slot1-validation.md).
- [Environment-control profile](slot1-env-control.md), [build checks](slot1-env-validation.md),
  [actual upgrade/boot selection](slot1-env-hardware-trial.md).

## Hardware evidence and deployment history

- [Initial SSH diagnostic boot](ssh-trial.md).
- [Initial Ethernet/Wi-Fi/NSS tests and memory failures](hardware-results.md).
- [NAND root and saved configuration](nand-root-hardware-trial.md).
- [Persistent 5 GHz integrity load test](persistent-5ghz-load-test.md).
- [Reset recovery entry](recovery-without-uart-input.md) and [failsafe/controller review](failsafe-and-boot-policy-review.md).
- [Earlier AP topology behind W6x](ap-with-w6x.md) and [earlier W6x IPv6 activation](w6x-native-ipv6.md).
- [Transition to EX511 gateway](principal-with-w6x.md) and [completed cleanup](post-cutover-cleanup.md).
- [Current status](status.md) and [future hardware testing](hardware-test-plan.md).

No password, factory dump, calibration payload, SSH private key or owner
firmware binary belongs in an issue or release asset. Report relevant
sanitized facts using the EX511 issue template.

## Placeholder conventions

Maintained installation commands use configurable host variables. Case studies
use symbolic host/network/checkpoint names so that technical topology remains
understandable without publishing a particular person's addresses or files.
Historical commands are evidence; use build-current.md and installation-ssh.md
for the current independent source snapshot. Private migration executors are
not distributed; their guard/validation behavior is documented in the case study.
