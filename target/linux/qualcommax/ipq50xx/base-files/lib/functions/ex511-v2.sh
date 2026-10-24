# SPDX-License-Identifier: GPL-2.0-only
# EX511 factory data is UBIFS, not a fixed-offset raw flash structure.

ex511_v2_mac_from_file() {
	local record="$1"
	local mac

	[ -f "$record" ] && [ ! -L "$record" ] || return 1
	[ "$(wc -c < "$record")" -eq 6 ] || return 1
	mac=$(get_mac_binary "$record" 0)

	# Six complete octets, unicast, non-zero, and no stock GMAC placeholders.
	echo "$mac" | grep -Eq '^([0-9a-f]{2}:){5}[0-9a-f]{2}$' || return 1
	[ $((0x${mac%%:*} & 1)) -eq 0 ] || return 1
	case "$mac" in
	00:00:00:00:00:00|00:11:22:33:44:55|00:11:22:33:44:56)
		return 1
		;;
	esac

	printf '%s\n' "$mac"
}

ex511_v2_with_factory() (
	local callback="$1"
	shift
	local mtd_num flags ubidev mountpoint
	local attached=0 mounted=0
	local PATH="/usr/sbin:/usr/bin:/sbin:/bin"
	local lockdir=/tmp/lock

	# Network defaults and firmware hotplug can overlap. Hold the same lock
	# through unmount/detach so neither reader tears down another's UBI.
	mkdir -p "$lockdir" || return 1
	exec 9>"$lockdir/ex511-v2-factory.lock"
	flock -x -w 30 9 || return 1

	# The caller sources functions/system.sh and upgrade/nand.sh. Never use
	# nand_attach_ubi(): its recovery path may format an unrecognized UBI.
	mtd_num=$(find_mtd_index misc_data_ro)
	[ -n "$mtd_num" ] || return 1
	flags=$(cat "/sys/class/mtd/mtd$mtd_num/flags" 2>/dev/null)
	[ -n "$flags" ] || return 1
	[ $((flags & 0x400)) -eq 0 ] || return 1 # MTD_WRITEABLE must be clear.

	trap '
		if [ "$mounted" -eq 1 ]; then
			umount "$mountpoint" || exit 1
		fi
		[ -z "$mountpoint" ] || rmdir "$mountpoint"
		if [ "$attached" -eq 1 ]; then
			ubidetach -m "$mtd_num" >/dev/null 2>&1
		fi
	' EXIT

	ubidev=$(nand_find_ubi misc_data_ro)
	if [ -z "$ubidev" ]; then
		ubiattach -m "$mtd_num" >/dev/null 2>&1 || return 1
		attached=1
		ubidev=$(nand_find_ubi misc_data_ro)
	fi
	[ -n "$ubidev" ] || return 1
	[ "$(cat "/sys/class/ubi/$ubidev/ro_mode" 2>/dev/null)" = 1 ] || return 1

	mountpoint=$(mktemp -d /tmp/ex511-v2-factory.XXXXXX) || return 1
	mount -t ubifs -o ro,noatime "$ubidev:misc_ro" "$mountpoint" || return 1
	mounted=1

	"$callback" "$mountpoint" "$@"
)

ex511_v2_factory_mac_record() {
	# 0x0434F100 is a vendor record filename, not a physical NAND offset.
	ex511_v2_mac_from_file "$1/0x0434F100"
}

ex511_v2_get_factory_mac() {
	ex511_v2_with_factory ex511_v2_factory_mac_record
}
