# SPDX-License-Identifier: GPL-2.0-only

# Called under ex511_v2_with_factory's lock and read-only UBIFS mount.
ex511_v2_prepare_5g_cal() {
	local factory="$1"
	local output="$2"
	local actual expected base_mac

	# The locally imported BDF must match this unit's factory country/FEM.
	# Never execute/source factory data. The parser emits only two bounded fields.
	[ -f /etc/ex511-v2-bdf-info ] && [ ! -L /etc/ex511-v2-bdf-info ] || return 1
	expected=$(cat /etc/ex511-v2-bdf-info) || return 1
	actual=$(ex511-v2-caldata --radio-info "$factory/0x0434F700") || return 1
	[ "$actual" = "$expected" ] || return 1

	base_mac=$(ex511_v2_mac_from_file "$factory/0x0434F100") || return 1
	# Stock wifi1 uses factory base + 2. Patch only the RAM copy, maintaining
	# the complete EEPROM checksum and setting its firmware MAC-selection flag.
	ex511-v2-caldata --prepare "$factory/0x043A0000" "$output" \
		"$(macaddr_add "$base_mac" 2)"
}
