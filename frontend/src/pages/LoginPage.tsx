import { useState, type FormEvent } from "react";
import { useAuthStore } from "../store/authStore";
import { loginWithZitadel } from "../auth/zitadelClient";

const API = "";

async function fetchMe(token: string) {
  const r = await fetch(`${API}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error("failed");
  return r.json();
}

export function LoginPage() {
  const { setAuth } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"login" | "setup">("login");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint = mode === "setup" ? "/auth/setup" : "/auth/login";
      const body: Record<string, string> = { email, password };
      if (mode === "setup") body.name = email.split("@")[0];

      const r = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) {
        if (r.status === 409 && mode === "setup") {
          setMode("login");
          setError("Setup already done — please log in.");
        } else {
          setError(data.detail ?? "Something went wrong");
        }
        return;
      }
      const token = data.access_token;
      const user = await fetchMe(token);
      setAuth(user, token);
    } catch {
      setError("Could not reach the server");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="flex items-center justify-center min-h-screen"
      style={{ background: "#f7f7f8" }}
    >
      <div
        className="w-full max-w-sm rounded-2xl p-8"
        style={{ background: "#ffffff", border: "1px solid #e8e8ea" }}
      >
        {/* Brand */}
        <div className="flex items-center gap-2.5 mb-8">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center"
            style={{ background: "#2563eb" }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
          <div>
            <div className="font-semibold text-gray-900 text-sm tracking-tight">Knowledge Mesh</div>
            <div className="text-xs" style={{ color: "#9ca3af" }}>Agentic RAG</div>
          </div>
        </div>

        <h1 className="text-base font-semibold text-gray-900 mb-1">
          {mode === "setup" ? "Create your account" : "Sign in"}
        </h1>
        <p className="text-xs text-gray-400 mb-6">
          {mode === "setup"
            ? "Set up the first admin account"
            : "Enter your credentials to continue"}
        </p>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full text-sm px-3 py-2.5 rounded-lg border focus:outline-none"
              style={{ border: "1px solid #e8e8ea", background: "#f7f7f8" }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "#2563eb"; e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37,99,235,.08)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "#e8e8ea"; e.currentTarget.style.boxShadow = "none"; }}
              placeholder="you@company.com"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full text-sm px-3 py-2.5 rounded-lg border focus:outline-none"
              style={{ border: "1px solid #e8e8ea", background: "#f7f7f8" }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "#2563eb"; e.currentTarget.style.boxShadow = "0 0 0 3px rgba(37,99,235,.08)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "#e8e8ea"; e.currentTarget.style.boxShadow = "none"; }}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="text-xs px-3 py-2 rounded-lg" style={{ background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca" }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-sm font-medium text-white transition-opacity"
            style={{ background: "#2563eb", opacity: loading ? 0.7 : 1 }}
          >
            {loading ? "Please wait…" : mode === "setup" ? "Create account" : "Sign in"}
          </button>
        </form>

        {/* SSO divider — only shown when Zitadel is configured */}
        {import.meta.env.VITE_ZITADEL_CLIENT_ID && (
          <>
            <div className="mt-5 flex items-center gap-3">
              <div className="flex-1 h-px" style={{ background: "#e8e8ea" }} />
              <span className="text-xs text-gray-400">or</span>
              <div className="flex-1 h-px" style={{ background: "#e8e8ea" }} />
            </div>
            <button
              type="button"
              onClick={() => loginWithZitadel()}
              className="mt-3 w-full py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
              style={{ background: "#f7f7f8", color: "#374151", border: "1px solid #e8e8ea" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#e5e7eb"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#f7f7f8"; }}
            >
              {/* Zitadel shield icon */}
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              Sign in with SSO
            </button>
          </>
        )}

        <div className="mt-5 text-center">
          {mode === "login" ? (
            <button
              onClick={() => { setMode("setup"); setError(""); }}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              First time? Set up your account →
            </button>
          ) : (
            <button
              onClick={() => { setMode("login"); setError(""); }}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              Already have an account? Sign in
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
