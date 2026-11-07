/**
 * µLearn Concierge — Chat UI
 * Handles message sending, typewriter effect, typing indicator,
 * suggestions, auto-scroll, keyboard shortcuts, and accessibility.
 */

(function () {
  "use strict";

  // ----- DOM refs -----
  const chatMessages = document.getElementById("chatMessages");
  const chatForm = document.getElementById("chatForm");
  const messageInput = document.getElementById("messageInput");
  const btnSend = document.getElementById("btnSend");
  const btnNewChat = document.getElementById("btnNewChat");
  const suggestions = document.getElementById("suggestions");
  const charCount = document.getElementById("charCount");
  const syncTimestamp = document.getElementById("syncTimestamp");

  // ----- State -----
  const MAX_LENGTH = 1000;
  let conversationHistory = [];
  let isSending = false;
  window.__isSending = () => isSending;

  // ----- Init -----
  function init() {
    chatForm.addEventListener("submit", handleSubmit);
    messageInput.addEventListener("input", handleInput);
    messageInput.addEventListener("keydown", handleKeyDown);
    btnNewChat.addEventListener("click", handleNewChat);

    // Suggestion chips
    document.querySelectorAll(".chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const question = chip.dataset.question || chip.textContent;
        messageInput.value = question;
        handleSubmit(new Event("submit"));
      });
    });

    // Load sync timestamp
    fetchSyncStatus();

    // Init particles
    initParticles();

    // Ensure message list starts strictly at scrollTop 0
    if (chatMessages) {
      chatMessages.scrollTop = 0;
      requestAnimationFrame(() => {
        if (chatMessages) chatMessages.scrollTop = 0;
      });
    }

    // Window resize handler: if content fits without scrolling, ensure scrollTop stays 0
    window.addEventListener("resize", () => {
      if (chatMessages && chatMessages.scrollHeight <= chatMessages.clientHeight) {
        chatMessages.scrollTop = 0;
      }
    });

    // Focus input without shifting scroll
    if (messageInput) {
      messageInput.focus({ preventScroll: true });
    }
  }

  // ----- Input handling -----
  function handleInput() {
    // Auto-resize textarea
    messageInput.style.height = "auto";
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + "px";

    // Enable/disable send button
    const hasText = messageInput.value.trim().length > 0;
    btnSend.disabled = !hasText;

    // Char counter (show when > 800)
    const len = messageInput.value.length;
    if (len > 800) {
      charCount.textContent = `${len}/${MAX_LENGTH}`;
      charCount.style.opacity = "1";
      if (len > 950) charCount.style.color = "#e07a5f";
    } else {
      charCount.style.opacity = "0";
    }
  }

  function handleKeyDown(e) {
    // Enter to send (without shift)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isSending && messageInput.value.trim()) {
        handleSubmit(new Event("submit"));
      }
    }
  }

  // ----- Send message -----
  async function handleSubmit(e) {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || isSending) return;

    isSending = true;
    messageInput.value = "";
    messageInput.style.height = "auto";
    btnSend.disabled = true;
    hideSuggestions();

    // Add user message
    appendMessage(text, "user");
    scrollToBottom(true);

    // Show typing indicator
    const typingEl = showTypingIndicator();

    // 30-second client-side timeout
    const CLIENT_TIMEOUT_MS = 30000;
    const controller = new AbortController();
    let isTimedOut = false;
    const timeoutId = setTimeout(() => {
      isTimedOut = true;
      controller.abort();
    }, CLIENT_TIMEOUT_MS);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          message: text,
          history: conversationHistory.slice(-6),
        }),
      });

      clearTimeout(timeoutId);

      // Remove typing indicator
      typingEl.remove();

      if (res.status === 429) {
        appendMessage(
          "Please wait a moment before sending another message.",
          "assistant"
        );
        isSending = false;
        return;
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        appendMessage(
          err.error || "Something went wrong. Please try again.",
          "assistant"
        );
        isSending = false;
        return;
      }

      const data = await res.json();

      // Typewriter append for assistant response (sources shown only if used_sources is true)
      await typewriterAppend(
        data.reply,
        data.sources || [],
        Boolean(data.used_sources)
      );

      // Update history
      conversationHistory.push(
        { role: "user", content: text },
        { role: "assistant", content: data.reply }
      );
    } catch (err) {
      clearTimeout(timeoutId);
      typingEl.remove();
      if (isTimedOut || err.name === "AbortError") {
        appendMessage(
          "Taking longer than usual, please try again.",
          "assistant"
        );
      } else {
        appendMessage(
          "Network error. Please check your connection and try again.",
          "assistant"
        );
      }
    }

    isSending = false;
    if (messageInput) messageInput.focus({ preventScroll: true });
  }

  // ----- Message rendering -----
  function appendMessage(text, role) {
    const msg = document.createElement("div");
    msg.className = `message message--${role} message--entrance`;

    if (role === "assistant") {
      const avatar = document.createElement("div");
      avatar.className = "message__avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = "µ";
      msg.appendChild(avatar);
    }

    const content = document.createElement("div");
    content.className = "message__content";

    const bubble = document.createElement("div");
    bubble.className = "message__bubble";
    bubble.innerHTML = role === "assistant" ? formatMarkdown(text) : escapeHtml(text);
    content.appendChild(bubble);

    msg.appendChild(content);
    chatMessages.appendChild(msg);
    scrollToBottom(role === "user");
    return msg;
  }

  async function typewriterAppend(text, sources, usedSources = false) {
    // Check prefers-reduced-motion
    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    const msg = document.createElement("div");
    msg.className = "message message--assistant message--entrance";

    const avatar = document.createElement("div");
    avatar.className = "message__avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "µ";
    msg.appendChild(avatar);

    const content = document.createElement("div");
    content.className = "message__content";

    const bubble = document.createElement("div");
    bubble.className = "message__bubble";
    content.appendChild(bubble);
    msg.appendChild(content);
    chatMessages.appendChild(msg);

    if (prefersReduced) {
      // No animation, show all at once
      bubble.innerHTML = formatMarkdown(text);
    } else {
      // Typewriter effect — fluid, responsive typing (~0.8s total)
      const formatted = formatMarkdown(text);
      const totalChars = formatted.length;
      const chunkSize = Math.max(8, Math.ceil(totalChars / 40));
      let i = 0;

      await new Promise((resolve) => {
        function tick() {
          if (i < totalChars) {
            i = Math.min(i + chunkSize, totalChars);
            bubble.innerHTML = formatted.slice(0, i);
            scrollToBottom(false);
            setTimeout(tick, 16);
          } else {
            resolve();
          }
        }
        tick();
      });
    }

    // Add source chips ONLY when retrieved context was actually used
    if (usedSources && sources && sources.length > 0) {
      const sourceDiv = document.createElement("div");
      sourceDiv.className = "message__sources";
      sources.forEach((s) => {
        const chip = document.createElement("a");
        chip.className = "source-chip";
        chip.href = s.url;
        chip.target = "_blank";
        chip.rel = "noopener noreferrer";
        chip.textContent = s.label;
        sourceDiv.appendChild(chip);
      });
      content.appendChild(sourceDiv);
    }

    scrollToBottom(false);
  }

  // ----- Typing indicator -----
  function showTypingIndicator() {
    const msg = document.createElement("div");
    msg.className = "message message--assistant message--entrance";
    msg.id = "typingIndicator";

    const avatar = document.createElement("div");
    avatar.className = "message__avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "µ";
    msg.appendChild(avatar);

    const content = document.createElement("div");
    content.className = "message__content";

    const indicator = document.createElement("div");
    indicator.className = "typing-indicator";
    indicator.setAttribute("aria-label", "Assistant is typing");
    for (let i = 0; i < 3; i++) {
      const dot = document.createElement("span");
      dot.className = "typing-indicator__dot";
      indicator.appendChild(dot);
    }
    content.appendChild(indicator);
    msg.appendChild(content);
    chatMessages.appendChild(msg);
    scrollToBottom(true);
    return msg;
  }

  // ----- Suggestions -----
  function hideSuggestions() {
    suggestions.classList.add("suggestions--hidden");
  }

  // ----- New chat -----
  function handleNewChat() {
    conversationHistory = [];
    // Remove all messages except the welcome
    const messages = chatMessages.querySelectorAll(".message");
    messages.forEach((msg, i) => {
      if (i > 0) msg.remove();
    });
    suggestions.classList.remove("suggestions--hidden");

    // Strictly ensure message list is reset to top so welcome bubble is fully visible
    if (chatMessages) {
      chatMessages.scrollTop = 0;
      requestAnimationFrame(() => {
        if (chatMessages) {
          chatMessages.scrollTo({ top: 0, behavior: "auto" });
          chatMessages.scrollTop = 0;
        }
      });
    }

    if (messageInput) {
      messageInput.focus({ preventScroll: true });
    }
  }

  // ----- Auto-scroll -----
  function scrollToBottom(force = false) {
    if (!chatMessages) return;

    requestAnimationFrame(() => {
      const scrollHeight = chatMessages.scrollHeight;
      const clientHeight = chatMessages.clientHeight;
      const maxScroll = scrollHeight - clientHeight;

      // If content is shorter than or equal to visible area, strictly stay at scrollTop 0
      if (maxScroll <= 0) {
        chatMessages.scrollTop = 0;
        return;
      }

      const currentScroll = chatMessages.scrollTop;
      const distanceFromBottom = maxScroll - currentScroll;

      // Scroll only if forced (e.g. user just sent a message) OR if user is near bottom (<= 80px)
      if (force || distanceFromBottom <= 80) {
        chatMessages.scrollTo({
          top: scrollHeight,
          behavior: "smooth",
        });
      }
    });
  }

  // ----- Utilities -----
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function formatMarkdown(text) {
    // Simple markdown-to-HTML for chat messages
    let html = escapeHtml(text);

    // Bold: **text** or __text__
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");

    // Italic: *text* or _text_
    html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");

    // Inline code: `code`
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Links: [text](url)
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );

    // Bare URLs
    html = html.replace(
      /(?<!["=])(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
    );

    // Unordered list items: • or - or * at start of line
    html = html.replace(/^[•\-\*]\s+(.+)$/gm, "<li>$1</li>");
    html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");

    // Numbered list items
    html = html.replace(/^\d+\.\s+(.+)$/gm, "<li>$1</li>");

    // Paragraphs (double newline)
    html = html.replace(/\n\n+/g, "</p><p>");
    html = "<p>" + html + "</p>";

    // Single newlines to <br> within paragraphs
    html = html.replace(/\n/g, "<br>");

    // Clean up empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, "");

    // HR: ---
    html = html.replace(/<p>---<\/p>/g, "<hr>");

    return html;
  }

  // ----- Sync status -----
  async function fetchSyncStatus() {
    try {
      const res = await fetch("/api/status");
      if (res.ok) {
        const data = await res.json();
        if (data.news_last_synced) {
          syncTimestamp.textContent = data.news_last_synced;
        }
      }
    } catch (e) {
      // Silently fail — non-critical
    }
  }

  // ----- Particle system -----
  function initParticles() {
    const canvas = document.getElementById("particleCanvas");
    if (!canvas) return;

    // Respect reduced motion
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const ctx = canvas.getContext("2d");
    let particles = [];
    let mouseX = 0, mouseY = 0;
    const PARTICLE_COUNT = 40;

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }

    function createParticle() {
      return {
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        size: Math.random() * 2 + 0.5,
        speedX: (Math.random() - 0.5) * 0.3,
        speedY: (Math.random() - 0.5) * 0.3 - 0.1, // slight upward drift
        opacity: Math.random() * 0.4 + 0.1,
        // Gold or blue tint
        color: Math.random() > 0.6
          ? "201, 169, 110" // gold
          : "74, 124, 155",  // blue
      };
    }

    function initParticleArray() {
      particles = [];
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        particles.push(createParticle());
      }
    }

    function animate() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      particles.forEach((p) => {
        // Slow parallax toward mouse
        const dx = (mouseX - canvas.width / 2) * 0.00005;
        const dy = (mouseY - canvas.height / 2) * 0.00005;

        p.x += p.speedX + dx * p.size;
        p.y += p.speedY + dy * p.size;

        // Wrap around
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color}, ${p.opacity})`;
        ctx.fill();
      });

      requestAnimationFrame(animate);
    }

    resize();
    initParticleArray();
    animate();

    window.addEventListener("resize", () => {
      resize();
    });

    document.addEventListener("mousemove", (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
    });
  }

  // ----- Start -----
  document.addEventListener("DOMContentLoaded", init);
})();
