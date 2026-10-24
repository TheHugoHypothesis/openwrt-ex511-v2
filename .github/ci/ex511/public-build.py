#!/usr/bin/env python3
"""Prepare, validate and package public EX511 test builds; no private overlay inputs."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path.cwd().resolve()
SCRIPTS = ROOT / 'scripts/ex511-v2'
PROFILES = ['tplink_ex511-v2-initramfs-test', 'tplink_ex511-v2-slot1', 'tplink_ex511-v2-slot1-env']

def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)

def output(args):
    return subprocess.check_output([str(x) for x in args], text=True).strip()

def load(name):
    import sys
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), SCRIPTS/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def prepare(out):
    if (ROOT/'files').exists():
        raise ValueError('Public builds require a clean checkout without files/ or private overlays')
    feeds = {}
    for line in (ROOT/'feeds.conf.default').read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        kind, name, source = line.split()
        if kind != 'src-git' or not re.search(r'\^[0-9a-f]{40}$', source):
            raise ValueError('Every feed must be pinned to an immutable commit')
        url, expected = source.rsplit('^', 1)
        actual = output(['git', '-C', ROOT/'feeds'/name, 'rev-parse', 'HEAD'])
        if actual != expected:
            raise ValueError('Feed checkout does not match the source pin: '+name)
        feeds[name] = {'url': url, 'commit': actual}
    seed = (ROOT/'configs/ex511-v2-slot1-env.config').read_text()
    seed = re.sub(r'^CONFIG_TARGET_qualcommax_ipq50xx_DEVICE_.*=y\n', '', seed, flags=re.M)
    seed += '\nCONFIG_TARGET_MULTI_PROFILE=y\nCONFIG_TARGET_PER_DEVICE_ROOTFS=y\n'
    seed += ''.join('CONFIG_TARGET_DEVICE_qualcommax_ipq50xx_DEVICE_'+p+'=y\n' for p in PROFILES)
    seed += 'CONFIG_BUILD_LOG=y\n'
    (ROOT/'.config').write_text(seed)
    (out/'seed.config').write_text(seed)
    run(['make', 'defconfig'])
    config = (ROOT/'.config').read_text()
    required = [line for line in seed.splitlines() if line.startswith('CONFIG_') and '=y' in line]
    dropped = [line for line in required if line not in config.splitlines()]
    if dropped:
        raise ValueError('defconfig dropped requested symbols: '+', '.join(dropped))
    selected = re.findall(r'^CONFIG_TARGET_DEVICE_qualcommax_ipq50xx_DEVICE_(.*)=y$', config, re.M)
    if sorted(selected) != sorted(PROFILES):
        raise ValueError('Unexpected device profile selection')
    shutil.copy2(ROOT/'.config', out/'complete.config')
    (out/'diffconfig').write_text(output([ROOT/'scripts/diffconfig.sh'])+'\n')
    info = {'source_commit': output(['git','rev-parse','HEAD']),
            'source_date_epoch': int(output(['git','show','-s','--format=%ct','HEAD'])),
            'feeds': feeds, 'profiles': PROFILES, 'private_overlay_included': False,
            'external_radio': 'Matching local regional/FEM BDF provisioning required; no private BDF imported',
            'hardware_validation': 'This CI output has not been tested on physical hardware',
            'package_updates': 'Use matching release package bundle; rolling feeds disabled'}
    write_json(out/'build-info.json', info)
    overlay = ROOT/'files'
    (overlay/'etc/apk/repositories.d').mkdir(parents=True)
    (overlay/'etc/apk/repositories.d/distfeeds.list').write_text(
        '# Public test build: use the matching release APK bundle.\n'
        '# Rolling snapshot repositories are disabled to avoid ABI mismatches.\n')
    write_json(overlay/'etc/ex511-public-build.json', info)

def licenses(out):
    dest = ROOT/'files/usr/share/licenses/ex511-public-build'
    dest.mkdir(parents=True)
    archives = [('nss-firmware-*.tar.zst', '/LICENSE.md', 'NSS-FIRMWARE.txt'),
                ('ath11k-legacy-firmware-*.tar.zst', '/ath11k-firmware/LICENSE.md', 'ATH11K-FIRMWARE.txt')]
    for pattern, suffix, name in archives:
        found = sorted((ROOT/'dl').glob(pattern))
        if len(found) != 1:
            raise ValueError('Missing or ambiguous firmware license archive: '+pattern)
        names = output(['tar','--zstd','-tf',found[0]]).splitlines()
        member = [p for p in names if p.endswith(suffix)]
        if len(member) != 1:
            raise ValueError('Cannot identify exact firmware license: '+name)
        data = subprocess.check_output(['tar','--zstd','-xOf',found[0],member[0]])
        if b'redistribut' not in data.lower():
            raise ValueError('Unexpected firmware license contents')
        (dest/name).write_bytes(data)
    (dest/'README.txt').write_text('Firmware components retain their own licenses; they are not relicensed as GPL.\n'
        'No privately imported regional/FEM BDF or per-device calibration is included.\n'
        'Public upstream board files retain their upstream provenance.\n')
    shutil.copytree(dest, out/'licenses', dirs_exist_ok=True)

def extract_root(image, target):
    with tarfile.open(image, 'r:') as tf:
        matches = [m for m in tf.getmembers() if m.isfile() and m.name.endswith('/root')]
        if len(matches) != 1:
            raise ValueError('Cannot identify exact SquashFS root in sysupgrade')
        squashfs = target/'root.squashfs'
        squashfs.write_bytes(tf.extractfile(matches[0]).read())
    root = target/'rootfs'
    run([ROOT/'staging_dir/host/bin/unsquashfs4', '-no-progress', '-no-xattrs', '-excludes', '-d', root, squashfs, 'dev'],
        stdout=subprocess.DEVNULL)
    return root

def audit_public_root(root):
    for name in ['etc/ex511-v2-bdf-info','etc/ex511-v2-bdf-provenance.json']:
        if (root/name).exists():
            raise ValueError('Private BDF overlay marker is forbidden in a public CI image')
    for pattern in ['etc/dropbear/dropbear_*_host_key','root/.ssh/*','etc/ssh/ssh_host_*_key']:
        if list(root.glob(pattern)):
            raise ValueError('Preprovisioned device/authentication keys are forbidden')
    for name in ['etc/config/network','etc/config/wireless']:
        p = root/name
        if p.exists() and re.search(r'option\s+(?:username|password|key)\s+', p.read_text()):
            raise ValueError('Preprovisioned network credentials are forbidden')
    if not (root/'etc/ex511-public-build.json').is_file():
        raise ValueError('Missing public-build provenance')
    if not (root/'usr/share/licenses/ex511-public-build/NSS-FIRMWARE.txt').is_file():
        raise ValueError('Missing firmware license notice')

def validate(out):
    images = ROOT/'bin/targets/qualcommax/ipq50xx'
    kernels = list((ROOT/'build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx').glob('linux-*/.config.set'))
    if len(kernels) != 1:
        raise ValueError('Cannot identify exact kernel configuration')
    kconfig = kernels[0]
    shutil.copy2(kconfig, out/'kernel.config')
    validator = load('validate-nss-build')
    slot = load('check-slot1-image')
    assessment = load('assess-ssh-trial')
    results = {}
    for profile in PROFILES:
        dtb = ROOT/'build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx'/('image-ipq5018-'+profile.replace('tplink_', 'tplink-')+'.dtb')
        trial = profile.endswith('initramfs-test')
        env = profile.endswith('slot1-env')
        validator.validate_dtb(dtb, readonly_trial=trial, slot1=not trial, env_control=env)
        if trial:
            fit = images/('openwrt-qualcommax-ipq50xx-'+profile+'-initramfs-uImage.itb')
            candidate = assessment.fit_metadata(fit.read_bytes())
            if candidate['writable_nand_partitions'] or candidate['kernel_overlaps_stock_fit_input']:
                raise ValueError('Unsafe diagnostic FIT protection or load geometry')
            if re.search(r'(?:^|\s)(?:root|ubi\.mtd)=', candidate['bootargs_append']):
                raise ValueError('Diagnostic image selects a persistent root')
            leb = (fit.stat().st_size+126975)//126976
            ini = out/'trial-ubinize.ini'
            ini.write_text(f'[kernel]\nmode=ubi\nimage={fit}\nvol_id=0\nvol_type=dynamic\nvol_name=kernel\nvol_size={leb*126976}\n')
            ubi = images/'ex511-v2-readonly-trial.ubi'
            run([ROOT/'staging_dir/host/bin/ubinize','-m','2048','-p','128KiB','-s','2048','-O','2048','-o',ubi,ini])
            results[profile] = load('check-trial-ubi').check(ubi.read_bytes(),fit.read_bytes())
        else:
            stem = images/('openwrt-qualcommax-ipq50xx-'+profile+'-squashfs')
            image = Path(str(stem)+'-sysupgrade.bin')
            ubi = Path(str(stem)+'-factory.ubi')
            cmd = ['python3',SCRIPTS/'check-slot1-image.py','--sysupgrade',image,'--ubi',ubi,
                   '--kernel-config',kconfig,'--fwtool',ROOT/'staging_dir/host/bin/fwtool']
            if env:
                cmd.append('--env-control')
            run(cmd)
            with tempfile.TemporaryDirectory(prefix='ex511-public-root-') as tmp:
                root = extract_root(image,Path(tmp))
                validator.validate_rootfs(root,False)
                audit_public_root(root)
            results[profile] = {'image_sha256':digest(image),'factory_ubi_sha256':digest(ubi),'privacy_audit':'passed'}
    write_json(out/'validation.json',results)
    (out/'VALIDATED').write_text('All three profiles passed offline checks; no physical-hardware result is implied.\n')

def tar_zstd(dest, cwd, paths, excludes=()):
    cmd = ['tar','--zstd','-cf',dest,*['--exclude='+x for x in excludes],'-C',cwd,*paths]
    run(cmd)

def package(out):
    if not (out/'VALIDATED').is_file():
        raise ValueError('Refusing to package unvalidated images')
    assets = out/'assets'
    assets.mkdir()
    images = ROOT/'bin/targets/qualcommax/ipq50xx'
    for p in images.iterdir():
        if p.is_file() and (p.suffix in ['.bin','.ubi','.itb','.manifest','.json','.buildinfo']):
            shutil.copy2(p,assets/p.name)
    for name in ['complete.config','seed.config','diffconfig','kernel.config','build-info.json','validation.json']:
        shutil.copy2(out/name,assets/name)
    tar_zstd(assets/'third-party-license-notices.tar.zst',out,['licenses'])
    package_paths = ['bin/targets/qualcommax/ipq50xx/packages']
    if (ROOT/'bin/packages').is_dir():
        package_paths.append('bin/packages')
    tar_zstd(assets/'matching-packages.tar.zst',ROOT,package_paths)
    # Corresponding source: exact checkout, feed source and downloaded source archives.
    source_tar = out/'source-snapshot.tar'
    run(['git','archive','--format=tar','-o',source_tar,'HEAD'])
    run(['zstd','-T0','-3',source_tar,'-o',assets/'source-snapshot.tar.zst'])
    tar_zstd(assets/'pinned-feed-sources.tar.zst',ROOT,['feeds'],excludes=['.git','*.index','*.targetindex'])
    # Split large source-download bundles to stay below GitHub's per-asset limit.
    downloads = out/'source-downloads.tar.zst'
    tar_zstd(downloads,ROOT,['dl'])
    if downloads.stat().st_size > 1900*1024*1024:
        run(['split','-b','1900M','-d',downloads,str(assets/'source-downloads.tar.zst.part-')])
    else:
        shutil.move(downloads,assets/downloads.name)
    info = json.loads((out/'build-info.json').read_text())
    (assets/'TESTING.md').write_text('''# Experimental EX511 V2 public test images

No image in this release has been hardware-tested as a new CI build.
No private regional/FEM BDF or per-device calibration is included. The external
5-GHz radio requires matching local provisioning; its guard is not bypassed.
Use Ethernet for first access. These are not signed stock-web installation images.

Start with the read-only initramfs-test FIT/kernel-only UBI and the staged root-SSH
guide. Protected slot1 images preserve stock slot0. The slot1-env profile additionally
permits reviewed environment writes; installing it does not select a boot policy.
Do not substitute the profiles or use sysupgrade -F. Match your hardware/bootloader,
back up privately and verify readbacks. There is no arbitrary-hang A/B rollback.

Rolling package repositories are disabled. Use only the matching APK bundle from
this release. Never mix official snapshot kmods with this kernel. Original license
notices and corresponding source bundles are included. If source-download parts
are present, concatenate them in lexical order before extracting the archive.

Reproduce with the pinned source/feed commits and the CI workflow at:
'''+f'https://github.com/TheHugoHypothesis/openwrt-ex511-v2/commit/{info["source_commit"]}\n')
    (assets/'sha256sums').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in sorted(assets.iterdir()) if p.is_file()))
    print('Validated public assets:',len(list(assets.iterdir())))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['prepare','licenses','validate','package'])
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.is_relative_to(ROOT):
        raise ValueError('CI output must stay outside the source checkout')
    out.mkdir(parents=True,exist_ok=True)
    globals()[a.stage](out)

if __name__=='__main__':
    main()
