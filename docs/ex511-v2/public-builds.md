# Public CI test builds

The workflow EX511 reproducible public test build is an owner-triggered,
source-pinned build on a clean hosted runner. It fetches the exact feeds in
feeds.conf.default and builds three profiles together with the additional
NSS/ath11k 256-MiB allocation profile enabled:

- All-read-only initramfs diagnostic FIT and kernel-only UBI.
- Protected persistent physical-slot1 sysupgrade and factory UBI.
- Explicit slot1 environment-control sysupgrade and factory UBI.

No private overlay, stock extraction, per-device calibration or network
configuration is accepted by the public workflow. The images use the public
upstream firmware/board packages already selected by this source. **They do
not contain a locally imported matching regional/FEM 5-GHz BDF or its marker.**
The external radio's provisioning guard is preserved and 5 GHz requires
separate matching local provisioning; do not interpret its absence as a
new driver regression. Start testing through Ethernet. Radio defaults stay
disabled as on an ordinary initial OpenWrt configuration.

Do not install a random regional BDF or bypass the guard. The private importer
is a local workflow described in build-current.md; redistribution permission
for someone else's extracted board data is not established by CI.

## Reproduction and provenance

Each release identifies the exact Git commit and feed commits, requested and
expanded configs, kernel config, manifests and validation results. The workflow
fixes SOURCE_DATE_EPOCH to the source commit and records host package versions;
actions are pinned to immutable commits. This is a repeatable source/build
recipe, not a claim that different hosts/reruns must produce bit-identical
artifacts. Dependencies/download hashes are checked by the OpenWrt build.

Run the workflow from a reviewed branch through GitHub Actions or reproduce
its ordered steps on Ubuntu 24.04. The build helper refuses a pre-existing
files/ directory, verifies feed pins and checks every requested profile/option
survives make defconfig. No repository secret provides board data.

## Publication gates

A successful compile alone is insufficient. Before a draft is published:

1. The compiled device trees must match the physical geometry/protection profiles.
2. Persistent image metadata, UBI tables/CRCs, exact payload reconstruction and
   stock FIT loading assumptions must pass existing offline checkers.
3. Actual SquashFS roots must contain the expected factory/NSS/ath11k helpers,
   no private BDF marker/provenance, no predefined authentication/device keys
   and no configured network credentials.
4. The diagnostic FIT must protect all NAND partitions and avoid a persistent
   root/load overlap; its generated kernel-only UBI must reconstruct exactly.
5. Upgrade/boot-controller fixture tests must pass. None of these gates proves
   operation on a second router or power-loss-safe recovery.

## Assets and package updates

Releases include checksums, exact configs, manifests, offline validation,
firmware license notices, matching APK bundles, source snapshot, pinned feed
sources and downloaded source archives. Large source archives may be split;
concatenate parts in lexical order before extracting. Preserve component
licenses: binary firmware is not relicensed under GPL.

Rolling package repositories are deliberately disabled in these experimental
images to avoid incompatible kmods and core packages. Use only the matching
release bundle or build additional packages from the same source/config.
No private package signing key is published; image/package public keys are
part of their normal build. Do not use --allow-untrusted or force a kernel
ABI mismatch as an update strategy.

These artifacts are test candidates, not previously hardware-qualified owner
images. Follow installation-ssh.md and recovery.md, verify your unit first,
keep off-device backups, and never use sysupgrade -F. The CI publishes a
prerelease only after every required build/validation step succeeds; failed
runs keep diagnostic logs but publish no usable-image claim.
