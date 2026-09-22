# Isolated Google OAuth 2.0 mockup

A standalone research proof-of-concept on **port 8002**. It is deliberately not
wired into LogiStream: separate crate, separate process, separate `.env`,
separate port. Starting, stopping or crashing it cannot affect the demo stack.

| | Demo stack (frozen) | This mockup |
|---|---|---|
| Ports | 3000, 8000, 8001, 8080, 4000, 5432 | **8002** |
| Secrets | repo-root `.env` | `auth_mockup/.env` |
| Started by | `bash demo/start.sh` | `bash auth_mockup/run.sh` |
| Shares code with the demo | — | **nothing** |

---

## One-time setup

### 1. Create the Google credentials

<https://console.cloud.google.com/apis/credentials> →
**Create Credentials → OAuth client ID → Web application**.

Add this as an **Authorised redirect URI**, exactly:

```
http://localhost:8002/api/auth/callback
```

Google string-matches this. A trailing slash, `127.0.0.1` instead of
`localhost`, or `https` will all fail with `redirect_uri_mismatch`.

While the app is in *Testing*, add your own Google account under
**OAuth consent screen → Test users**, or sign-in returns `access_denied`.

### 2. Fill in the env file

```bash
cp auth_mockup/.env.example auth_mockup/.env
```

Then edit `auth_mockup/.env` and paste the client ID and secret. The file is
gitignored. **Do not put these in the repo-root `.env`** — that one belongs to
the demo stack.

---

## Running it

```bash
bash auth_mockup/run.sh
```

Or by hand:

```bash
cd auth_mockup
source ../scripts/env.sh     # puts the MinGW linker on PATH (see below)
cargo run --release
```

It refuses to start with a clear message if the credentials are missing, rather
than failing later at the token exchange.

## Trying the flow

```bash
# 1. get the consent URL
curl -s http://localhost:8002/api/auth/login | python -m json.tool
```

```json
{
  "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&scope=openid+profile+email&state=...",
  "state": "AQYdNrq--B7t...",
  "expires_in_seconds": 600
}
```

2. Open `authorize_url` in a browser and approve.
3. Google redirects to `/api/auth/callback`, which verifies the state, exchanges
   the code and returns the profile:

```json
{
  "authenticated": true,
  "profile": { "sub": "1030...", "name": "...", "email": "...", "email_verified": true },
  "token": { "type": "Bearer", "scopes": [...], "expires_in_seconds": 3599,
             "access_token": "<redacted - see main.rs>" }
}
```

---

## Design notes for the paper

**The `state` parameter is verified, not just generated.** `/login` mints a
random `CsrfToken`, stores it with a 10-minute TTL, and `/callback` requires a
state it issued. The entry is removed on use, so a replayed callback is
rejected. Skipping this is the textbook OAuth login-CSRF hole, and a PoC that
describes the flow should show the check rather than imply it.

Verified locally without contacting Google:

```
callback with no params            -> 400
callback with code but no state    -> 400
callback with a forged state       -> 400  "unknown or already-used state..."
replay of a valid state            -> 400  (single-use enforced)
```

**The access token is not returned.** `/callback` reports the token type,
scopes and lifetime but redacts the token itself. A PoC that echoes live
credentials into a JSON body is one screenshot away from leaking one into a
paper.

**Redirects are disabled on the HTTP client** (`redirect::Policy::none()`),
which is the `oauth2` crate's own recommendation — following redirects during a
token exchange is an SSRF foot-gun.

**State lives in memory.** Fine for a single-process PoC; a real deployment
would use a signed cookie or a shared session store, and would need it anyway to
survive more than one instance.

---

## Two things that will waste your afternoon otherwise

**`oauth2` 5.x is not `oauth2` 4.x.** Most examples online are 4.x and will not
compile. 5.x uses a typed builder (`BasicClient::new(id).set_client_secret(..)
.set_auth_uri(..).set_token_uri(..)`) and `request_async` takes an
`&impl AsyncHttpClient`.

**`reqwest` is pinned to 0.12 on purpose.** `oauth2` 5.0 depends on
`reqwest ^0.12` and its `AsyncHttpClient` impl is for *that* version's `Client`.
Asking for `reqwest = "0.13"` compiles two copies and the client no longer
satisfies the trait — which surfaces as an inscrutable "trait bound not
satisfied", not a version error.

**Linker.** This machine has no MSVC C++ toolset, so `rust-toolchain.toml` pins
the GNU target exactly as `/gateway` does, and `scripts/env.sh` puts the
portable MinGW-w64 in `tools/` on PATH (it supplies the assembler `dlltool`
needs). `run.sh` sources it for you. See PROGRESS.md, "three layers of Windows
linker trouble".
