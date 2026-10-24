# Publication and privacy boundaries

This publication includes source, generic installation/build/recovery guidance,
technical comparisons and anonymized test reports. It does not include stock
passwords, account settings, SSH private keys, per-unit addresses, raw device
logs, NAND/environment dumps, calibration payloads or deployment automation.

Technical findings are retained: partition geometry, boot-policy semantics,
firmware/source versions, image hashes, aggregate traffic results, memory
failures, recovery limits and differences between tested images. Dates and
aggregate hardware measurements are evidence, not executable network settings.

Reports of the example two-router deployment use symbolic address/path
placeholders. They are not instructions to reproduce an operator's network.
The installation guide supplies configurable targets rather than published local
addresses. Read [source-provenance.md](source-provenance.md) before attempting
to reproduce a historical hash or follow an old commit reference.

The release is experimental source and documentation, with no private firmware
assets. The source licenses and third-party notices remain intact. Matching
BDF/calibration provenance is required locally; redistribution rights are not
assumed. Root access to stock is a prerequisite, not a universal unlock
provided here. UART input is not required by the SSH workflow. The suggested
RX-gap explanation is not physically confirmed for EX511.

No claim is made of automatic arbitrary-hang rollback, a completed recovery
upload, power-fail-safe environment writes, independent installations on every
regional variant or a fresh firmware build from a documentation release.

Use the issue template for sanitized reproduction details. Never post config
exports, raw captures or credentials. A public CI run verifies source fixtures;
it cannot validate a flash operation or RF behavior on someone else's router.
