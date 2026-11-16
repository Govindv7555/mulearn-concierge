/**
 * µLearn Concierge — "Mu", the little chat buddy.
 *
 * A tiny original mascot that sits on the top-left edge of the chat window.
 * Its head sways, its legs swing, and it reacts to the conversation with short
 * words ("Ohooo!", "There you go!", "Oops!") instead of whole sentences.
 *
 * It is purely decorative (aria-hidden) and talks to chat.js only through
 * CustomEvents, so the chat keeps working even if this file fails to load:
 *   concierge:send     { text }
 *   concierge:reply    { reply, usedSources, offline }
 *   concierge:error    { kind: "timeout" | "network" | "rate" | "server" }
 *   concierge:newchat
 */
(function () {
  "use strict";

  var panel = document.querySelector(".chat-panel");
  if (!panel || panel.querySelector(".buddy")) return;

  // ---------------------------------------------------------------------------
  // Words Mu can say (short on purpose)
  // ---------------------------------------------------------------------------
  var PHRASES = {
    greet: ["Hi there!", "Hello!", "Hey, hey!"],
    think: ["Hmm…", "Let me see…", "Thinking…"],
    grounded: ["There you go!", "Ta-da!", "Got it!", "Ohooo!"],
    chat: ["Ohooo!", "Ooh!", "Nice!", "Hehe!"],
    thanks: ["Aww!", "Anytime!", "Hehe!"],
    laugh: ["Haha!", "Hehe!", "LOL!"],
    unsure: ["Hmm…", "Not sure…", "Ehh…"],
    busy: ["Oops!", "Busy bees!", "Zzz…"],
    error: ["Oops!", "Uh-oh!", "Whoops!"],
    offline: ["Oops!", "No signal!", "Uh-oh!"],
    slow: ["Whoa, easy!", "Slow down!"],
    fresh: ["Fresh start!", "New page!"],
    tickle: ["Hehe!", "Hey!", "Boop!", "Eek!"],
    hint: ["Psst… ask me!"]
  };

  var GREETING = /^\s*(hi+|hello+|hey+|hlo|helo|yo|hola|namaste)\b/i;
  var THANKS = /\b(thanks?|thank you|thanku|thx|ty)\b/i;
  var LAUGH = /\b(lol|haha+|hehe+|funny|joke)\b/i;
  var UNSURE = /(i'?m not certain|i am not certain|not sure|couldn'?t find|don'?t have (that|any))/i;

  // ---------------------------------------------------------------------------
  // Markup (inline SVG so it needs no image files)
  // ---------------------------------------------------------------------------
  var SVG =
    '<svg viewBox="0 0 96 112" width="100%" height="100%" focusable="false">' +
    '<defs>' +
    '<linearGradient id="bd-gold" x1="0" y1="0" x2="1" y2="1">' +
    '<stop offset="0" stop-color="#F3E3B8"/><stop offset="1" stop-color="#C9A96E"/></linearGradient>' +
    '<linearGradient id="bd-navy" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0" stop-color="#24375F"/><stop offset="1" stop-color="#101C33"/></linearGradient>' +
    '</defs>' +
    // legs (drawn first so the body overlaps the hips)
    '<g class="b-leg b-leg--l"><rect x="38" y="78" width="7" height="15" rx="3.5" fill="url(#bd-navy)" stroke="#C9A96E" stroke-width="1"/>' +
    '<ellipse cx="42" cy="94.5" rx="6.8" ry="3.6" fill="url(#bd-gold)"/></g>' +
    '<g class="b-leg b-leg--r"><rect x="51" y="78" width="7" height="15" rx="3.5" fill="url(#bd-navy)" stroke="#C9A96E" stroke-width="1"/>' +
    '<ellipse cx="55" cy="94.5" rx="6.8" ry="3.6" fill="url(#bd-gold)"/></g>' +
    // body
    '<rect x="33" y="54" width="30" height="30" rx="11" fill="url(#bd-navy)" stroke="#C9A96E" stroke-width="1.2"/>' +
    '<text class="b-mu" x="48" y="77" text-anchor="middle">µ</text>' +
    // arms
    '<g class="b-arm b-arm--l"><line x1="35" y1="62" x2="25" y2="74" stroke="url(#bd-gold)" stroke-width="6" stroke-linecap="round"/>' +
    '<circle cx="24" cy="75.5" r="4" fill="url(#bd-gold)"/></g>' +
    '<g class="b-arm b-arm--r"><line x1="61" y1="62" x2="73" y2="72" stroke="url(#bd-gold)" stroke-width="6" stroke-linecap="round"/>' +
    '<circle cx="74.5" cy="73.5" r="4" fill="url(#bd-gold)"/></g>' +
    // head
    '<g class="b-head">' +
    '<line x1="48" y1="13" x2="48" y2="5" stroke="#C9A96E" stroke-width="2" stroke-linecap="round"/>' +
    '<circle class="b-bulb" cx="48" cy="4" r="3.3" fill="#FFE29A"/>' +
    '<ellipse cx="48" cy="34" rx="27" ry="22" fill="url(#bd-gold)" stroke="#8C6F3A" stroke-width="1"/>' +
    '<rect x="28" y="22" width="40" height="24" rx="12" fill="#0B1426"/>' +
    '<g class="b-eyes">' +
    '<g class="b-eyes-open"><ellipse class="b-eye" cx="40" cy="32" rx="4" ry="4.6" fill="#FFF6DD"/>' +
    '<ellipse class="b-eye" cx="56" cy="32" rx="4" ry="4.6" fill="#FFF6DD"/>' +
    '<circle cx="41.2" cy="30.4" r="1.2" fill="#0B1426"/><circle cx="57.2" cy="30.4" r="1.2" fill="#0B1426"/></g>' +
    '<g class="b-eyes-happy"><path d="M35.5 33.5 Q40 27.5 44.5 33.5" stroke="#FFF6DD" stroke-width="2.6" fill="none" stroke-linecap="round"/>' +
    '<path d="M51.5 33.5 Q56 27.5 60.5 33.5" stroke="#FFF6DD" stroke-width="2.6" fill="none" stroke-linecap="round"/></g>' +
    '</g>' +
    '<g class="b-brows"><path d="M35 28 L44 25.5" stroke="#FFF6DD" stroke-width="1.8" stroke-linecap="round"/>' +
    '<path d="M61 28 L52 25.5" stroke="#FFF6DD" stroke-width="1.8" stroke-linecap="round"/></g>' +
    '<path class="b-mouth b-mouth--smile" d="M43 40 Q48 45 53 40" stroke="#FFF6DD" stroke-width="2" fill="none" stroke-linecap="round"/>' +
    '<path class="b-mouth b-mouth--open" d="M42.5 39.5 Q48 48 53.5 39.5 Z" fill="#FFB36B"/>' +
    '<path class="b-mouth b-mouth--flat" d="M44 41.5 L52 41.5" stroke="#FFF6DD" stroke-width="2" stroke-linecap="round"/>' +
    '<path class="b-mouth b-mouth--sad" d="M43 43.5 Q48 38.5 53 43.5" stroke="#FFF6DD" stroke-width="2" fill="none" stroke-linecap="round"/>' +
    '<circle class="b-cheek" cx="31" cy="41" r="3.2" fill="#FF9A8B"/><circle class="b-cheek" cx="65" cy="41" r="3.2" fill="#FF9A8B"/>' +
    '<path class="b-sweat" d="M72 18 q3.6 5.4 0 8.4 q-3.6 -3 0 -8.4z" fill="#8FC7FF"/>' +
    '</g>' +
    '</svg>';

  var root = document.createElement("div");
  root.className = "buddy";
  root.setAttribute("aria-hidden", "true");
  root.setAttribute("data-mood", "idle");
  root.innerHTML =
    '<div class="buddy__bubble"><span class="buddy__text"></span></div>' +
    '<div class="buddy__figure">' + SVG + '<div class="buddy__hit"></div></div>';
  panel.appendChild(root);

  var bubble = root.querySelector(".buddy__bubble");
  var textEl = root.querySelector(".buddy__text");
  var hit = root.querySelector(".buddy__hit");

  // ---------------------------------------------------------------------------
  // Behaviour
  // ---------------------------------------------------------------------------
  var hideTimer = null;
  var safetyTimer = null;
  var lastPhrase = "";
  var lastUser = "";
  var sentAny = false;
  var greeted = false;

  function pick(list) {
    var choice = list[0];
    for (var i = 0; i < 6 && list.length > 1; i++) {
      choice = list[Math.floor(Math.random() * list.length)];
      if (choice !== lastPhrase) break;
    }
    lastPhrase = choice;
    return choice;
  }

  function restartReaction() {
    root.classList.remove("is-react");
    void root.offsetWidth; // restart the CSS animation
    root.classList.add("is-react");
  }

  function hide() {
    clearTimeout(hideTimer);
    clearTimeout(safetyTimer);
    bubble.classList.remove("is-on");
    root.classList.remove("is-waving", "is-react");
    root.setAttribute("data-mood", "idle");
  }

  /**
   * Say a short word. mood: idle | happy | think | sad | oops.
   * ms = how long to keep the bubble (0 = until the next call, with a safety cap).
   */
  function say(text, mood, ms, wave) {
    clearTimeout(hideTimer);
    clearTimeout(safetyTimer);
    textEl.textContent = text;
    bubble.classList.add("is-on");
    root.setAttribute("data-mood", mood);
    root.classList.toggle("is-waving", !!wave);
    restartReaction();
    hideTimer = ms > 0 ? setTimeout(hide, ms) : null;
    if (!ms) safetyTimer = setTimeout(hide, 40000);
  }

  function classify(detail) {
    var reply = String(detail.reply || "");
    if (detail.offline) return ["busy", "oops", 2600];
    if (UNSURE.test(reply)) return ["unsure", "sad", 2400];
    if (THANKS.test(lastUser)) return ["thanks", "happy", 2400];
    if (GREETING.test(lastUser) && lastUser.length < 24) return ["greet", "happy", 2400, true];
    if (LAUGH.test(lastUser)) return ["laugh", "happy", 2200];
    if (detail.usedSources) return ["grounded", "happy", 2400];
    return ["chat", "happy", 2200];
  }

  document.addEventListener("concierge:send", function (e) {
    sentAny = true;
    lastUser = String((e.detail && e.detail.text) || "");
    say(pick(PHRASES.think), "think", 0);
  });

  document.addEventListener("concierge:reply", function (e) {
    var c = classify(e.detail || {});
    say(pick(PHRASES[c[0]]), c[1], c[2], c[3]);
  });

  document.addEventListener("concierge:error", function (e) {
    var kind = (e.detail && e.detail.kind) || "server";
    var key = kind === "rate" ? "slow" : kind === "network" ? "offline" : "error";
    say(pick(PHRASES[key]), "oops", 2800);
  });

  document.addEventListener("concierge:newchat", function () {
    sentAny = false;
    say(pick(PHRASES.fresh), "happy", 1800, true);
  });

  // Size Mu to the space above the card so it never pokes off the top of the screen.
  // Mu sits with its hips on the card edge; that is 0.875 x its width above the card.
  function fit() {
    var rect = panel.getBoundingClientRect();
    if (!rect.height) return;               // chat is hidden (3D intro still playing): keep defaults
    var w = Math.floor((rect.top - 4) / 0.875);
    root.style.setProperty("--bd-fit", Math.min(72, w) + "px");
    root.classList.toggle("is-tiny", w < 40);
  }
  fit();
  window.addEventListener("resize", fit);
  window.addEventListener("load", fit);
  if ("ResizeObserver" in window) new ResizeObserver(fit).observe(panel);  // also fires when the chat is revealed

  // Tickle: clicking Mu makes it jump and giggle.
  hit.addEventListener("click", function () {
    root.classList.remove("is-jump");
    void root.offsetWidth;
    root.classList.add("is-jump");
    say(pick(PHRASES.tickle), "happy", 1600);
    setTimeout(function () { root.classList.remove("is-jump"); }, 700);
  });

  // Greet once when the chat first scrolls into view (the 3D intro hides it first),
  // then give one friendly nudge if nobody has said anything for a while.
  function onFirstVisible() {
    if (greeted) return;
    greeted = true;
    setTimeout(function () { say(pick(PHRASES.greet), "happy", 2600, true); }, 700);
    setTimeout(function () {
      if (!sentAny && root.offsetParent !== null) say(pick(PHRASES.hint), "happy", 2600);
    }, 22000);
  }

  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        root.classList.toggle("is-paused", !en.isIntersecting);
        if (en.isIntersecting) onFirstVisible();
      });
    }, { threshold: 0.6 });
    io.observe(root);
  } else {
    onFirstVisible();
  }

  // Tiny public hook for debugging / future use: window.MuBuddy.say("Hi!", "happy", 2000)
  window.MuBuddy = { say: say, hide: hide };
})();
