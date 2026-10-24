#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile the complete EX511 DTS against an already prepared target kernel."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-dir', type=Path, required=True,
                        help='patched Linux directory from target/linux/prepare')
    parser.add_argument('--dtc', required=True, help='host device tree compiler')
    parser.add_argument('--output', type=Path, required=True, help='output board DTB')
    parser.add_argument('--dts', default='ipq5018-tplink-ex511-v2.dts',
                        help='board filename in target/linux/qualcommax/dts')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    kernel = args.kernel_dir.resolve()
    if not (kernel / 'arch/arm64/boot/dts/qcom/ipq5018.dtsi').is_file():
        parser.error('--kernel-dir must contain the prepared IPQ5018 target sources')
    source = root / 'target/linux/qualcommax/dts' / args.dts
    if Path(args.dts).name != args.dts or not source.is_file():
        parser.error('--dts must name an existing target board file')
    with tempfile.TemporaryDirectory(prefix='ex511-dtb-') as work:
        preprocessed = Path(work) / 'ex511.pp.dts'
        subprocess.run([
            'gcc', '-E', '-P', '-x', 'assembler-with-cpp', '-nostdinc', '-undef',
            '-D__DTS__', '-I' + str(kernel / 'include'),
            '-I' + str(kernel / 'arch/arm64/boot/dts/qcom'),
            '-I' + str(source.parent), str(source), '-o', str(preprocessed),
        ], check=True)
        subprocess.run([
            args.dtc, '-I', 'dts', '-O', 'dtb', str(preprocessed),
            '-o', str(args.output),
        ], check=True)
    print(f'PASS: {source.name} compiled against prepared target sources')
    print('Compilation does not establish schema compliance or hardware operation.')


if __name__ == '__main__':
    main()
