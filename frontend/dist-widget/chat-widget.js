(function(){"use strict";(function(){const i=document.currentScript||document.querySelector("script[data-token]");if(!i)return;const T=new URL(i.src).origin,t={token:i.getAttribute("data-token")||"",orgId:parseInt(i.getAttribute("data-org")||"0",10),title:i.getAttribute("data-title")||"Ask AI",position:i.getAttribute("data-position")||"bottom-right",accentColor:i.getAttribute("data-accent-color")||"#D85A30",welcomeMessage:i.getAttribute("data-welcome")||"Ask me anything about your knowledge base",context:i.getAttribute("data-context")||"",apiUrl:T};if(!t.token){console.warn("[rag-widget] data-token is required");return}const z=Math.random().toString(36).slice(2),p=[];fetch(`${t.apiUrl}/widget/config`,{headers:{"X-Embed-Token":t.token}}).then(e=>e.ok?e.json():null).then(e=>{e&&(e.chatbot_name&&(t.title=e.chatbot_name),e.accent_color&&(t.accentColor=e.accent_color),e.position&&(t.position=e.position),e.welcome_message&&(t.welcomeMessage=e.welcome_message),I())}).catch(()=>{});const m=`
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

    .powered-by {
      text-align: center;
      font-size: 10px;
      color: #d1d5db;
      padding: 4px 0 8px;
      background: white;
      flex-shrink: 0;
    }
  `,g=document.createElement("div");g.setAttribute("id","rag-chat-widget"),document.body.appendChild(g);const a=g.attachShadow({mode:"open"}),f=document.createElement("style");f.textContent=m,a.appendChild(f);const w=t.position.includes("left")?" pos-left":"",r=document.createElement("button");r.className="bubble"+w,r.setAttribute("aria-label","Open chat"),r.innerHTML=`
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
    </svg>`,a.appendChild(r);const y=e=>e.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"),s=document.createElement("div");s.className="panel hidden"+w,s.setAttribute("role","dialog"),s.setAttribute("aria-label",t.title),s.innerHTML=`
    <div class="panel-header">
      <span class="title" id="widget-title">${y(t.title)}</span>
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
        <span id="widget-welcome">${y(t.welcomeMessage)}</span>
      </div>
    </div>
    <div class="input-row">
      <input type="text" id="chat-input" placeholder="Ask a question…" autocomplete="off" />
      <button id="send-btn">Send</button>
    </div>
    <div class="powered-by">Powered by Knowledge Mesh</div>
  `,a.appendChild(s);const l=a.getElementById("msg-list"),c=a.getElementById("chat-input"),v=a.getElementById("send-btn");function I(){f.textContent=m.replace(/--accent:\s*[^;]+;/,`--accent: ${t.accentColor};`);const e=t.position.includes("left");r.classList.toggle("pos-left",e),s.classList.toggle("pos-left",e),s.setAttribute("aria-label",t.title);const n=a.getElementById("widget-title");n&&(n.textContent=t.title);const o=a.getElementById("widget-welcome");o&&b&&(o.textContent=t.welcomeMessage)}let k=!1,b=!0;function C(e,n){b&&(l.innerHTML="",b=!1);const o=document.createElement("div");return o.className=`msg ${e}`,o.textContent=n,l.appendChild(o),l.scrollTop=l.scrollHeight,o}function E(e){k=e,v.disabled=e,c.disabled=e}async function L(){const e=c.value.trim();if(!e||k)return;c.value="",C("user",e),p.push({role:"user",content:e});const n=C("assistant","▌");n.classList.add("typing"),E(!0);let o="";try{const u={message:e,org_id:t.orgId,history:p.slice(-10),session_id:z};t.context&&p.length===1&&(u.message=`[Context: ${t.context}]

${e}`);const h=await fetch(`${t.apiUrl}/chat/stream`,{method:"POST",headers:{"Content-Type":"application/json","X-Embed-Token":t.token},body:JSON.stringify(u)});if(!h.ok)throw new Error(`HTTP ${h.status}`);const S=h.body.getReader(),$=new TextDecoder;let x="";for(;;){const{done:B,value:_}=await S.read();if(B)break;x+=$.decode(_,{stream:!0});const A=x.split(`
`);x=A.pop();for(const M of A)if(M.startsWith("data: "))try{const d=JSON.parse(M.slice(6));if(d.type==="token")o+=d.content,n.textContent=o+"▌",l.scrollTop=l.scrollHeight;else if(d.type==="done")n.textContent=o||d.answer||"",n.classList.remove("typing"),p.push({role:"assistant",content:o});else if(d.type==="error")throw new Error(d.message)}catch{}}}catch(u){n.textContent="⚠ Something went wrong. Please try again.",n.classList.remove("typing"),console.error("[rag-widget]",u)}finally{n.classList.contains("typing")&&(n.textContent=o||"(no response)",n.classList.remove("typing")),E(!1),c.focus()}}r.addEventListener("click",()=>{const e=!s.classList.contains("hidden");s.classList.toggle("hidden",e),e||c.focus()}),a.querySelector(".close").addEventListener("click",()=>{s.classList.add("hidden")}),v.addEventListener("click",L),c.addEventListener("keydown",e=>{e.key==="Enter"&&!e.shiftKey&&(e.preventDefault(),L())}),document.addEventListener("click",e=>{g.contains(e.target)||s.classList.add("hidden")})})()})();
