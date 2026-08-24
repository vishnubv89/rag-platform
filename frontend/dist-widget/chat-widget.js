(function(){"use strict";(function(){const d=document.currentScript||document.querySelector("script[data-token]");if(!d)return;const U=new URL(d.src).origin,t={token:d.getAttribute("data-token")||"",orgId:parseInt(d.getAttribute("data-org")||"0",10),title:d.getAttribute("data-title")||"Ask AI",position:d.getAttribute("data-position")||"bottom-right",accentColor:d.getAttribute("data-accent-color")||"#D85A30",welcomeMessage:d.getAttribute("data-welcome")||"Ask me anything about your knowledge base",context:d.getAttribute("data-context")||"",apiUrl:U};if(!t.token){console.warn("[rag-widget] data-token is required");return}const O=Math.random().toString(36).slice(2),x=[];fetch(`${t.apiUrl}/widget/config`,{headers:{"X-Embed-Token":t.token}}).then(e=>e.ok?e.json():null).then(e=>{e&&(e.chatbot_name&&(t.title=e.chatbot_name),e.accent_color&&(t.accentColor=e.accent_color),e.position&&(t.position=e.position),e.welcome_message&&(t.welcomeMessage=e.welcome_message),P())}).catch(()=>{});const T=`
    :host {
      all: initial;
      font-family: system-ui, sans-serif;
      --accent: ${t.accentColor};
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

    .mic-btn {
      flex-shrink: 0;
      width: 34px; height: 34px;
      padding: 0;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      background: white;
      color: #6b7280;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: background .15s, border-color .15s;
    }
    .mic-btn svg { width: 15px; height: 15px; }
    .mic-btn.recording {
      background: #FCEBEB; border-color: #F7C1C1; color: #791F1F;
      animation: mic-pulse 1.4s ease-in-out infinite;
    }
    .mic-btn:disabled { opacity: .5; cursor: default; animation: none; }
    @keyframes mic-pulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(121,31,31,.35); }
      50% { box-shadow: 0 0 0 5px rgba(121,31,31,0); }
    }

    .msg-actions { margin: -4px 0 2px; }
    .msg-actions .speak-btn {
      background: none; border: none; cursor: pointer;
      color: #9ca3af; padding: 2px; opacity: .8;
      display: inline-flex; align-items: center;
    }
    .msg-actions .speak-btn:hover { opacity: 1; }
    .msg-actions .speak-btn svg { width: 13px; height: 13px; }
    .msg-actions .speak-btn.playing svg { color: var(--accent); }

    .powered-by {
      text-align: center;
      font-size: 10px;
      color: #d1d5db;
      padding: 4px 0 8px;
      background: white;
      flex-shrink: 0;
    }
  `,w=document.createElement("div");w.setAttribute("id","rag-chat-widget"),document.body.appendChild(w);const c=w.attachShadow({mode:"open"}),v=document.createElement("style");v.textContent=T,c.appendChild(v);const A=t.position.includes("left")?" pos-left":"",b=document.createElement("button");b.className="bubble"+A,b.setAttribute("aria-label","Open chat"),b.innerHTML=`
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
    </svg>`,c.appendChild(b);const S=e=>e.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"),r=document.createElement("div");r.className="panel hidden"+A,r.setAttribute("role","dialog"),r.setAttribute("aria-label",t.title),r.innerHTML=`
    <div class="panel-header">
      <span class="title" id="widget-title">${S(t.title)}</span>
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
        <span id="widget-welcome">${S(t.welcomeMessage)}</span>
      </div>
    </div>
    <div class="input-row">
      <button id="mic-btn" class="mic-btn" type="button" aria-label="Speak your question">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="23"/>
        </svg>
      </button>
      <input type="text" id="chat-input" placeholder="Ask a question…" autocomplete="off" />
      <button id="send-btn">Send</button>
    </div>
    <div class="powered-by">Powered by Knowledge Mesh</div>
  `,c.appendChild(r);const p=c.getElementById("msg-list"),l=c.getElementById("chat-input"),B=c.getElementById("send-btn"),y=c.getElementById("mic-btn");function P(){v.textContent=T.replace(/--accent:\s*[^;]+;/,`--accent: ${t.accentColor};`);const e=t.position.includes("left");b.classList.toggle("pos-left",e),r.classList.toggle("pos-left",e),r.setAttribute("aria-label",t.title);const i=c.getElementById("widget-title");i&&(i.textContent=t.title);const n=c.getElementById("widget-welcome");n&&C&&(n.textContent=t.welcomeMessage)}let E=!1,C=!0;function $(e,i){C&&(p.innerHTML="",C=!1);const n=document.createElement("div");return n.className=`msg ${e}`,n.textContent=i,p.appendChild(n),p.scrollTop=p.scrollHeight,n}function z(e){E=e,B.disabled=e,l.disabled=e,y.disabled=e||k==="transcribing"}let f=null;function N(e,i){if(!i.trim())return;const n=document.createElement("div");n.className="msg-actions";const o=document.createElement("button");o.className="speak-btn",o.type="button",o.title="Play aloud",o.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>',o.addEventListener("click",async()=>{if(f&&!f.paused){f.pause(),f=null,o.classList.remove("playing");return}o.disabled=!0;try{const s=await fetch(`${t.apiUrl}/voice/speak`,{method:"POST",headers:{"Content-Type":"application/json","X-Embed-Token":t.token},body:JSON.stringify({text:i})});if(!s.ok)throw new Error(`HTTP ${s.status}`);const g=await s.blob(),a=new Audio(URL.createObjectURL(g));f=a,o.classList.add("playing"),a.onended=()=>o.classList.remove("playing"),a.onerror=()=>o.classList.remove("playing"),await a.play()}catch(s){console.error("[rag-widget] speak failed",s)}finally{o.disabled=!1}}),n.appendChild(o),e.insertAdjacentElement("afterend",n),p.scrollTop=p.scrollHeight}let h=null,L=[],k="idle";function m(e){k=e,y.classList.toggle("recording",e==="recording"),y.disabled=e==="transcribing"||E}async function _(){var e;if(!((e=navigator.mediaDevices)!=null&&e.getUserMedia)){console.warn("[rag-widget] voice input not supported in this browser");return}try{const i=await navigator.mediaDevices.getUserMedia({audio:!0});L=[];const n=new MediaRecorder(i);h=n,n.ondataavailable=o=>{o.data.size>0&&L.push(o.data)},n.onstop=async()=>{i.getTracks().forEach(s=>s.stop());const o=new Blob(L,{type:"audio/webm"});if(o.size===0){m("idle");return}m("transcribing");try{const s=new FormData;s.append("file",o,"speech.webm");const g=await fetch(`${t.apiUrl}/voice/transcribe`,{method:"POST",headers:{"X-Embed-Token":t.token},body:s});if(!g.ok)throw new Error(`HTTP ${g.status}`);const{text:a}=await g.json();a!=null&&a.trim()&&(l.value=l.value?`${l.value} ${a.trim()}`:a.trim(),l.focus())}catch(s){console.error("[rag-widget] transcribe failed",s)}finally{m("idle")}},n.start(),m("recording")}catch{console.warn("[rag-widget] microphone access denied"),m("idle")}}function D(){(h==null?void 0:h.state)==="recording"&&h.stop()}y.addEventListener("click",()=>{k==="recording"?D():k==="idle"&&_()});async function j(){const e=l.value.trim();if(!e||E)return;l.value="",$("user",e),x.push({role:"user",content:e});const i=$("assistant","▌");i.classList.add("typing"),z(!0);let n="";try{const o={message:e,org_id:t.orgId,history:x.slice(-10),session_id:O};t.context&&x.length===1&&(o.message=`[Context: ${t.context}]

${e}`);const s=await fetch(`${t.apiUrl}/chat/stream`,{method:"POST",headers:{"Content-Type":"application/json","X-Embed-Token":t.token},body:JSON.stringify(o)});if(!s.ok)throw new Error(`HTTP ${s.status}`);const g=s.body.getReader(),a=new TextDecoder;let M="";for(;;){const{done:R,value:q}=await g.read();if(R)break;M+=a.decode(q,{stream:!0});const H=M.split(`
`);M=H.pop();for(const I of H)if(I.startsWith("data: "))try{const u=JSON.parse(I.slice(6));if(u.type==="token")n+=u.content,i.textContent=n+"▌",p.scrollTop=p.scrollHeight;else if(u.type==="done")i.textContent=n||u.answer||"",i.classList.remove("typing"),x.push({role:"assistant",content:n}),N(i,n||u.answer||"");else if(u.type==="error")throw new Error(u.message)}catch{}}}catch(o){i.textContent="⚠ Something went wrong. Please try again.",i.classList.remove("typing"),console.error("[rag-widget]",o)}finally{i.classList.contains("typing")&&(i.textContent=n||"(no response)",i.classList.remove("typing")),z(!1),l.focus()}}b.addEventListener("click",()=>{const e=!r.classList.contains("hidden");r.classList.toggle("hidden",e),e||l.focus()}),c.querySelector(".close").addEventListener("click",()=>{r.classList.add("hidden")}),B.addEventListener("click",j),l.addEventListener("keydown",e=>{e.key==="Enter"&&!e.shiftKey&&(e.preventDefault(),j())}),document.addEventListener("click",e=>{w.contains(e.target)||r.classList.add("hidden")})})()})();
