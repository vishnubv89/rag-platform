/**
 * Zitadel OIDC client — PKCE Authorization Code flow.
 *
 * The UserManager is initialised once per page load.  All redirect URIs must
 * exactly match what is registered in the Zitadel application settings.
 */
import { UserManager, WebStorageStateStore, type User } from "oidc-client-ts";

const AUTHORITY  = import.meta.env.VITE_ZITADEL_AUTHORITY  ?? "http://localhost:8088";
const CLIENT_ID  = import.meta.env.VITE_ZITADEL_CLIENT_ID  ?? "";
const REDIRECT_URI = `${window.location.origin}/callback`;

export const zitadelManager = new UserManager({
  authority:                  AUTHORITY,
  client_id:                  CLIENT_ID,
  redirect_uri:               REDIRECT_URI,
  post_logout_redirect_uri:   window.location.origin,
  scope:                      "openid profile email",
  response_type:              "code",
  // Store OIDC state in sessionStorage so it survives the redirect but is
  // cleared when the tab closes (safer than localStorage for tokens).
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  // Zitadel issues tokens with the client_id as audience — skip aud check
  // here; the backend validates audience against its own client_id.
  filterProtocolClaims: true,
  loadUserInfo: true,
});

/** Kick off the PKCE login redirect to Zitadel. */
export function loginWithZitadel(): Promise<void> {
  return zitadelManager.signinRedirect();
}

/**
 * Complete the PKCE callback after Zitadel redirects back.
 * Call this only when window.location.pathname === "/callback".
 */
export function handleZitadelCallback(): Promise<User> {
  return zitadelManager.signinRedirectCallback();
}

/** Sign the user out of Zitadel and redirect back to the app root. */
export function logoutZitadel(): Promise<void> {
  return zitadelManager.signoutRedirect();
}
