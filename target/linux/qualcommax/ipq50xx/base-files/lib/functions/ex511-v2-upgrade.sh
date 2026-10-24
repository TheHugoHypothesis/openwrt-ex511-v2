#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only

# No bootloader/environment/BOOTCONFIG writes. The only upgrade destination
# accepted here is an explicitly selected physical-slot-1 firmware profile.
# The opt-in env-control variant permits APPSBLENV, but this upgrader never
# writes it. Require matching image metadata to retain that control on upgrade.
ex511_slot1_check_layout() {
	local target stock env path value index count=0 writable=0 ubi_args=0 token
	local env_control=0 expected_writable=1

	[ -e /proc/device-tree/chosen/openwrt,ex511-slot1-layout ] || {
		echo "EX511: boot the dedicated slot1 profile; this layout cannot sysupgrade."
		return 1
	}
	target=$(find_mtd_index rootfs_1)
	stock=$(find_mtd_index rootfs)
	case "$target:$stock" in
		*[!0-9:]*|:*|*:) return 1 ;;
	esac
	[ "$target" != "$stock" ] || return 1
	if [ -e /proc/device-tree/chosen/openwrt,ex511-env-control ]; then
		env_control=1
		expected_writable=2
		env=$(find_mtd_index 0:APPSBLENV)
		case "$env" in ''|*[!0-9]*) return 1 ;; esac
		[ "$env" != "$target" ] && [ "$env" != "$stock" ] || return 1
		path="/sys/class/mtd/mtd$env"
		[ "$(cat "$path/offset" 2>/dev/null)" = 3145728 ] || return 1
		[ "$(cat "$path/size" 2>/dev/null)" = 524288 ] || return 1
		[ "$(cat "$path/erasesize" 2>/dev/null)" = 131072 ] || return 1
		[ "$(cat "$path/writesize" 2>/dev/null)" = 2048 ] || return 1
	fi
	for index in "$target" "$stock"; do
		path="/sys/class/mtd/mtd$index"
		[ "$(cat "$path/size" 2>/dev/null)" = 38141952 ] || return 1
		[ "$(cat "$path/erasesize" 2>/dev/null)" = 131072 ] || return 1
	done
	[ "$(cat /sys/class/mtd/mtd"$target"/offset 2>/dev/null)" = 57278464 ] || return 1
	[ "$(cat /sys/class/mtd/mtd"$stock"/offset 2>/dev/null)" = 19136512 ] || return 1
	for path in /sys/class/mtd/mtd*; do
		index=${path##*/mtd}
		case "$index" in ''|*[!0-9]*) continue ;; esac
		value=$(cat "$path/flags" 2>/dev/null) || return 1
		case "$value" in 0x0|0x400) ;; *) return 1 ;; esac
		if [ "$index" = "$target" ] || { [ "$env_control" = 1 ] && [ "$index" = "$env" ]; }; then
			[ "$value" = 0x400 ] || return 1
			writable=$((writable + 1))
		else
			[ "$value" = 0x0 ] || return 1
		fi
		count=$((count + 1))
	done
	[ "$count:$writable" = "17:$expected_writable" ] || return 1
	for token in $(cat /proc/cmdline); do
		case "$token" in
			ubi.mtd=rootfs_1) ubi_args=$((ubi_args + 1)) ;;
			ubi.mtd=*) return 1 ;;
		esac
	done
	[ "$ubi_args" = 1 ] || return 1
}

ex511_slot1_check_image() {
	local meta compat keys key device found=0 env_found=0
	meta=$(mktemp /tmp/ex511-slot1-meta.XXXXXX) || return 1
	if ! fwtool -q -i "$meta" "$1"; then
		rm -f "$meta"
		return 1
	fi
	. /usr/share/libubox/jshn.sh
	json_load "$(cat "$meta")"
	local result=$?
	rm -f "$meta"
	[ "$result" = 0 ] || return 1
	json_get_var compat compat_version
	[ "$compat" = 2.0 ] || return 1
	json_select new_supported_devices || return 1
	json_get_keys keys
	for key in $keys; do
		json_get_var device "$key"
		[ "$device" != tplink,ex511-v2-slot1 ] || found=1
		[ "$device" != tplink,ex511-v2-slot1-env ] || env_found=1
	done
	[ "$found" = 1 ] || return 1
	if [ -e /proc/device-tree/chosen/openwrt,ex511-env-control ]; then
		[ "$env_found" = 1 ] || return 1
	fi
	return 0
}

ex511_slot1_pre_upgrade() {
	ex511_slot1_check_layout && ex511_slot1_check_image "$1" || {
		echo "EX511: refusing upgrade: slot, protection, boot arguments or image do not match."
		return 1
	}
	CI_UBIPART=rootfs_1
	CI_KERN_UBIPART=rootfs_1
	CI_ROOT_UBIPART=rootfs_1
	CI_DATA_UBIPART=rootfs_1
	CI_KERNPART=kernel
	CI_ROOTPART=rootfs
}
