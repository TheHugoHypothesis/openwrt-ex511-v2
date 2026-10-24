// SPDX-License-Identifier: GPL-2.0-only
/* EX511 radio records: bounded reads, EEPROM checksum and RAM-file preparation. */
#define _GNU_SOURCE
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define CAL_SIZE 131072

static int read_record(const char *path, unsigned char *data, size_t length)
{
	struct stat st;
	size_t done = 0;
	ssize_t n;
	int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);

	if (fd < 0)
		return -1;
	if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size != (off_t)length) {
		close(fd);
		return -1;
	}
	while (done < length) {
		n = read(fd, data + done, length - done);
		if (n < 0 && errno == EINTR)
			continue;
		if (n <= 0) {
			close(fd);
			return -1;
		}
		done += n;
	}
	close(fd);
	return 0;
}

static uint16_t get_word(const unsigned char *data, size_t offset)
{
	return data[offset] | ((uint16_t)data[offset + 1] << 8);
}

static bool valid_cal(const unsigned char *data)
{
	uint16_t checksum = 0;
	size_t i;

	/* Observed EX511 QCN6122 EEPROM format, not the vendor flash-write API's header. */
	if (memcmp(data, "\x01\x00\x04\x04", 4))
		return false;
	for (i = 0; i < CAL_SIZE; i += 2)
		checksum ^= get_word(data, i);
	return checksum == 0xffff;
}

static int parse_mac(const char *s, unsigned char *mac)
{
	unsigned int octets[6];
	unsigned int i;
	int consumed = 0;

	if (strlen(s) != 17 || sscanf(s, "%2x:%2x:%2x:%2x:%2x:%2x%n",
		&octets[0], &octets[1], &octets[2], &octets[3], &octets[4], &octets[5],
		&consumed) != 6 || consumed != 17)
		return -1;
	for (i = 0; i < 6; i++) {
		if (!isxdigit((unsigned char)s[3 * i]) || !isxdigit((unsigned char)s[3 * i + 1]))
			return -1;
		mac[i] = octets[i];
	}
	if ((mac[0] & 1) || !memcmp(mac, "\0\0\0\0\0\0", 6) ||
	    !memcmp(mac, "\x00\x11\x22\x33\x44\x55", 6) ||
	    !memcmp(mac, "\x00\x11\x22\x33\x44\x56", 6))
		return -1;
	return 0;
}

static void patch_word(unsigned char *data, size_t offset, uint16_t value)
{
	uint16_t checksum = get_word(data, 0xa) ^ get_word(data, offset) ^ value;

	data[offset] = value;
	data[offset + 1] = value >> 8;
	data[0xa] = checksum;
	data[0xb] = checksum >> 8;
}

static int publish_cal(const char *path, const unsigned char *data)
{
	char *temporary;
	size_t done = 0;
	ssize_t n;
	int fd, ret = -1;

	if (asprintf(&temporary, "%s.XXXXXX", path) < 0)
		return -1;
	fd = mkstemp(temporary);
	if (fd < 0) {
		free(temporary);
		return -1;
	}
	while (done < CAL_SIZE) {
		n = write(fd, data + done, CAL_SIZE - done);
		if (n < 0 && errno == EINTR)
			continue;
		if (n <= 0)
			goto out;
		done += n;
	}
	if (fchmod(fd, 0644))
		goto out;
	if (close(fd)) {
		fd = -1;
		goto out;
	}
	fd = -1;
	/* Atomic publication without replacing an existing file or following a symlink. */
	if (!link(temporary, path))
		ret = 0;
out:
	if (fd >= 0)
		close(fd);
	unlink(temporary);
	free(temporary);
	return ret;
}

static bool delimiter(unsigned char c)
{
	return c == 0 || c == ';' || isspace(c);
}

static int get_field(const unsigned char *data, size_t length, const char *key,
		     char *out, size_t capacity)
{
	size_t i, j, n = strlen(key);
	bool found = false;

	for (i = 0; i + n < length; i++) {
		if ((i && !delimiter(data[i - 1])) || memcmp(data + i, key, n))
			continue;
		if (found)
			return -1;
		for (j = 0; i + n + j < length && !delimiter(data[i + n + j]); j++) {
			if (j + 1 >= capacity)
				return -1;
			out[j] = data[i + n + j];
		}
		if (!j || i + n + j == length)
			return -1;
		out[j] = 0;
		found = true;
	}
	return found ? 0 : -1;
}

static int radio_info(const char *path)
{
	unsigned char data[256];
	char country[3], fem[7];

	if (read_record(path, data, sizeof(data)) ||
	    get_field(data, sizeof(data), "Country=", country, sizeof(country)) ||
	    get_field(data, sizeof(data), "FEM_MASK_5G=", fem, sizeof(fem)))
		return -1;
	if (strlen(country) != 2 || country[0] < 'A' || country[0] > 'Z' ||
	    country[1] < 'A' || country[1] > 'Z' ||
	    (strlen(fem) != 2 && strlen(fem) != 6) || !isdigit((unsigned char)fem[0]) ||
	    !isdigit((unsigned char)fem[1]) || (strlen(fem) == 6 && strcmp(fem + 2, "_FCC")))
		return -1;
	printf("%s %s\n", country, fem);
	return 0;
}

int main(int argc, char **argv)
{
	unsigned char *data, mac[6];
	int ret = 1;
	size_t i;

	if (argc == 3 && !strcmp(argv[1], "--radio-info")) {
		if (!radio_info(argv[2]))
			return 0;
		fputs("ex511-v2-caldata: invalid radio selection record\n", stderr);
		return 1;
	}
	if (!((argc == 3 && !strcmp(argv[1], "--verify")) ||
	      (argc == 5 && !strcmp(argv[1], "--prepare")))) {
		fputs("Usage: ex511-v2-caldata --verify FILE | --radio-info FILE | --prepare INPUT OUTPUT MAC\n", stderr);
		return 2;
	}
	data = malloc(CAL_SIZE);
	if (!data)
		return 1;
	if (read_record(argv[2], data, CAL_SIZE) || !valid_cal(data)) {
		fputs("ex511-v2-caldata: invalid EEPROM size, header or checksum\n", stderr);
		goto out;
	}
	if (argc == 3) {
		ret = 0;
		goto out;
	}
	if (parse_mac(argv[4], mac)) {
		fputs("ex511-v2-caldata: invalid radio MAC\n", stderr);
		goto out;
	}
	for (i = 0; i < sizeof(mac); i += 2)
		patch_word(data, 0xe + i, get_word(mac, i));
	patch_word(data, 0x3e, get_word(data, 0x3e) | 1);
	if (!valid_cal(data) || publish_cal(argv[3], data)) {
		fputs("ex511-v2-caldata: could not publish prepared RAM calibration\n", stderr);
		goto out;
	}
	ret = 0;
out:
	free(data);
	return ret;
}
