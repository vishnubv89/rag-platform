import { useState } from "react";
import { getConfig, saveConfig } from "../api/client";

const WIZARD_DONE_KEY = "rag_wizard_done";

type Provider = "gemini" | "anthropic" | "nvidia";

const PROVIDER_LABELS: Record<Provider, string> = {
  gemini:    "Gemini (Google)",
  anthropic: "Anthropic (Claude)",
  nvidia:    "NVIDIA NIM / OpenAI-compatible",
};

const PROVIDER_KEY_LABEL: Partial<Record<Provider, string>> = {
  anthropic: "Anthropic API Key",
  nvidia:    "API Key",
};

const PROVIDER_KEY_PLACEHOLDER: Partial<Record<Provider, string>> = {
  anthropic: "sk-ant-…",
  nvidia:    "nvapi-…",
};

const PROVIDER_KEY_FIELD: Partial<Record<Provider, string>> = {
  anthropic: "anthropic_api_key",
  nvidia:    "nvidia_api_key",
};

const DEFAULT_MODELS: Record<Provider, string> = {
  gemini:    "gemini-2.0-flash",
  anthropic: "claude-sonnet-4-6",
  nvidia:    "meta/llama-3.2-3b-instruct",
};

interface Props {
  orgId: number | null;
  onDone: () => void;
}

