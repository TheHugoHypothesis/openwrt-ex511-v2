# Source provenance and incremental upstream history

This branch preserves the public upstream NSS history and adds reviewable
EX511-specific commits on top of the recorded upstream baseline. Personal
session history is not replayed. Older engineering reports retain original
image/source identifiers as provenance; those identifiers are not necessarily
part of the maintained incremental branch.

The deployed historical image was built from ff5b0529bb8beffdcfb4f54d453799f4423d6f1f
and identifies as SNAPSHOT r0+37938-ff5b0529bb8, Linux 6.18.55. Its artifact
hashes and pinned feeds remain in [slot1-env-validation.md](slot1-env-validation.md).
The earlier persistent 5-GHz load used r37932-a72260511bb, not that final image.

The current branch retains firmware functionality and the later reviewed
workstation fixes. Address arguments are explicit and BDF provenance validation
is regional rather than hard-coded to one installation. Rebuilding this branch
produces a new build identity; it is not claimed byte-identical to an older image.

Upstream baseline: kuncy7/openwrt-nss-edma c3po-tag-8021q, including the
October 21 source 9caa35b4d718382ad882cb35c2372dbb569de901.
Credits and source lineage are preserved in [credits.md](credits.md). No private
Git bundle, original local refs or personal deployment configuration is imported.

The 25 October integration advances the upstream merge base through
865da78e2ef7caee3d6854c0b353535413d878c9 while retaining the EX511 guards.
See the [change review and configuration boundary](upstream-update-2026-10-25.md).
