# Physical cutover and cleanup — 24 October 2026

> **Anonymized deployment case study.** Addresses and local checkpoint paths
> are placeholders, not usable configuration. Operator-specific automation
> is not published; this report preserves topology, observations and limits.

The owner completed the cable change and reported working Internet. Read-only
inspection then confirmed EX511 PPPoE up with a native IPv6 delegated /64,
and downstream router using DHCP WAN with gateway $EX511_HOST. downstream router's detached migration log
recorded successful guarded IPv4 confirmation. Its googlespecs network uses
RA/DHCPv6/NDP relay; the workstation was connected by Ethernet to that network.

## Configuration cleanup applied

- Executed the EX511 finalizer only after observing LAN2 carrier down and
  working PPPoE Internet. LAN2 was added back to br-lan; all LAN1–4 now belong
  to the EX511 client LAN, along with the existing Wi-Fi APs.
- Removed EX511 migration_uplink and its DHCP section, masquerading zone,
  forwarding and temporary SSH/DHCP rules. The sole default IPv4 route is
  through pppoe-wan. EX511 LAN remains $EX511_HOST/24.
- Removed downstream router ex511_offline_access, the temporary SSH exception for the
  workstation's former legacy-Wi-Fi address. Normal access through the main
  downstream router LAN remains available. The link-local UDP 547 rule is retained because
  it supports the active DHCPv6 relay; it is not migration debris.
- Preserved downstream router LAN/VLAN configuration, Wi-Fi, DNS/adblock and LED scheduling.
  The independent legacy LAN remains; it is user configuration, not disposable
  migration state. EX511 PPPoE credentials, Wi-Fi, factory data and boot policy
  were not altered by cleanup. No deliberate reboot/flash was performed.

## Files and recovery copies

Reviewed old deployment directories were compressed into root-only archives,
copied to private workstation storage, opened to check archive membership and
SHA256 compared between copies before deleting the original directories.

EX511 directories consolidated:

- <PRIVATE_CHECKPOINT>
- <PRIVATE_CHECKPOINT>, including the finalizer's checkpoint

downstream router directories consolidated:

- <PRIVATE_MIGRATION_CHECKPOINT>
- /root/downstream-router-isp-offline
- <PRIVATE_CHECKPOINT>
- <PRIVATE_CHECKPOINT>

Each router retains <PRIVATE_RECOVERY_DIR> with:

- migration-history-20261024.tar.gz — earlier checkpoints, scripts and logs
- working-config-20261024.tar.gz — current network/dhcp/firewall/wireless
- README.txt — role and recovery cautions

The directory is mode 0700 and archives mode 0600. These contain credentials
and must not be published. Off-device copies are in the private cleanup
checkpoint selected by <PRIVATE_EVIDENCE_DIR>/current-cleanup-path.
Historical restore scripts are now inside archives, not loose executable
rollback paths. No active migration guard was found before consolidation.

On the workstation, archived then removed the task's /tmp/ex511-transition
helpers and generated offline-cutover Python bytecode. The two cleanup helper
scripts and their bytecode were also archived then removed at completion.
The saved Ethernet and Wi-Fi NetworkManager profiles were already automatic:
no temporary static addresses/routes, DNS override or saved metric change
remained, so they were left untouched. Ethernet had only its DHCP IPv4 lease;
Wi-Fi was inactive. Unrelated Wi-Fi profiles and Tailscale were preserved.
Source repositories, stock firmware dumps, build artifacts and private
recovery evidence were retained. This is targeted migration cleanup, not a
purge of valuable firmware/build data or application caches.

The workstation offline installer now refuses to run when the private
principal-cutover-completed marker exists. Its source/instructions remain as
historical project documentation, with a completed warning, rather than being
silently deleted from Git.

## Results after cleanup

- EX511: fw4 check passes; Internet IPv4 and IPv6 ping both 3/3.
- downstream router: fw4 check passes; Internet IPv4 and IPv6 ping both 3/3.
- Workstation behind downstream router: HTTPS forced to IPv4 and separately to IPv6 both
  returned HTTP 200 from openwrt.org. This confirms an actual downstream
  IPv6 client path through downstream router relay and EX511, not merely router addresses.
- Pinned-key root SSH works on both current management addresses.
- No pending network/dhcp/firewall UCI edits remained at the final check.

These short functional checks do not establish prolonged relay stability,
IPv6 isolation, renewal/reconnect robustness or PPPoE NSS acceleration.
Those remain separate testing tasks.
