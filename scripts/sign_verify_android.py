"""Sign the final APK with the private release identity and verify its public fingerprint."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

sdk = Path(os.environ['ANDROID_HOME'])
tools = sorted((sdk / 'build-tools').glob('*/apksigner'))[-1].parent
apk = Path('apps/mobile/android/app/build/outputs/apk/release/app-release.apk')
expected = Path('docs/android-release-certificate.sha256').read_text().strip()
out = Path('artifacts/android-verification')
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    keystore = Path(directory) / 'release.p12'
    keystore.write_bytes(base64.b64decode(os.environ['ANDROID_RELEASE_KEYSTORE_BASE64'], validate=True))
    keystore.chmod(0o600)
    signed = Path(directory) / 'signed.apk'
    subprocess.run([str(tools/'apksigner'), 'sign', '--ks', str(keystore), '--ks-type', 'PKCS12',
        '--ks-key-alias', os.environ['ANDROID_RELEASE_KEY_ALIAS'],
        '--ks-pass', 'env:ANDROID_RELEASE_STORE_PASSWORD', '--key-pass', 'env:ANDROID_RELEASE_KEY_PASSWORD',
        '--v1-signing-enabled', 'true', '--v2-signing-enabled', 'true', '--v3-signing-enabled', 'true',
        '--out', str(signed), str(apk)], check=True)
    apk.write_bytes(signed.read_bytes())

def run(tool, *args):
    return subprocess.check_output([str(tools/tool), *args], text=True, stderr=subprocess.STDOUT)
signature = run('apksigner', 'verify', '--verbose', '--print-certs', str(apk))
assert f'certificate SHA-256 digest: {expected}' in signature, 'Unexpected signing identity'
assert 'CN=Android Debug' not in signature, 'Debug signing certificate must never be released'
assert 'Verified using v2 scheme (APK Signature Scheme v2): true' in signature
assert 'Verified using v3 scheme (APK Signature Scheme v3): true' in signature
metadata = run('aapt', 'dump', 'badging', str(apk))
config = json.loads(Path('apps/mobile/app.json').read_text())['expo']
assert f"name='{config['android']['package']}' versionCode='{config['android']['versionCode']}' versionName='{config['version']}'" in metadata
assert "sdkVersion:'24'" in metadata
for abi in ('arm64-v8a', 'armeabi-v7a', 'x86', 'x86_64'):
    assert f"'{abi}'" in metadata, f'Missing ABI: {abi}'
manifest = run('aapt', 'dump', 'xmltree', str(apk), 'AndroidManifest.xml')
for flag in ('debuggable', 'testOnly'):
    assert not re.search(flag + r'.*=.*0xffffffff', manifest), f'{flag} APK cannot be released'
alignment = run('zipalign', '-c', '-P', '16', '-v', '4', str(apk))
with zipfile.ZipFile(apk) as archive:
    assert archive.testzip() is None
    bundle = archive.read('assets/index.android.bundle')
    assert b'https://uniserve-api.onrender.com/api/v1' in bundle
    assert b'example.invalid' not in bundle
sha = hashlib.sha256(apk.read_bytes()).hexdigest()
(out/'signature.txt').write_text(signature)
(out/'metadata.txt').write_text(metadata)
(out/'manifest.txt').write_text(manifest)
(out/'alignment.txt').write_text(alignment)
(out/'SHA256SUMS.txt').write_text(sha+'  app-release.apk\n')
(out/'provenance.json').write_text(json.dumps({'source_commit':os.environ['GITHUB_SHA'],
    'run_id':os.environ['GITHUB_RUN_ID'],'version':config['version'],
    'versionCode':config['android']['versionCode'],'sha256':sha,
    'certificate_sha256':expected,'bytes':apk.stat().st_size},indent=2)+'\n')
print(signature)
print(metadata)
print('Final signed APK validated; SHA256:',sha)
