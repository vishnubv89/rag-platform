/**
 * Knowledge Mesh embeddable chat widget.
 *
 * Drop-in usage:
 *   <script src="https://your-domain/widget/chat-widget.js"
 *     data-token="km_..."
 *     data-org="42"
 *     data-title="Ask AI"
 *     data-position="bottom-right"
 *   ></script>
 *
 * The widget:
 *  - Attaches a Shadow DOM to isolate styles from the host page
 *  - Streams responses from /chat/stream using X-Embed-Token auth
 *  - Maintains a session ID per page load
 *  - Never depends on the host page's CSS or JS
 */

(function () {
  const script =
    (document.currentScript as HTMLScriptElement | null) ||
    document.querySelector<HTMLScriptElement>(`script[data-token]`);
  if (!script) return;

  const apiUrl = new URL(script.src).origin;
  const cfg = {
    token: script.getAttribute("data-token") || "",
    orgId: parseInt(script.getAttribute("data-org") || "0", 10),
    // title/position/accentColor/welcomeMessage below are overridden by the
    // org's server-side chatbot config (fetched via /widget/config) once it
    // resolves — these attribute values only apply before that resolves,
    // or as a fallback if the fetch fails.
    title: script.getAttribute("data-title") || "Ask AI",
    position: script.getAttribute("data-position") || "bottom-right",
    accentColor: script.getAttribute("data-accent-color") || "#D85A30",
    welcomeMessage: script.getAttribute("data-welcome") || "Ask me anything about your knowledge base",
    context: script.getAttribute("data-context") || "",
    apiUrl,
  };

  if (!cfg.token) {
    console.warn("[rag-widget] data-token is required");
    return;
  }

  const sessionId = Math.random().toString(36).slice(2);
  const history: { role: string; content: string }[] = [];

  // ── Server-driven appearance (per-chatbot, set in Admin UI) ───────────────

  fetch(`${cfg.apiUrl}/widget/config`, { headers: { "X-Embed-Token": cfg.token } })
    .then((r) => (r.ok ? r.json() : null))
    .then((remote) => {
      if (!remote) return;
      if (remote.chatbot_name) cfg.title = remote.chatbot_name;
      if (remote.accent_color) cfg.accentColor = remote.accent_color;
      if (remote.position) cfg.position = remote.position;
      if (remote.welcome_message) cfg.welcomeMessage = remote.welcome_message;
      applyAppearance();
    })
    .catch(() => {
      // Fall back silently to data-* attributes / defaults already set above.
    });

  // ── CSS ──────────────────────────────────────────────────────────────────

  const css = `
    :host {
      all: initial;
      font-family: system-ui, sans-serif;
      --accent: ${cfg.accentColor};
    }

    .bubble, .panel { right: 24px; left: auto; }
    .bubble.pos-left, .panel.pos-left { left: 24px; right: auto; }

    .bubble {
      position: fixed;
      bottom: 24px;
      width: 52px; height: 52px;
      border-radius: 50%;
      background: var(--accent);
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 14px rgba(0,0,0,.25);
      display: flex; align-items: center; justify-content: center;
      transition: transform .15s, box-shadow .15s, filter .15s;
      z-index: 2147483647;
    }
    .bubble:hover { transform: scale(1.08); filter: brightness(0.92); }
    .bubble svg { width: 24px; height: 24px; fill: white; }

    .panel {
      position: fixed;
      bottom: 88px;
      width: 360px; max-width: calc(100vw - 48px);
      height: 520px; max-height: calc(100vh - 120px);
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,.18);
      display: flex; flex-direction: column;
      overflow: hidden;
      z-index: 2147483646;
      transition: opacity .18s, transform .18s;
    }
    .panel.hidden { opacity: 0; pointer-events: none; transform: translateY(12px); }

    .panel-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 14px 16px;
      background: var(--accent);
      color: white;
      flex-shrink: 0;
    }
    .panel-header .title { font-size: 14px; font-weight: 600; letter-spacing: .01em; }
    .panel-header .close {
      background: none; border: none; cursor: pointer;
      color: rgba(255,255,255,.75); font-size: 20px; line-height: 1;
      padding: 0 2px;
    }
    .panel-header .close:hover { color: white; }

    .messages {
      flex: 1; overflow-y: auto; padding: 14px;
      display: flex; flex-direction: column; gap: 10px;
      background: #f8faff;
    }
    .messages::-webkit-scrollbar { width: 4px; }
    .messages::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 4px; }

    .msg {
      max-width: 84%;
      padding: 9px 13px;
      border-radius: 14px;
      font-size: 13px; line-height: 1.5;
      word-break: break-word;
    }
    .msg.user {
      align-self: flex-end;
      background: var(--accent); color: white;
      border-bottom-right-radius: 4px;
    }
    .msg.assistant {
      align-self: flex-start;
      background: white; color: #1f2937;
      border: 1px solid #e5e7eb;
      border-bottom-left-radius: 4px;
    }
    .msg.typing { color: #9ca3af; font-style: italic; }

    .empty-state {
      flex: 1; display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      color: #9ca3af; font-size: 13px; gap: 8px;
      padding: 24px;
      text-align: center;
    }
    .empty-state svg { width: 36px; height: 36px; opacity: .35; }

    .input-row {
      display: flex; gap: 8px;
      padding: 12px;
      border-top: 1px solid #f0f0f0;
      background: white;
      flex-shrink: 0;
    }
    .input-row input {
      flex: 1;
      padding: 9px 13px;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      font-size: 13px;
      outline: none;
      transition: border-color .15s;
    }
    .input-row input:focus { border-color: var(--accent); }
    .input-row input::placeholder { color: #9ca3af; }

    .input-row button {
      padding: 9px 16px;
      background: var(--accent); color: white;
      border: none; border-radius: 10px;
      font-size: 13px; font-weight: 500;
      cursor: pointer;
      transition: filter .15s;
      flex-shrink: 0;
    }
    .input-row button:hover { filter: brightness(0.88); }
    .input-row button:disabled { filter: grayscale(0.4) brightness(1.3); cursor: default; }

    .powered-by {
      text-align: center;
      font-size: 10px;
      color: #d1d5db;
      padding: 4px 0 8px;
      background: white;
      flex-shrink: 0;
    }
  `;

  // ── DOM ───────────────────────────────────────────────────────────────────

  const host = document.createElement("div");
  host.setAttribute("id", "rag-chat-widget");
  document.body.appendChild(host);

  const shadow = host.attachShadow({ mode: "open" });

  const styleEl = document.createElement("style");
  styleEl.textContent = css;
  shadow.appendChild(styleEl);

  const posClass = cfg.position.includes("left") ? " pos-left" : "";

  const bubble = document.createElement("button");
  bubble.className = "bubble" + posClass;
  bubble.setAttribute("aria-label", "Open chat");
  bubble.innerHTML = `
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
    </svg>`;
  shadow.appendChild(bubble);

  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const panel = document.createElement("div");
  panel.className = "panel hidden" + posClass;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", cfg.title);
  panel.innerHTML = `
    <div class="panel-header">
      <span class="title" id="widget-title">${esc(cfg.title)}</span>
      <button class="close" aria-label="Close chat">×</button>
    </div>
    <div class="messages" id="msg-list">
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863
                   9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574
                   3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span id="widget-welcome">${esc(cfg.welcomeMessage)}</span>
      </div>
    </div>
    <div class="input-row">
      <input type="text" id="chat-input" placeholder="Ask a question…" autocomplete="off" />
      <button id="send-btn">Send</button>
    </div>
    <div class="powered-by">Powered by Knowledge Mesh</div>
  `;
  shadow.appendChild(panel);

  const msgList = shadow.getElementById("msg-list")!;
  const input = shadow.getElementById("chat-input") as HTMLInputElement;
  const sendBtn = shadow.getElementById("send-btn") as HTMLButtonElement;

  function applyAppearance() {
    styleEl.textContent = css.replace(
      /--accent:\s*[^;]+;/,
      `--accent: ${cfg.accentColor};`
    );
    const left = cfg.position.includes("left");
    bubble.classList.toggle("pos-left", left);
    panel.classList.toggle("pos-left", left);
    panel.setAttribute("aria-label", cfg.title);
    const titleEl = shadow.getElementById("widget-title");
    if (titleEl) titleEl.textContent = cfg.title;
    const welcomeEl = shadow.getElementById("widget-welcome");
    if (welcomeEl && firstMessage) welcomeEl.textContent = cfg.welcomeMessage;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  let busy = false;
  let firstMessage = true;

  function addMsg(role: string, text: string): HTMLDivElement {
    if (firstMessage) {
      msgList.innerHTML = "";
      firstMessage = false;
    }
    const el = document.createElement("div");
    el.className = `msg ${role}`;
    el.textContent = text;
    msgList.appendChild(el);
    msgList.scrollTop = msgList.scrollHeight;
    return el;
  }

  function setDisabled(v: boolean) {
    busy = v;
    sendBtn.disabled = v;
    input.disabled = v;
  }

  // ── Send ──────────────────────────────────────────────────────────────────

  async function send() {
    const message = input.value.trim();
    if (!message || busy) return;
    input.value = "";

    addMsg("user", message);
    history.push({ role: "user", content: message });

    const typing = addMsg("assistant", "▌");
    typing.classList.add("typing");
    setDisabled(true);

    let accumulated = "";
    try {
      const body: Record<string, unknown> = {
        message,
        org_id: cfg.orgId,
        history: history.slice(-10),
        session_id: sessionId,
      };
      if (cfg.context && history.length === 1) {
        body.message = `[Context: ${cfg.context}]\n\n${message}`;
      }

      const resp = await fetch(`${cfg.apiUrl}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Embed-Token": cfg.token,
        },
        body: JSON.stringify(body),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop()!;
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            if (ev.type === "token") {
              accumulated += ev.content;
              typing.textContent = accumulated + "▌";
              msgList.scrollTop = msgList.scrollHeight;
            } else if (ev.type === "done") {
              typing.textContent = accumulated || ev.answer || "";
              typing.classList.remove("typing");
              history.push({ role: "assistant", content: accumulated });
            } else if (ev.type === "error") {
              throw new Error(ev.message);
            }
          } catch {
            // ignore unparseable lines
          }
        }
      }
    } catch (err) {
      typing.textContent = "⚠ Something went wrong. Please try again.";
      typing.classList.remove("typing");
      console.error("[rag-widget]", err);
    } finally {
      if (typing.classList.contains("typing")) {
        typing.textContent = accumulated || "(no response)";
        typing.classList.remove("typing");
      }
      setDisabled(false);
      input.focus();
    }
  }

  // ── Events ────────────────────────────────────────────────────────────────

  bubble.addEventListener("click", () => {
    const isOpen = !panel.classList.contains("hidden");
    panel.classList.toggle("hidden", isOpen);
    if (!isOpen) input.focus();
  });

  shadow.querySelector(".close")!.addEventListener("click", () => {
    panel.classList.add("hidden");
  });

  sendBtn.addEventListener("click", send);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  document.addEventListener("click", (e) => {
    if (!host.contains(e.target as Node)) {
      panel.classList.add("hidden");
    }
  });
})();