export function FirstRunWizard({ orgId, onDone }: Props) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [provider, setProvider] = useState<Provider>("gemini");
  const [model, setModel] = useState(DEFAULT_MODELS["gemini"]);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://integrate.api.nvidia.com/v1");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function handleProviderChange(p: Provider) {
    setProvider(p);
    setModel(DEFAULT_MODELS[p]);
    setApiKey("");
    setError("");
  }

  async function handleSave() {
    const keyField = PROVIDER_KEY_FIELD[provider];
    if (keyField && !apiKey.trim()) {
      setError("API key is required for this provider.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const settings: Record<string, string> = { llm_provider: provider };
      if (provider === "gemini")    settings.llm_model = model;
      if (provider === "anthropic") { settings.anthropic_model = model; settings.anthropic_api_key = apiKey; }
      if (provider === "nvidia")    { settings.nvidia_model = model; settings.nvidia_api_key = apiKey; settings.nvidia_base_url = baseUrl; }
      await saveConfig(orgId, settings);
      setStep(3);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function finish() {
    localStorage.setItem(WIZARD_DONE_KEY, "1");
    onDone();
  }

  return (
    <div
      className="fixed inset-0 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.45)", zIndex: 1000 }}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl flex flex-col"
        style={{ width: "100%", maxWidth: 480, maxHeight: "90vh", overflow: "hidden" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4" style={{ borderBottom: "1px solid #e8e8ea" }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: "#2563eb" }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
            </div>
            <span className="font-semibold text-gray-900">Setup wizard</span>
          </div>
          {/* Step indicators */}
          <div className="flex items-center gap-1.5">
            {([1, 2, 3] as const).map((s) => (
              <div
                key={s}
                className="rounded-full transition-all"
                style={{
                  width: step === s ? 20 : 8,
                  height: 8,
                  background: step >= s ? "#2563eb" : "#e5e7eb",
                }}
              />
            ))}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {step === 1 && (
            <div className="flex flex-col gap-4">
              <div>
                <h2 className="text-xl font-bold text-gray-900 mb-1">Welcome to RAG Platform</h2>
                <p className="text-sm text-gray-500">
                  Let's get your AI assistant up and running. This takes about 2 minutes.
                </p>
              </div>
              <div className="flex flex-col gap-3 mt-2">
                {[
                  { icon: "🤖", title: "Pick an LLM provider", desc: "Gemini, Anthropic, or any OpenAI-compatible API" },
                  { icon: "📚", title: "Connect your knowledge", desc: "Upload docs or connect ServiceNow, Confluence, and more" },
                  { icon: "💬", title: "Start chatting", desc: "Ask questions, get answers grounded in your data" },
                ].map((item) => (
                  <div key={item.title} className="flex items-start gap-3 p-3 rounded-xl" style={{ background: "#f8faff", border: "1px solid #e0eaff" }}>
                    <span className="text-xl">{item.icon}</span>
                    <div>
                      <div className="text-sm font-semibold text-gray-800">{item.title}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{item.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col gap-4">
              <div>
                <h2 className="text-xl font-bold text-gray-900 mb-1">Choose your LLM provider</h2>
                <p className="text-sm text-gray-500">This drives chat, grading, and document suggestions.</p>
              </div>

              {/* Provider tabs */}
              <div className="flex gap-2">
                {(["gemini", "anthropic", "nvidia"] as Provider[]).map((p) => (
                  <button
                    key={p}
                    onClick={() => handleProviderChange(p)}
                    className="flex-1 py-2 text-xs font-medium rounded-lg border transition-all"
                    style={{
                      background: provider === p ? "#2563eb" : "#f9fafb",
                      color: provider === p ? "white" : "#374151",
                      borderColor: provider === p ? "#2563eb" : "#e5e7eb",
                    }}
                  >
                    {p === "gemini" ? "Gemini" : p === "anthropic" ? "Anthropic" : "NVIDIA"}
                  </button>
                ))}
              </div>

              {/* Model field */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Model</label>
                <input
                  className="w-full text-sm px-3 py-2 rounded-lg border focus:outline-none focus:border-blue-500"
                  style={{ border: "1px solid #d1d5db" }}
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                />
                <p className="text-xs text-gray-400 mt-1">
                  {provider === "gemini" && "e.g. gemini-2.0-flash, gemini-1.5-pro, gemini-2.5-pro"}
                  {provider === "anthropic" && "e.g. claude-sonnet-4-6, claude-opus-4-7, claude-haiku-4-5-20251001"}
                  {provider === "nvidia" && "e.g. meta/llama-3.2-3b-instruct, meta/llama-3.1-405b-instruct"}
                </p>
              </div>

              {/* API key field (not Gemini) */}
              {PROVIDER_KEY_FIELD[provider] && (
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    {PROVIDER_KEY_LABEL[provider]}
                  </label>
                  <input
                    type="password"
                    className="w-full text-sm px-3 py-2 rounded-lg border focus:outline-none focus:border-blue-500 font-mono"
                    style={{ border: "1px solid #d1d5db" }}
                    placeholder={PROVIDER_KEY_PLACEHOLDER[provider]}
                    value={apiKey}
                    onChange={(e) => { setApiKey(e.target.value); setError(""); }}
                    autoComplete="new-password"
                  />
                </div>
              )}

              {/* NVIDIA base URL */}
              {provider === "nvidia" && (
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">API Base URL</label>
                  <input
                    className="w-full text-sm px-3 py-2 rounded-lg border focus:outline-none focus:border-blue-500 font-mono"
                    style={{ border: "1px solid #d1d5db" }}
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                  />
                  <p className="text-xs text-gray-400 mt-1">Works with OpenAI, Groq, Together AI, Ollama, and any OpenAI-compatible endpoint.</p>
                </div>
              )}

              {provider === "gemini" && (
                <div className="text-xs text-gray-500 p-3 rounded-lg" style={{ background: "#f0fdf4", border: "1px solid #bbf7d0" }}>
                  Gemini uses the <code className="font-mono text-xs">GOOGLE_API_KEY</code> environment variable set on your server — no key needed here.
                </div>
              )}

              {error && <p className="text-xs text-red-600">{error}</p>}
            </div>
          )}

          {step === 3 && (
            <div className="flex flex-col items-center gap-4 py-4 text-center">
              <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ background: "#f0fdf4" }}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900 mb-1">You're all set!</h2>
                <p className="text-sm text-gray-500">
                  {PROVIDER_LABELS[provider]} is configured. Head to Chat to ask your first question, or visit Knowledge Hub to upload documents.
                </p>
              </div>
              <div className="text-xs text-gray-400 p-3 rounded-lg w-full text-left" style={{ background: "#f8f9fa", border: "1px solid #e9ecef" }}>
                <span className="font-semibold text-gray-600">Tip:</span> Connect a data source like ServiceNow or Confluence in the Admin UI to ground answers in your team's knowledge.
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4" style={{ borderTop: "1px solid #e8e8ea" }}>
          {step === 1 && (
            <>
              <button
                onClick={finish}
                className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                Skip setup
              </button>
              <button
                onClick={() => setStep(2)}
                className="text-sm font-medium px-5 py-2 rounded-lg text-white transition-colors"
                style={{ background: "#2563eb" }}
              >
                Get started →
              </button>
            </>
          )}
          {step === 2 && (
            <>
              <button
                onClick={() => setStep(1)}
                className="text-xs text-gray-500 hover:text-gray-700 transition-colors"
              >
                ← Back
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="text-sm font-medium px-5 py-2 rounded-lg text-white transition-colors disabled:opacity-60"
                style={{ background: "#2563eb" }}
              >
                {saving ? "Saving…" : "Save & continue →"}
              </button>
            </>
          )}
          {step === 3 && (
            <button
              onClick={finish}
              className="ml-auto text-sm font-medium px-5 py-2 rounded-lg text-white"
              style={{ background: "#2563eb" }}
            >
              Start chatting →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function needsWizard(config: Record<string, string>, role: string): boolean {
  if (role !== "superadmin") return false;
  if (localStorage.getItem(WIZARD_DONE_KEY)) return false;
  const provider = config.llm_provider;
  if (!provider) return true;
  if (provider === "anthropic" && !config.anthropic_api_key) return true;
  if (provider === "nvidia" && !config.nvidia_api_key) return true;
  return false;
}

export function useWizardCheck(orgId: number | null, role: string) {
  const [show, setShow] = useState(false);
  const [checked, setChecked] = useState(false);

  async function check() {
    if (role !== "superadmin" || localStorage.getItem(WIZARD_DONE_KEY)) {
      setChecked(true);
      return;
    }
    try {
      const cfg = await getConfig(orgId);
      setShow(needsWizard(cfg, role));
    } catch {
      // If config fetch fails, don't block the app
    } finally {
      setChecked(true);
    }
  }

  return { show, setShow, checked, check };
}
