(function () {
  // Автоматическое определение URL бэкенда (текущий хост или кастомный)
  const scriptTag = document.currentScript;
  const API_BASE = (scriptTag && scriptTag.getAttribute("data-api")) || window.location.origin;

  // Подключение CSS
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = `${API_BASE}/static/widget.css`;
  document.head.appendChild(link);

  let history = [];
  let isOpen = false;

  // Создание DOM элементов
  const button = document.createElement("button");
  button.id = "cvg-chat-widget-button";
  button.innerHTML = "💬";
  button.title = "Консультант по звуковому оборудованию CVGaudio";

  const windowEl = document.createElement("div");
  windowEl.id = "cvg-chat-widget-window";
  windowEl.className = "cvg-hidden";

  windowEl.innerHTML = `
    <div class="cvg-header">
      <div class="cvg-header-title">
        <span class="cvg-badge">CVG</span>
        <div>
          <h4>Инженер-консультант</h4>
          <p>Помощь в подборе звукового оборудования</p>
        </div>
      </div>
      <button class="cvg-close-btn">&times;</button>
    </div>
    <div class="cvg-messages" id="cvg-msg-container">
      <div class="cvg-msg cvg-msg-assistant">
        Здравствуйте! Я виртуальный инженер-консультант <b>CVGaudio (ЮНИТРЕКС)</b>.<br><br>
        Помогу рассчитать акустику для вашего объекта (кафе, магазин, фитнес, офис) или подобрать усилители и громкоговорители. Задайте вопрос своими словами!
      </div>
    </div>
    <div class="cvg-quick-actions" id="cvg-chips">
      <div class="cvg-chip" data-q="Мне нужно озвучить кафе на 60 кв. метров. Что посоветуете?">☕ Озвучить кафе/ресторан</div>
      <div class="cvg-chip" data-q="Помоги подобрать трансляционный микшер-усилитель на 2 зоны с Bluetooth">🔊 Подобрать усилитель</div>
      <div class="cvg-chip" data-q="Как озвучить торговый зал магазина с высокими потолками?">🛒 Звук для магазина</div>
      <div class="cvg-chip" data-q="Какие условия доставки и есть ли гарантия?">🚚 Доставка и гарантия</div>
    </div>
    <div class="cvg-lead-bar">
      Нужен точный проект? <span class="cvg-lead-link" id="cvg-lead-btn">Оставить заявку инженеру</span>
    </div>
    <div class="cvg-input-bar">
      <input type="text" id="cvg-chat-input" placeholder="Задайте вопрос по оборудованию..." autocomplete="off" />
      <button class="cvg-send-btn" id="cvg-send-btn">&#10148;</button>
    </div>
  `;

  document.body.appendChild(button);
  document.body.appendChild(windowEl);

  const msgContainer = windowEl.querySelector("#cvg-msg-container");
  const inputEl = windowEl.querySelector("#cvg-chat-input");
  const sendBtn = windowEl.querySelector("#cvg-send-btn");
  const closeBtn = windowEl.querySelector(".cvg-close-btn");
  const chipsContainer = windowEl.querySelector("#cvg-chips");
  const leadBtn = windowEl.querySelector("#cvg-lead-btn");

  // Переключение окна
  function toggleWidget() {
    isOpen = !isOpen;
    if (isOpen) {
      windowEl.classList.remove("cvg-hidden");
      button.innerHTML = "✕";
      inputEl.focus();
    } else {
      windowEl.classList.add("cvg-hidden");
      button.innerHTML = "💬";
    }
  }

  button.addEventListener("click", toggleWidget);
  closeBtn.addEventListener("click", toggleWidget);

  // Обработка клика по чипам
  chipsContainer.addEventListener("click", function (e) {
    if (e.target.classList.contains("cvg-chip")) {
      const q = e.target.getAttribute("data-q");
      sendMessage(q);
      chipsContainer.style.display = "none";
    }
  });

  // Отправка сообщения
  function formatMarkdown(text) {
    // Простое преобразование ссылок [text](url) -> <a> и **жирного**
    let formatted = text
      .replace(/\*\*(.*?)\*\*/g, "<b>$1</b>")
      .replace(/\[(.*?)\]\((https?:\/\/.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/\n/g, "<br>");
    return formatted;
  }

  function appendMessage(role, content, sources = []) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `cvg-msg cvg-msg-${role}`;
    msgDiv.innerHTML = formatMarkdown(content);

    if (sources && sources.length > 0) {
      const srcBox = document.createElement("div");
      srcBox.className = "cvg-sources";
      srcBox.innerHTML = '<div class="cvg-sources-title">Источники в каталоге:</div>';
      sources.slice(0, 3).forEach(s => {
        const a = document.createElement("a");
        a.className = "cvg-source-tag";
        a.href = s.url;
        a.target = "_blank";
        a.rel = "noopener";
        a.innerText = s.title;
        srcBox.appendChild(a);
      });
      msgDiv.appendChild(srcBox);
    }

    msgContainer.appendChild(msgDiv);
    msgContainer.scrollTop = msgContainer.scrollHeight;
    return msgDiv;
  }

  async function sendMessage(text) {
    const query = (text || inputEl.value).trim();
    if (!query) return;

    inputEl.value = "";
    appendMessage("user", query);
    history.push({ role: "user", content: query });

    // Индикатор набора текста
    const typingDiv = document.createElement("div");
    typingDiv.className = "cvg-msg cvg-msg-assistant cvg-typing";
    typingDiv.innerText = "Ассистент готовит ответ...";
    msgContainer.appendChild(typingDiv);
    msgContainer.scrollTop = msgContainer.scrollHeight;

    try {
      const resp = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query, history: history })
      });

      typingDiv.remove();

      if (resp.status === 401) {
        appendMessage("assistant", "🔒 <b>Требуется авторизация</b><br>Пожалуйста, войдите на стенд, используя логин и пароль в окне авторизации на странице.");
        return;
      }

      if (!resp.ok) {
        throw new Error(`Ошибка сервера: ${resp.status}`);
      }

      const data = await resp.json();
      appendMessage("assistant", data.response, data.sources);
      history.push({ role: "assistant", content: data.response });
    } catch (err) {
      typingDiv.remove();
      appendMessage("assistant", `⚠️ Не удалось связаться с сервером. Пожалуйста, проверьте подключение. (${err.message})`);
    }
  }

  sendBtn.addEventListener("click", () => sendMessage());
  inputEl.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
  });

  // Модалка / форма заявки инженеру
  leadBtn.addEventListener("click", function () {
    const name = prompt("Как к вам обращаться?");
    if (!name) return;
    const phone = prompt("Ваш номер телефона для связи:");
    if (!phone) return;

    fetch(`${API_BASE}/api/lead`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        phone: phone,
        comment: "Заявка на расчет акустики из веб-чата",
        chat_history: history
      })
    })
      .then(async r => {
        if (r.status === 401) throw new Error("Требуется авторизация на стенде");
        return r.json();
      })
      .then(res => {
        appendMessage("assistant", `✅ Спасибо, <b>${name}</b>! Ваша заявка передана дежурному инженеру ЮНИТРЕКС. Мы свяжемся с вами по номеру ${phone}.`);
      })
      .catch(e => {
        alert("Не удалось отправить заявку: " + e.message);
      });
  });
})();
