//! Isolated Google OAuth 2.0 proof-of-concept — LogiStream research mockup.
//!
//! ISOLATION IS THE POINT. This binary is a parallel workspace on port 8002. It
//! shares no code, no database, no process and no `.env` with the frozen demo
//! stack (web :3000, gateway :8000, orchestrator :8001, domain :8080, LiteLLM
//! :4000). Stopping or crashing it cannot affect them.
//!
//! Flow:
//!   GET /api/auth/login     -> mints a CSRF state, returns Google's consent URL
//!   GET /api/auth/callback  -> verifies state, swaps code for a token, returns
//!                              the OpenID Connect profile
//!
//! `oauth2` 5.x notes, because 4.x examples on the web will not compile here:
//!   * `BasicClient::new(id)` then `.set_client_secret(..).set_auth_uri(..)`
//!     `.set_token_uri(..).set_redirect_uri(..)` — a typed builder.
//!   * `request_async` takes `&impl AsyncHttpClient`, implemented for
//!     `reqwest::Client` **version 0.12**. Cargo.toml pins that deliberately.

use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};

use axum::{
    Json, Router,
    extract::{Query, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::get,
};
use oauth2::{
    AuthUrl, AuthorizationCode, ClientId, ClientSecret, CsrfToken, RedirectUrl, Scope,
    TokenResponse, TokenUrl, basic::BasicClient,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use tower_http::cors::{Any, CorsLayer};
use tracing::{info, warn};

// Google's well-known endpoints.
const GOOGLE_AUTH_URL: &str = "https://accounts.google.com/o/oauth2/v2/auth";
const GOOGLE_TOKEN_URL: &str = "https://oauth2.googleapis.com/token";
const GOOGLE_USERINFO_URL: &str = "https://openidconnect.googleapis.com/v1/userinfo";

/// How long a pending authorisation may sit before its state is rejected.
const STATE_TTL: Duration = Duration::from_secs(10 * 60);

// ---------------------------------------------------------------------- state

#[derive(Clone)]
struct AppState {
    client_id: String,
    client_secret: String,
    redirect_url: String,
    http: reqwest::Client,
    /// Issued CSRF states awaiting a callback. In-memory on purpose: this is a
    /// single-process mockup, and a real deployment would put this in a signed
    /// cookie or a session store.
    pending: Arc<Mutex<HashMap<String, Instant>>>,
}

/// Mint the OAuth client. Free function so the concrete generic stays inferred.
fn build_oauth_client(
    st: &AppState,
) -> Result<
    oauth2::Client<
        oauth2::basic::BasicErrorResponse,
        oauth2::basic::BasicTokenResponse,
        oauth2::basic::BasicTokenIntrospectionResponse,
        oauth2::StandardRevocableToken,
        oauth2::basic::BasicRevocationErrorResponse,
        oauth2::EndpointSet,
        oauth2::EndpointNotSet,
        oauth2::EndpointNotSet,
        oauth2::EndpointNotSet,
        oauth2::EndpointSet,
    >,
    AppError,
> {
    Ok(BasicClient::new(ClientId::new(st.client_id.clone()))
        .set_client_secret(ClientSecret::new(st.client_secret.clone()))
        .set_auth_uri(
            AuthUrl::new(GOOGLE_AUTH_URL.to_string())
                .map_err(|e| AppError::config(format!("bad auth url: {e}")))?,
        )
        .set_token_uri(
            TokenUrl::new(GOOGLE_TOKEN_URL.to_string())
                .map_err(|e| AppError::config(format!("bad token url: {e}")))?,
        )
        .set_redirect_uri(
            RedirectUrl::new(st.redirect_url.clone())
                .map_err(|e| AppError::config(format!("bad redirect url: {e}")))?,
        ))
}

// ---------------------------------------------------------------------- errors

struct AppError {
    status: StatusCode,
    message: String,
}

impl AppError {
    fn config(m: impl Into<String>) -> Self {
        Self { status: StatusCode::INTERNAL_SERVER_ERROR, message: m.into() }
    }
    fn bad_request(m: impl Into<String>) -> Self {
        Self { status: StatusCode::BAD_REQUEST, message: m.into() }
    }
    fn upstream(m: impl Into<String>) -> Self {
        Self { status: StatusCode::BAD_GATEWAY, message: m.into() }
    }
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        // The message is ours, never a raw upstream body, so this cannot leak a
        // token or the client secret.
        warn!(status = %self.status, "{}", self.message);
        (self.status, Json(json!({ "error": self.message }))).into_response()
    }
}

// -------------------------------------------------------------------- handlers

async fn health() -> impl IntoResponse {
    Json(json!({
        "ok": true,
        "service": "logistream-auth-mockup",
        "port": 8002,
        "note": "isolated OAuth PoC; not part of the LogiStream demo path"
    }))
}

#[derive(Serialize)]
struct LoginResponse {
    authorize_url: String,
    state: String,
    expires_in_seconds: u64,
}

/// `GET /api/auth/login`
///
/// Mints a fresh CSRF token, builds Google's consent URL for
/// `openid profile email`, and hands both back as JSON. The caller redirects
/// the browser to `authorize_url`.
async fn login(State(st): State<AppState>) -> Result<Json<LoginResponse>, AppError> {
    let client = build_oauth_client(&st)?;

    let (url, csrf) = client
        .authorize_url(CsrfToken::new_random)
        .add_scope(Scope::new("openid".to_string()))
        .add_scope(Scope::new("profile".to_string()))
        .add_scope(Scope::new("email".to_string()))
        .url();

    {
        let mut pending = st.pending.lock().expect("state mutex poisoned");
        // opportunistic sweep, so a long-running process does not grow forever
        pending.retain(|_, issued| issued.elapsed() < STATE_TTL);
        pending.insert(csrf.secret().clone(), Instant::now());
    }

    info!("issued authorization url (state {}…)", &csrf.secret()[..8.min(csrf.secret().len())]);

    Ok(Json(LoginResponse {
        authorize_url: url.to_string(),
        state: csrf.secret().clone(),
        expires_in_seconds: STATE_TTL.as_secs(),
    }))
}

#[derive(Deserialize)]
struct CallbackQuery {
    code: Option<String>,
    state: Option<String>,
    error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct GoogleProfile {
    sub: String,
    #[serde(default)]
    name: Option<String>,
    #[serde(default)]
    given_name: Option<String>,
    #[serde(default)]
    family_name: Option<String>,
    #[serde(default)]
    picture: Option<String>,
    #[serde(default)]
    email: Option<String>,
    #[serde(default)]
    email_verified: Option<bool>,
}

/// `GET /api/auth/callback`
///
/// Verifies the returned `state` against the ones we issued, exchanges the
/// authorization code for an access token, then fetches the OIDC profile.
///
/// The state check is not optional decoration: without it this endpoint would
/// accept a code obtained in someone else's browser, which is the textbook
/// OAuth CSRF (login-CSRF) attack. A paper describing this flow should show it
/// being done.
async fn callback(
    State(st): State<AppState>,
    Query(q): Query<CallbackQuery>,
) -> Result<Json<serde_json::Value>, AppError> {
    if let Some(err) = q.error {
        return Err(AppError::bad_request(format!(
            "google returned an error instead of a code: {err}"
        )));
    }

    let code = q.code.ok_or_else(|| AppError::bad_request("no ?code= in the callback"))?;
    let state = q.state.ok_or_else(|| AppError::bad_request("no ?state= in the callback"))?;

    // ---- CSRF: the state must be one WE issued, and must be single-use
    {
        let mut pending = st.pending.lock().expect("state mutex poisoned");
        match pending.remove(&state) {
            None => {
                return Err(AppError::bad_request(
                    "unknown or already-used state - possible CSRF, or the login expired",
                ));
            }
            Some(issued) if issued.elapsed() >= STATE_TTL => {
                return Err(AppError::bad_request("state expired; start the login again"));
            }
            Some(_) => {}
        }
    }

    // ---- exchange the code for a token
    let client = build_oauth_client(&st)?;
    let token = client
        .exchange_code(AuthorizationCode::new(code))
        .request_async(&st.http)
        .await
        .map_err(|e| AppError::upstream(format!("token exchange failed: {e}")))?;

    let access_token = token.access_token().secret();

    // ---- fetch the profile with the token we just obtained
    let profile: GoogleProfile = st
        .http
        .get(GOOGLE_USERINFO_URL)
        .bearer_auth(access_token)
        .send()
        .await
        .map_err(|e| AppError::upstream(format!("userinfo request failed: {e}")))?
        .error_for_status()
        .map_err(|e| AppError::upstream(format!("userinfo returned an error: {e}")))?
        .json()
        .await
        .map_err(|e| AppError::upstream(format!("userinfo was not the expected JSON: {e}")))?;

    // Never log the token or the email body; the subject id is enough to trace.
    info!("authenticated google subject {}", profile.sub);

    Ok(Json(json!({
        "authenticated": true,
        "profile": profile,
        "token": {
            // The token itself is deliberately NOT returned. A PoC that echoes
            // access tokens into a JSON response is one screenshot away from
            // leaking a live credential into a paper.
            "type": token.token_type().as_ref(),
            "scopes": token.scopes().map(|s| s.iter().map(|x| x.to_string()).collect::<Vec<_>>()),
            "expires_in_seconds": token.expires_in().map(|d| d.as_secs()),
            "access_token": "<redacted - see main.rs>"
        }
    })))
}

// ------------------------------------------------------------------------ main

fn env_required(key: &str) -> Result<String, String> {
    match std::env::var(key) {
        Ok(v) if !v.trim().is_empty() => Ok(v),
        _ => Err(format!("{key} is not set - copy .env.example to .env and fill it in")),
    }
}

#[tokio::main]
async fn main() {
    // Loads auth_mockup/.env only. The repo-root .env belongs to the demo stack
    // and is neither read nor written here.
    let _ = dotenvy::dotenv();

    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    let client_id = match env_required("GOOGLE_CLIENT_ID") {
        Ok(v) => v,
        Err(e) => {
            eprintln!("STOP: {e}");
            std::process::exit(2);
        }
    };
    let client_secret = match env_required("GOOGLE_CLIENT_SECRET") {
        Ok(v) => v,
        Err(e) => {
            eprintln!("STOP: {e}");
            std::process::exit(2);
        }
    };

    let port: u16 = std::env::var("AUTH_MOCKUP_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8002);

    let redirect_url = std::env::var("GOOGLE_REDIRECT_URL")
        .unwrap_or_else(|_| format!("http://localhost:{port}/api/auth/callback"));

    // redirect(none) is the oauth2 crate's own recommendation: following
    // redirects during a token exchange is an SSRF foot-gun.
    let http = reqwest::ClientBuilder::new()
        .redirect(reqwest::redirect::Policy::none())
        .timeout(Duration::from_secs(30))
        .build()
        .expect("failed to build the http client");

    let state = AppState {
        client_id,
        client_secret,
        redirect_url: redirect_url.clone(),
        http,
        pending: Arc::new(Mutex::new(HashMap::new())),
    };

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    // axum 0.8 path syntax is /{param}; the 0.7 /:param form panics at startup.
    let app = Router::new()
        .route("/health", get(health))
        .route("/api/auth/login", get(login))
        .route("/api/auth/callback", get(callback))
        .layer(cors)
        .with_state(state);

    let addr = format!("0.0.0.0:{port}");
    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .unwrap_or_else(|e| panic!("cannot bind {addr}: {e}"));

    info!("auth mockup listening on {addr}");
    info!("redirect uri (must match Google Cloud Console EXACTLY): {redirect_url}");

    axum::serve(listener, app)
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
            info!("shutting down");
        })
        .await
        .expect("server error");
}
