/**
 * RAG Platform — Chat Widget
 *
 * Drop-in JS snippet for embedding the chat on any website.
 * Reads config from the <script> tag's data-* attributes:
 *
 *   <script src="/chat-widget.js"
 *           data-token="emb_xxxx"
 *           data-org="3"
 *           data-title="Ask AI"
 *           data-position="bottom-right"
 *           data-context="Current page: Incident INC001">
 *   </script>
 *
 * Shadow DOM is used for full CSS isolation.
 */

(function () {
  // ── Config ──────────────────────────────────────────────────────────────
  const script =
    (document.currentScript as HTMLScriptElement) ||
    document.querySelector('script[data-token]');

  if (!script) return;

  const apiUrl = new URL((script as HTMLScriptElement).src).origin;
  const cfg = {
    token:    script.getAttribute('data-token') || '',
    orgId:    parseInt(script.getAttribute('data-org') || '0', 10),
    title:    script.getAttribute('data-title') || 'Ask AI',
    position: script.getAttribute('data-position') || 'bottom-right',
    context:  script.getAttribute('data-context') || '',
    apiUrl,
  };

  if (!cfg.token) {
    console.warn('[rag-widget] data-token is required');
    return;
  }

  // ── Session ─────────────────────────────────────────────────────────────
  const sessionId = Math.random().toString(36).slice(2);
  const history: { role: string; content: string }[] = [];

  // ── CSS ──────────────────────────────────────────────────────────────────
  const CSS = `
    :host { all: initial; font-family: system-ui, sans-serif; }

    .bubble {
      position: fixed;
      ${cfg.position.includes('right') ? 'right: 24px;' : 'left: 24px;'}
      bottom: 24px;
      width: 52px; height: 52px;
      border-radius: 50%;
      background: #2563eb;
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 14px rgba(37,99,235,.45);
      display: flex; align-items: center; justify-content: center;
      transition: transform .15s, box-shadow .15s;
      z-index: 2147483647;
    }
    .bubble:hover { transform: scale(1.08); box-shadow: 0 6px 18px rgba(37,99,235,.55); }
    .bubble svg { width: 24px; height: 24px; fill: white; }

    .panel {
      position: fixed;
      ${cfg.position.includes('right') ? 'right: 24px;' : 'left: 24px;'}
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
      background: #2563eb;
      color: white;
      flex-shrink: 0;
    }
    .panel-header .title {
      font-size: 14px; font-weight: 600; letter-spacing: .01em;
    }
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
      background: #2563eb; color: white;
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
    .input-row input:focus { border-color: #93c5fd; }
    .input-row input::placeholder { color: #9ca3af; }

    .input-row button {
      padding: 9px 16px;
      background: #2563eb; color: white;
      border: none; border-radius: 10px;
      font-size: 13px; font-weight: 500;
      cursor: pointer;
      transition: background .15s;
      flex-shrink: 0;
    }
    .input-row button:hover { background: #1d4ed8; }
    .input-row button:disabled { background: #93c5fd; cursor: default; }

    .powered-by {
      text-align: center;
      font-size: 10px;
      color: #d1d5db;
      padding: 4px 0 8px;
      background: white;
      flex-shrink: 0;
    }
  `;

  // ── DOM ──────────────────────────────────────────────────────────────────
  const host = document.createElement('div');
  host.setAttribute('id', 'rag-chat-widget');
  document.body.appendChild(host);

  const shadow = host.attachShadow({ mode: 'open' });

  const styleEl = document.createElement('style');
  styleEl.textContent = CSS;
  shadow.appendChild(styleEl);

  // Bubble
  const bubble = document.createElement('button');
  bubble.className = 'bubble';
  bubble.setAttribute('aria-label', 'Open chat');
  bubble.innerHTML = `
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
    </svg>`;
  shadow.appendChild(bubble);

  // Panel
  const panel = document.createElement('div');
  panel.className = 'panel hidden';
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', cfg.title);
  panel.innerHTML = `
    <div class="panel-header">
      <span class="title">${escapeHtml(cfg.title)}</span>
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
        <span>Ask me anything about your knowledge base</span>
      </div>
    </div>
    <div class="input-row">
      <input type="text" id="chat-input" placeholder="Ask a question…" autocomplete="off" />
      <button id="send-btn">Send</button>
    </div>
    <div class="powered-by">Powered by Knowledge Mesh</div>
  `;
  shadow.appendChild(panel);

  // ── Refs ─────────────────────────────────────────────────────────────────
  const msgList   = shadow.getElementById('msg-list')!;
  const chatInput = shadow.getElementById('chat-input') as HTMLInputElement;
  const sendBtn   = shadow.getElementById('send-btn') as HTMLButtonElement;
  let   streaming = false;
  let   firstMsg  = true;

  // ── Helpers ───────────────────────────────────────────────────────────────
  function escapeHtml(s: string): string {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function addMessage(role: 'user' | 'assistant', text: string): HTMLElement {
    if (firstMsg) {
      msgList.innerHTML = '';   // clear empty-state
      firstMsg = false;
    }
    const el = document.createElement('div');
    el.className = `msg ${role}`;
    el.textContent = text;
    msgList.appendChild(el);
    msgList.scrollTop = msgList.scrollHeight;
    return el;
  }

  function setStreaming(on: boolean) {
    streaming = on;
    sendBtn.disabled = on;
    chatInput.disabled = on;
  }

  // ── Chat logic ────────────────────────────────────────────────────────────
  async function send() {
    const text = chatInput.value.trim();
    if (!text || streaming) return;

    chatInput.value = '';
    addMessage('user', text);
    history.push({ role: 'user', content: text });

    const assistantEl = addMessage('assistant', '▌');
    assistantEl.classList.add('typing');
    setStreaming(true);

    let assistantText = '';

    try {
      const body: Record<string, unknown> = {
        message: text,
        org_id:  cfg.orgId,
        history: history.slice(-10),
        session_id: sessionId,
      };
      // Prepend page context to the first message if provided
      if (cfg.context && history.length === 1) {
        body.message = `[Context: ${cfg.context}]\n\n${text}`;
      }

      const resp = await fetch(`${cfg.apiUrl}/chat/stream`, {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'X-Embed-Token': cfg.token,
        },
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const reader  = resp.body!.getReader();
      const decoder = new TextDecoder();
      let   buf     = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        // Process complete SSE lines
        const lines = buf.split('\n');
        buf = lines.pop()!;   // keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'token') {
              assistantText += data.content;
              assistantEl.textContent = assistantText + '▌';
              msgList.scrollTop = msgList.scrollHeight;
            } else if (data.type === 'done') {
              assistantEl.textContent = assistantText || data.answer || '';
              assistantEl.classList.remove('typing');
              history.push({ role: 'assistant', content: assistantText });
            } else if (data.type === 'error') {
              throw new Error(data.message);
            }
          } catch {
            // ignore malformed SSE frames
          }
        }
      }
    } catch (err) {
      assistantEl.textContent = '⚠ Something went wrong. Please try again.';
      assistantEl.classList.remove('typing');
      console.error('[rag-widget]', err);
    } finally {
      if (assistantEl.classList.contains('typing')) {
        assistantEl.textContent = assistantText || '(no response)';
        assistantEl.classList.remove('typing');
      }
      setStreaming(false);
      chatInput.focus();
    }
  }

  // ── Events ────────────────────────────────────────────────────────────────
  bubble.addEventListener('click', () => {
    const isOpen = !panel.classList.contains('hidden');
    panel.classList.toggle('hidden', isOpen);
    if (!isOpen) chatInput.focus();
  });

  shadow.querySelector('.close')!.addEventListener('click', () => {
    panel.classList.add('hidden');
  });

  sendBtn.addEventListener('click', send);

  chatInput.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  // Close on outside click
  document.addEventListener('click', (e: MouseEvent) => {
    if (!host.contains(e.target as Node)) {
      panel.classList.add('hidden');
    }
  });
})();
