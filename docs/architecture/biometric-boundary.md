# UniServe — Biometric Authentication Boundary

## Design Principle

**UniServe never receives, processes, stores, or transmits biometric data.**

Biometric authentication is a **client-side convenience** that unlocks access to
existing application credentials. The backend has no awareness of how the client
authenticated locally — it only sees the resulting session tokens.

---

## Architecture Boundary

```
┌──────────────────────────────────────────────────────────┐
│                     Mobile Device                         │
│                                                          │
│  ┌─────────────┐    ┌─────────────────────────────────┐  │
│  │  Native OS  │    │  UniServe Mobile App            │  │
│  │  Biometric  │◄──►│  (React Native + Expo)          │  │
│  │  API        │    │                                 │  │
│  │             │    │  ┌───────────────────────────┐  │  │
│  │  • iOS Face │    │  │  Secure Storage           │  │  │
│  │    ID /     │    │  │  (Expo SecureStore /      │  │  │
│  │    Touch ID │    │  │   Keychain)               │  │  │
│  │  • Android  │    │  │                           │  │  │
│  │    Biometric│    │  │  • refresh_token          │  │  │
│  │    Prompt   │    │  │  • user_id (for PIN)      │  │  │
│  └─────────────┘    │  └───────────────────────────┘  │  │
│                     └──────────────┬──────────────────┘  │
│                                    │                      │
│                     ┌──────────────▼──────────────────┐  │
│                     │  HTTP Header                    │  │
│                     │  Authorization: Bearer <token>  │  │
│                     └──────────────┬──────────────────┘  │
└────────────────────────────────────┼─────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────┐
│                   UniServe Backend                      │
│                                                        │
│  Receives: Bearer token (JWT)                          │
│  Validates: JWT signature, expiry, session status      │
│  Does NOT know: how the client obtained/unlocked it    │
│                                                        │
│  The backend treats biometric login identically to     │
│  any other authenticated request — a valid session.    │
└────────────────────────────────────────────────────────┘
```

---

## How Biometric Login Works (Client-Side Only)

### Flow

1. **First login**: User authenticates with email/password → backend issues
   access token + refresh token → app stores refresh token in secure storage.

2. **Biometric enrollment**: App optionally marks the stored credential as
   "protected by biometrics" in secure storage. This is a local-only flag.

3. **Subsequent logins**: App invokes the OS biometric API (Face ID, Touch ID,
   fingerprint). On success, the OS releases the stored refresh token from
   secure storage. The app then calls `/api/v1/auth/refresh` with that token
   to obtain a fresh access token.

4. **Backend interaction**: The refresh endpoint is a standard token refresh —
   identical to any other refresh flow. The backend never sees biometric data.

### Native APIs Used (Mobile Implementation Phase)

| Platform | API | Purpose |
|----------|-----|---------|
| iOS | `expo-local-authentication` (Face ID / Touch ID) | Gate access to secure storage |
| Android | `expo-local-authentication` (BiometricPrompt) | Gate access to secure storage |
| Secure Storage | `expo-secure-store` (Keychain / EncryptedSharedPreferences) | Store refresh token at rest |

These are **device-level** capabilities. The UniServe backend has no code for
biometric verification — and never will.

---

## Backend Responsibilities

| Responsibility | Owner | Notes |
|----------------|-------|-------|
| Biometric data capture | **Device OS** | Never touches UniServe backend |
| Biometric template storage | **Device OS secure enclave** | Hardware-backed; app never sees it |
| Biometric match verification | **Device OS** | Returns success/failure to app |
| Secure credential storage | **Device secure storage** | Keychain (iOS) / EncryptedSharedPrefs (Android) |
| Session lifecycle (create, validate, revoke) | **UniServe backend** | Standard JWT + session management |
| Biometric login revocation | **Client-side** (delete stored credential) + **Backend** (revoke session if desired) | User can revoke per-device from session management |

---

## Revocation Model

Biometric login is revocable at two levels:

1. **Per-device**: User can revoke a specific session via `POST /api/v1/auth/logout`
   or the session management UI. The stored refresh token becomes invalid.

2. **All devices**: User can call `POST /api/v1/auth/logout-all` to revoke every
   session. All stored refresh tokens become invalid — biometric login on all
   devices stops working until a fresh email/password login is performed.

3. **Disabling biometric login**: The user (or an admin) deletes the stored
   credential from the device. This is a client-side operation — no backend
   API call is needed. The user's email/password authentication is unaffected.

---

## Security Properties

| Property | Guarantee |
|----------|-----------|
| No biometric data on server | ✅ Backend never receives biometric data |
| No biometric templates stored by app | ✅ Only OS stores templates in secure enclave |
| Biometric verification is device-local | ✅ OS handles match; app receives boolean result |
| Backend sees only session tokens | ✅ Standard JWT validation, identical to password login |
| Biometric login is revocable | ✅ Per-device logout or logout-all invalidates session |
| Disabling biometric does not affect password login | ✅ These are independent client-side mechanisms |
| Server-side brute-force protection applies | ✅ PIN lockout and account lockout apply to PIN-based flows |

---

## What UniServe Does NOT Do

- ❌ Receive fingerprint or face images
- ❌ Store biometric templates
- ❌ Perform biometric matching on the server
- ❌ Provide a "biometric login" API endpoint (there is no `/auth/biometric/login`)
- ❌ Distinguish between biometric-initiated and password-initiated sessions at the API level
- ❌ Implement platform-specific biometric SDKs in the backend

---

## Future Mobile Implementation Notes

When implementing biometric login in the React Native/Expo mobile app:

1. Use `expo-local-authentication` for biometric prompt.
2. Use `expo-secure-store` (backed by iOS Keychain / Android EncryptedSharedPrefs)
   to store the refresh token.
3. Gate secure store access behind biometric authentication:
   ```
   LocalAuthentication.authenticateAsync() →
     if success → SecureStore.getItemAsync('refresh_token') →
       call /api/v1/auth/refresh with refresh_token →
         store new access token in memory
   ```
4. On first login, store the refresh token in secure storage.
5. On logout, clear secure storage and revoke the session server-side.
6. The backend API remains completely unchanged — no new endpoints needed.
