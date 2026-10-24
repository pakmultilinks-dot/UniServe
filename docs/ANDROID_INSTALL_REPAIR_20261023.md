# Android installation repair — started October 23, updated October 24, 2026

## Source and scope

Base: latest fetched `origin/main`, `5365f93fb017a60da49971a821458acb06933820` (PR #10 included). Repair branch: `fix/android-install-repair-20261023`. No automatic merge. Original checkout changes and database data are preserved. No UI redesign or payment-provider invocation.

## Installation diagnosis: what is actually proven

Diagnostic run: https://github.com/pakmultilinks-dot/UniServe/actions/runs/39912236783

The exact published `UniServe-main-76dedbe.apk` passed ZIP integrity, `apksigner verify`, 16 KB ZIP alignment, and **actual `adb install` on Android 15 / API 35 x86_64**. The published 0.1.7 candidate successfully installed over it with `adb install -r`.

Both have package `com.uniserve.mobile`, minSdk 24 (Android 7), targetSdk 36, and native libraries for arm64-v8a, armeabi-v7a, x86 and x86_64. Old version is 0.1.6/code 7; current prior candidate is 0.1.7/code 8. The manifests do not set debuggable or testOnly true. Both have the same valid v2 signing certificate:

`fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c`

Its subject is `CN=Android Debug`. This shared debug identity is a **confirmed release-signing weakness, not a proven explanation of the Samsung rejection**. The exact cause on that phone remains unknown without an installation error code/device evidence. Successful emulator installation must not be presented as reproducing or fixing an unknown Samsung-specific condition.

## Repair

The fresh corrected candidate is 0.1.9 / code 10 and retains UniServe's package and UI. The final APK is explicitly re-signed using a private persistent PKCS12 release identity, with v1/v2/v3 enabled. Private key material and passwords are only in protected local backup and encrypted GitHub Actions secrets, never source/artifacts/logs. The public certificate fingerprint is pinned in `docs/android-release-certificate.sha256`:

`f6991eea10fb24d0a5676207a150432f6e6d2bc5f5c653b9410dffe7ce7dbadf`

`sign_verify_android.py` fails on wrong certificate, package/version, missing ABI, testOnly/debuggable flags, invalid signature/alignment/archive, or missing production API URL. Public evidence includes certificate, metadata, manifest, alignment, checksum and exact build source/run provenance. The candidate APK is an Actions artifact; **a completed compile alone does not certify installation or ordering**. The dependent Android job must pass actual installation, startup, native student ordering and live staff-browser actions.

Signing changes mean a one-time migration from the old debug-signed APK requires uninstalling that old app first. Future private-signed builds must retain the same private identity; never regenerate the signing key per build. Uninstalling clears local app data, while account/order data remains on the backend.

## Verified mobile status defect

The 0.1.8 candidate passed actual installation and full ordering/cancellation/manager checks, but visual review caught a remaining defect: a **confirmed, rejected-before-preparation** scheduled order showed Preparing. Confirmation preserves Pending on the server; it does not prove preparation started. The screen now uses `preparation_started_at` and `ready_at` to retain only stages actually reached on cancellation. Four rendered regressions cover confirmed-only rejection, real preparation, reached readiness and ordinary completion. No styles, branding, navigation or business rules changed. A fresh 0.1.9/code 10 binary is required; the earlier 0.1.8 candidate is superseded for final handover.

## Samsung installation and diagnostic instructions

1. Download the new verified candidate, extract the APK if downloading an Actions artifact ZIP, and compare `Get-FileHash .\app-release.apk -Algorithm SHA256` with that exact build's checksum. Do not rename an old APK as the new version.
2. Remove the earlier debug-signed UniServe app before switching to the private-signed candidate. Check whether UniServe is separately installed in Secure Folder or a work profile; do not delete profiles or unrelated data.
3. Open the new APK and grant installation permission to the browser/file manager if Android requests it. Launch UniServe and use authorized test accounts. Test cash checkout only, then staff status changes, ready notification and collection.
4. If installation still fails, connect an authorized device with USB debugging and record the actual installer result:

```powershell
adb devices
adb shell getprop ro.build.version.sdk
adb shell getprop ro.product.cpu.abilist
adb shell pm list users
adb install .\app-release.apk
```

For a specific known profile, inspect without changing it:

```powershell
adb shell pm list packages --user <profile-id> com.uniserve.mobile
```

`INSTALL_FAILED_UPDATE_INCOMPATIBLE` points to an existing package with a different signing identity; `INSTALL_FAILED_VERSION_DOWNGRADE` is a version conflict; `INSTALL_FAILED_OLDER_SDK` or `INSTALL_FAILED_NO_MATCHING_ABIS` identifies device compatibility. Do not infer any of these solely from the generic Samsung dialog. Do not bypass signature checks or randomly lower SDK levels.

## Review and final release

PR: https://github.com/pakmultilinks-dot/UniServe/pull/12

Do not merge automatically. Once reviewed and merged, run **Build Android APK on the merged main commit**, require full CI plus installation/live-flow jobs to pass, and publish that exact verified artifact with its source SHA, certificate fingerprint and checksum under a new tag. Never overwrite older assets or label this branch candidate as a merged-main release. Physical Samsung verification remains separate from emulator verification.

## Optional future UX work — not implemented

Foodpanda's public [ordering explanation](https://www.foodpanda.pk/contents/how-it-works) was consulted only for general browse → cart → checkout → confirmation ideas. Future changes could improve semantic labels on native quantity controls and make loading/retry wording more consistent, subject to approval. No branding, layouts, delivery/rider/maps/payment features were copied. The nine reference images were not attached to this request's available files; no visual redesign was inferred from them.
