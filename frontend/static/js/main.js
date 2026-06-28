// ── Roadmap Generator ──────────────────────────────────────
const generateBtn = document.getElementById("generate-btn");
const roadmapOutput = document.getElementById("roadmap-output");
const roadmapCard = document.getElementById("roadmap-card");

if (generateBtn) {
  generateBtn.addEventListener("click", async () => {
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span class="spinner"></span> Generating...';
    roadmapCard.classList.remove("hidden");
    roadmapOutput.innerHTML = '<div class="skeleton" style="width:80%"></div><div class="skeleton" style="width:60%"></div><div class="skeleton" style="width:90%"></div><div class="skeleton" style="width:50%"></div>';

    try {
      const res = await fetch("/generate", { method: "POST" });
      const data = await res.json();
      if (data.error) {
        roadmapOutput.textContent = "⚠ " + data.error;
      } else {
        roadmapOutput.textContent = data.roadmap;
      }
    } catch (e) {
      roadmapOutput.textContent = "⚠ Could not reach the server. Please try again.";
    }

    generateBtn.disabled = false;
    generateBtn.innerHTML = '🗺 Generate My Roadmap';
  });
}

// ── Chat Assistant ─────────────────────────────────────────
const chatWindow = document.getElementById("chat-window");
const chatInput  = document.getElementById("chat-input");
const chatSend   = document.getElementById("chat-send");

function appendMsg(text, role) {
  const wrap   = document.createElement("div");
  wrap.className = `chat-msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  chatWindow.appendChild(wrap);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function appendThinking() {
  const wrap = document.createElement("div");
  wrap.className = "chat-msg ai";
  wrap.id = "thinking";
  wrap.innerHTML = '<div class="chat-bubble"><span class="spinner"></span> Thinking...</div>';
  chatWindow.appendChild(wrap);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function sendChat() {
  const q = chatInput.value.trim();
  if (!q) return;
  appendMsg(q, "user");
  chatInput.value = "";
  chatSend.disabled = true;
  appendThinking();

  try {
    const res  = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const data = await res.json();
    document.getElementById("thinking")?.remove();
    appendMsg(data.answer || data.error || "No response.", "ai");
  } catch (e) {
    document.getElementById("thinking")?.remove();
    appendMsg("⚠ Server error. Try again.", "ai");
  }
  chatSend.disabled = false;
}

if (chatSend) {
  chatSend.addEventListener("click", sendChat);
}
if (chatInput) {
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
}

// ── History expand ─────────────────────────────────────────
document.querySelectorAll(".history-toggle").forEach(btn => {
  btn.addEventListener("click", () => {
    const preview = btn.closest(".history-item").querySelector(".history-full");
    const isOpen  = preview.style.display === "block";
    preview.style.display = isOpen ? "none" : "block";
    btn.textContent = isOpen ? "Show roadmap ↓" : "Hide ↑";
  });
});
