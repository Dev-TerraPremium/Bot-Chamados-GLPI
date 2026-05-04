const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chat-form");
const inputEl = document.querySelector("#message-input");
const resetButtonEl = document.querySelector("#reset-button");
const sendButtonEl = document.querySelector("#send-button");

const storageKey = "assistente_chamados_ti_session_id";

function getSessionId() {
  const existing = window.localStorage.getItem(storageKey);
  if (existing) {
    return existing;
  }
  const created = crypto.randomUUID();
  window.localStorage.setItem(storageKey, created);
  return created;
}

let sessionId = getSessionId();

function appendMessage(role, text) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setBusy(isBusy) {
  inputEl.disabled = isBusy;
  sendButtonEl.disabled = isBusy;
  resetButtonEl.disabled = isBusy;
}

async function postConversationMessage(message) {
  const response = await fetch("/api/conversation/message", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId,
      message,
    }),
  });

  if (!response.ok) {
    throw new Error("Falha ao comunicar com o servidor.");
  }

  return response.json();
}

async function resetConversation() {
  const response = await fetch("/api/conversation/reset", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId,
      message: "",
    }),
  });

  if (!response.ok) {
    throw new Error("Falha ao reiniciar a conversa.");
  }

  return response.json();
}

async function sendBotStart() {
  setBusy(true);
  try {
    const data = await postConversationMessage("__start__");
    appendMessage("bot", data.bot_message);
  } catch (error) {
    appendMessage("bot system-note", error.message);
  } finally {
    setBusy(false);
    inputEl.focus();
  }
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) {
    return;
  }

  appendMessage("user", message);
  inputEl.value = "";
  setBusy(true);

  try {
    const data = await postConversationMessage(message);
    sessionId = data.session_id;
    window.localStorage.setItem(storageKey, sessionId);
    appendMessage("bot", data.bot_message);
  } catch (error) {
    appendMessage("bot system-note", error.message);
  } finally {
    setBusy(false);
    inputEl.focus();
  }
});

resetButtonEl.addEventListener("click", async () => {
  setBusy(true);
  messagesEl.replaceChildren();

  try {
    const data = await resetConversation();
    sessionId = data.session_id;
    window.localStorage.setItem(storageKey, sessionId);
    appendMessage("bot", data.bot_message);
  } catch (error) {
    appendMessage("bot system-note", error.message);
  } finally {
    setBusy(false);
    inputEl.focus();
  }
});

inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

sendBotStart();

