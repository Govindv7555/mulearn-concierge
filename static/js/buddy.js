/**
 * µLearn Concierge — Mu Mascot ("Mu")
 * Animated SVG companion sitting on the top-left ledge of the chat card.
 */

(function () {
  "use strict";

  // Pools of short phrases (all <= 16 chars)
  var POOLS = {
    greet: ["Hi there!", "Hello!", "Hey, hey!"],
    think: ["Hmm…", "Let me see…", "Thinking…"],
    grounded: ["There you go!", "Ta-da!", "Got it!", "Ohooo!"],
    happy: ["Ohooo!", "Ooh!", "Nice!", "Hehe!"],
    thanks: ["Aww!", "Anytime!", "Yay!"],
    laugh: ["Hehe!", "Haha!"],
    unsure: ["Hmm…", "Not sure…", "Ehh…"],
    offline: ["Oops!", "Busy bees!", "Zzz…"],
    error: ["Oops!", "Uh-oh!", "Whoops!"],
    network: ["Oops!", "No signal!", "Uh-oh!"],
    rate: ["Whoa, easy!", "Slow down!"],
    newchat: ["Fresh start!"],
    giggle: ["Hehe!", "Tickles!", "Eek!"],
    idle_prompt: ["Psst… ask me!"],
  };

  var lastWord = "";
  var lastUserText = "";
  var hasSent = false;
  var hasGreeted = false;
  var speechTimer = null;
  var thinkSafetyTimer = null;
  var idleTimer = null;

  var buddyEl = null;
  var textEl = null;
  var hitEl = null;

  function pickWord(pool) {
    if (!pool || pool.length === 0) return "";
    var choice = pool[Math.floor(Math.random() * pool.length)];
    if (pool.length > 1 && choice === lastWord) {
      var filtered = pool.filter(function (w) {
        return w !== lastWord;
      });
      choice = filtered[Math.floor(Math.random() * filtered.length)];
    }
    lastWord = choice;
    return choice;
  }

  function say(text, mood) {
    if (!buddyEl || !textEl) return;
    text = String(text || "").slice(0, 16);

    if (speechTimer) {
      clearTimeout(speechTimer);
      speechTimer = null;
    }
    if (thinkSafetyTimer) {
      clearTimeout(thinkSafetyTimer);
      thinkSafetyTimer = null;
    }

    textEl.textContent = text;
    buddyEl.dataset.mood = mood || "idle";
    buddyEl.dataset.speaking = "true";

    if (mood === "think") {
      // Stays active until reply/error arrives, with a 40s safety cap
      thinkSafetyTimer = setTimeout(function () {
        hide();
      }, 40000);
    } else {
      // Normal speech lasts about 2.5s, then returns to idle
      speechTimer = setTimeout(function () {
        hide();
      }, 2500);
    }
  }

  function hide() {
    if (!buddyEl) return;
    if (speechTimer) {
      clearTimeout(speechTimer);
      speechTimer = null;
    }
    if (thinkSafetyTimer) {
      clearTimeout(thinkSafetyTimer);
      thinkSafetyTimer = null;
    }
    buddyEl.dataset.speaking = "false";
    buddyEl.dataset.mood = "idle";
  }

  // Expose global controller
  window.MuBuddy = {
    say: say,
    hide: hide,
  };

  // Build Mascot DOM and SVG
  function createBuddyDOM() {
    var panel = document.querySelector(".chat-panel");
    if (!panel) return false;
    if (panel.querySelector(".buddy")) return true;

    var container = document.createElement("div");
    container.className = "buddy";
    container.setAttribute("aria-hidden", "true");
    container.dataset.mood = "idle";
    container.dataset.speaking = "false";

    // Speech bubble
    var bubble = document.createElement("div");
    bubble.className = "buddy__bubble";
    var textSpan = document.createElement("span");
    textSpan.className = "buddy__text";
    bubble.appendChild(textSpan);
    container.appendChild(bubble);

    // Figure
    var figure = document.createElement("div");
    figure.className = "buddy__figure";

    figure.innerHTML =
      '<svg class="buddy__svg" viewBox="0 0 96 112" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<g class="b-figure-inner">' +
      '<!-- Legs (alternate swing) -->' +
      '<g class="b-leg--l">' +
      '<rect x="35" y="83" width="7" height="19" rx="3.5" fill="#dfc28d" stroke="#b08d55" stroke-width="1"/>' +
      '<ellipse cx="37" cy="103" rx="6" ry="4" fill="#dfc28d" stroke="#b08d55" stroke-width="1"/>' +
      '</g>' +
      '<g class="b-leg--r">' +
      '<rect x="54" y="83" width="7" height="19" rx="3.5" fill="#dfc28d" stroke="#b08d55" stroke-width="1"/>' +
      '<ellipse cx="59" cy="103" rx="6" ry="4" fill="#dfc28d" stroke="#b08d55" stroke-width="1"/>' +
      '</g>' +
      '<!-- Left Arm -->' +
      '<g class="b-arm--l">' +
      '<rect x="18" y="66" width="16" height="6" rx="3" transform="rotate(35 33 69)" fill="#dfc28d" stroke="#b08d55" stroke-width="1"/>' +
      '<circle cx="21" cy="80" r="3.5" fill="#dfc28d" stroke="#b08d55" stroke-width="1"/>' +
      '</g>' +
      '<!-- Right Arm -->' +
      '<g class="b-arm--r">' +
      '<rect x="62" y="66" width="16" height="6" rx="3" transform="rotate(-35 63 69)" fill="#dfc28d" stroke="#b08d55" stroke-width="1"/>' +
      '<circle cx="75" cy="80" r="3.5" fill="#dfc28d" stroke="#b08d55" stroke-width="1"/>' +
      '</g>' +
      '<!-- Body & Chest Monogram -->' +
      '<g class="b-body">' +
      '<rect x="32" y="63" width="32" height="24" rx="12" fill="#0d172b" stroke="#c9a96e" stroke-width="2.2"/>' +
      '<g class="b-mu">' +
      '<text x="48" y="79.5" font-family="\'Cormorant Garamond\', \'Georgia\', serif" font-size="15" font-weight="600" fill="#dfc28d" text-anchor="middle" dominant-baseline="central">µ</text>' +
      '</g>' +
      '</g>' +
      '<!-- Neck -->' +
      '<rect x="44.5" y="60.5" width="7" height="4" rx="1.5" fill="#c9a96e"/>' +
      '<!-- Head Group -->' +
      '<g class="b-head">' +
      '<rect x="46.5" y="15" width="3" height="6" rx="1.5" fill="#c9a96e"/>' +
      '<g class="b-bulb">' +
      '<circle cx="48" cy="11.5" r="4.5" fill="#dfc28d" stroke="#c9a96e" stroke-width="1.2"/>' +
      '</g>' +
      '<rect x="17" y="20" width="62" height="42" rx="19" fill="#dfc28d" stroke="#b08d55" stroke-width="1.5"/>' +
      '<rect x="23.5" y="25" width="49" height="32" rx="13.5" fill="#0c1424"/>' +
      '<!-- Cheeks -->' +
      '<g class="b-cheeks">' +
      '<circle cx="29.5" cy="46" r="3.5" fill="#e87a90" opacity="0.65"/>' +
      '<circle cx="66.5" cy="46" r="3.5" fill="#e87a90" opacity="0.65"/>' +
      '</g>' +
      '<!-- Eyes: Normal blink -->' +
      '<g class="b-eyes b-eyes--normal">' +
      '<rect x="33" y="35" width="7" height="11" rx="3.5" fill="#ffffff"/>' +
      '<rect x="56" y="35" width="7" height="11" rx="3.5" fill="#ffffff"/>' +
      '<circle cx="37" cy="38" r="1.5" fill="#0c1424"/>' +
      '<circle cx="60" cy="38" r="1.5" fill="#0c1424"/>' +
      '</g>' +
      '<!-- Eyes: Happy squint ^ ^ -->' +
      '<g class="b-eyes b-eyes--happy">' +
      '<path d="M 31 42 Q 36.5 34 42 42" stroke="#ffffff" stroke-width="3" stroke-linecap="round" fill="none"/>' +
      '<path d="M 54 42 Q 59.5 34 65 42" stroke="#ffffff" stroke-width="3" stroke-linecap="round" fill="none"/>' +
      '</g>' +
      '<!-- Eyes: Think looking up -->' +
      '<g class="b-eyes b-eyes--think">' +
      '<rect x="34" y="32" width="7" height="10" rx="3.5" fill="#ffffff"/>' +
      '<rect x="57" y="32" width="7" height="10" rx="3.5" fill="#ffffff"/>' +
      '<circle cx="38" cy="34" r="1.5" fill="#0c1424"/>' +
      '<circle cx="61" cy="34" r="1.5" fill="#0c1424"/>' +
      '</g>' +
      '<!-- Eyes: Sad / Worried -->' +
      '<g class="b-eyes b-eyes--sad">' +
      '<ellipse cx="37" cy="40" rx="4.5" ry="5.5" transform="rotate(18 37 40)" fill="#ffffff"/>' +
      '<ellipse cx="59" cy="40" rx="4.5" ry="5.5" transform="rotate(-18 59 40)" fill="#ffffff"/>' +
      '<circle cx="38" cy="38" r="1.5" fill="#0c1424"/>' +
      '<circle cx="58" cy="38" r="1.5" fill="#0c1424"/>' +
      '</g>' +
      '<!-- Brows: Sad \ / -->' +
      '<g class="b-brows b-brows--sad">' +
      '<path d="M 32 32.5 Q 37 29.5 42 32.5" stroke="#ffffff" stroke-width="2" stroke-linecap="round" fill="none"/>' +
      '<path d="M 54 32.5 Q 59 29.5 64 32.5" stroke="#ffffff" stroke-width="2" stroke-linecap="round" fill="none"/>' +
      '</g>' +
      '<!-- 4 Mouths: smile, open, flat, sad -->' +
      '<path class="b-mouth b-mouth--smile" d="M 44 48.5 Q 48 52 52 48.5" stroke="#ffffff" stroke-width="2" stroke-linecap="round" fill="none"/>' +
      '<path class="b-mouth b-mouth--open" d="M 43 47 Q 48 47 53 47 Q 53 54.5 48 54.5 Q 43 54.5 43 47 Z" fill="#e88938" stroke="#dfc28d" stroke-width="1.2"/>' +
      '<path class="b-mouth b-mouth--flat" d="M 44.5 50 L 51.5 50" stroke="#ffffff" stroke-width="2" stroke-linecap="round" fill="none"/>' +
      '<path class="b-mouth b-mouth--sad" d="M 43 52.5 Q 48 47.5 53 52.5" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" fill="none"/>' +
      '<!-- Sweat Drop -->' +
      '<path class="b-sweat" d="M 72 28.5 C 72 26.5 70 23.5 70 23.5 C 70 23.5 68 26.5 68 28.5 C 68 30 69 31.5 70 31.5 C 71 31.5 72 30 72 28.5 Z" fill="#9de2fb" opacity="0.88"/>' +
      '</g>' +
      '</g>' +
      '</svg>' +
      '<div class="buddy__hit" aria-label="Mu Mascot"></div>';

    container.appendChild(figure);
    panel.appendChild(container);

    buddyEl = container;
    textEl = textSpan;
    hitEl = container.querySelector(".buddy__hit");

    if (hitEl) {
      hitEl.addEventListener("click", function (e) {
        e.stopPropagation();
        say(pickWord(POOLS.giggle), "giggle");
      });
    }

    return true;
  }

  // Fit sizing based on available space above card
  function fit() {
    var panel = document.querySelector(".chat-panel");
    if (!panel || !buddyEl) return;
    var rect = panel.getBoundingClientRect();
    // Skip if chat panel has no layout yet (3D intro playing)
    if (rect.width === 0 || rect.height === 0 || rect.top === 0) {
      return;
    }
    var spaceAvailable = rect.top;
    if (spaceAvailable < 40) {
      buddyEl.style.visibility = "hidden";
      return;
    }
    buddyEl.style.visibility = "visible";
    var isMobile = window.innerWidth <= 560;
    var maxBase = isMobile ? 56 : 72;
    var fitSize = Math.max(36, Math.min(maxBase, spaceAvailable));
    buddyEl.style.setProperty("--bd-fit", fitSize + "px");
  }

  // Event Listeners for concierge events
  function setupEvents() {
    window.addEventListener("concierge:send", function (e) {
      hasSent = true;
      if (idleTimer) {
        clearTimeout(idleTimer);
        idleTimer = null;
      }
      var text = (e.detail && e.detail.text) || "";
      lastUserText = text;
      say(pickWord(POOLS.think), "think");
    });

    window.addEventListener("concierge:reply", function (e) {
      var d = e.detail || {};
      var reply = d.reply || "";
      var usedSources = Boolean(d.usedSources);
      var offline = Boolean(d.offline);

      // Reply classification order: offline, unsure, thanks/greeting/laugh (from user's last message), grounded, normal
      if (offline) {
        say(pickWord(POOLS.offline), "offline");
      } else if (/not certain|not sure|i don't know/i.test(reply)) {
        say(pickWord(POOLS.unsure), "unsure");
      } else if (/\b(thanks|thank you|thx|ty)\b/i.test(lastUserText)) {
        say(pickWord(POOLS.thanks), "thanks");
      } else if (/\b(lol|haha|hehe|rofl|lmao)\b/i.test(lastUserText)) {
        say(pickWord(POOLS.laugh), "laugh");
      } else if (/^(hi|hello|hey|greetings|morning|evening|night)\b/i.test(lastUserText.trim())) {
        say(pickWord(POOLS.greet), "greet");
      } else if (usedSources) {
        say(pickWord(POOLS.grounded), "grounded");
      } else {
        say(pickWord(POOLS.happy), "happy");
      }
    });

    window.addEventListener("concierge:error", function (e) {
      var kind = (e.detail && e.detail.kind) || "";
      if (kind === "rate") {
        say(pickWord(POOLS.rate), "rate");
      } else if (kind === "network") {
        say(pickWord(POOLS.network), "network");
      } else {
        say(pickWord(POOLS.error), "error");
      }
    });

    window.addEventListener("concierge:newchat", function () {
      hasSent = false;
      if (idleTimer) {
        clearTimeout(idleTimer);
        idleTimer = null;
      }
      say(pickWord(POOLS.newchat), "newchat");
    });
  }

  // Monitor chat section visibility
  function setupObservers() {
    var chatSection = document.getElementById("chat");
    var panel = document.querySelector(".chat-panel");
    if (!chatSection || !panel) return;

    if ("IntersectionObserver" in window) {
      var observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (!buddyEl) return;
            if (entry.isIntersecting) {
              buddyEl.classList.remove("buddy--paused");
              fit();
              if (!hasGreeted) {
                hasGreeted = true;
                setTimeout(function () {
                  say(pickWord(POOLS.greet), "greet");
                }, 700);
                idleTimer = setTimeout(function () {
                  if (!hasSent) {
                    say("Psst… ask me!", "idle_prompt");
                  }
                }, 22000);
              }
            } else {
              buddyEl.classList.add("buddy--paused");
            }
          });
        },
        { threshold: 0.1 }
      );
      observer.observe(chatSection);
    } else {
      // Fallback
      if (!hasGreeted) {
        hasGreeted = true;
        setTimeout(function () {
          say(pickWord(POOLS.greet), "greet");
        }, 700);
      }
    }

    if (window.ResizeObserver) {
      new ResizeObserver(fit).observe(panel);
    }
    window.addEventListener("resize", fit);
  }

  function init() {
    createBuddyDOM();
    setupEvents();
    setupObservers();
    fit();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
