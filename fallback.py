"""
µLearn Concierge — Fallback Responder
Keyword-matching FAQ and small-talk responder that activates when the Gemini API
is unavailable or fails. Ensures the app never breaks and handles greetings,
small talk, and µLearn questions gracefully.
"""

import re
import random

# Small-talk intents: friendly canned replies with NO source chip
SMALL_TALK_INTENTS = [
    {
        "keywords": [
            "hi", "hello", "hey", "hlo", "helo", "hii", "wassup",
            "gm", "good morning", "good evening", "good afternoon", "howdy", "greetings"
        ],
        "answer": (
            "Hello! I'm your µLearn Concierge. How can I help you today? "
            "Feel free to ask about Interest Groups, Karma points, campus chapters, "
            "or the latest community news!"
        ),
    },
    {
        "keywords": ["how are you", "how are u", "hows it going", "how's it going", "how do you do", "how have you been"],
        "answer": (
            "I'm doing well, thank you for asking! Ready to help you explore everything "
            "happening across the µLearn community. What would you like to know?"
        ),
    },
    {
        "keywords": ["thank you", "thanks", "thanku", "thx", "appreciate it", "ty", "thank you so much"],
        "answer": (
            "You're very welcome! Let me know if you need any more information about "
            "µLearn, projects, or Karma points."
        ),
    },
    {
        "keywords": ["bye", "goodbye", "gn", "good night", "see you", "see ya", "cya", "farewell", "have a good day"],
        "answer": (
            "Goodbye! Have a great time learning and building on µLearn. See you around!"
        ),
    },
    {
        "keywords": ["ok", "okay", "alright", "got it", "sure", "k"],
        "answer": (
            "Understood! Let me know if you'd like to explore µLearn Interest Groups, "
            "Karma points, campus chapters, or the latest announcements."
        ),
    },
    {
        "keywords": ["who are you", "what are you", "who r u", "introduce yourself", "your name"],
        "answer": (
            "I'm the µLearn Concierge, an assistant created for µLearn CHN "
            "(College of Engineering Chengannur). I'm here to help you navigate "
            "the µLearn ecosystem, from Interest Groups to Karma points and announcements."
        ),
    },
    {
        "keywords": ["what can you do", "how can you help", "what do you do", "capabilities", "help me"],
        "answer": (
            "I can help you navigate the µLearn platform! Here's what you can ask me about:\n\n"
            "• What µLearn is and how to get your µID\n"
            "• Joining domain Interest Groups (AI, Web, IoT, etc.)\n"
            "• Earning Karma points and submitting proof of work\n"
            "• Forming Learning Circles with peers\n"
            "• Campus chapter activities (like µLearn CHN at CEC)\n"
            "• Latest announcements and community events"
        ),
    },
    {
        "keywords": ["joke", "tell me a joke", "make me laugh", "say something funny"],
        "answer": (
            "Why do programmers prefer dark mode? Because light attracts bugs! 🐛\n\n"
            "Feel free to ask another, or ask about our µLearn coding challenges!"
        ),
    },
]

# Curated µLearn platform FAQ entries
FAQ_ENTRIES = [
    {
        "keywords": ["what is mulearn", "what's mulearn", "about mulearn", "tell me about mulearn", "explain mulearn"],
        "answer": (
            "µLearn is a community-driven education platform launched by GTech "
            "(the Group of Technology Companies, the IT industry body of Kerala). It transforms learning "
            "through peer-to-peer collaboration, gamification with Karma points, "
            "and real-world skill development. Instead of traditional lectures, "
            "µLearn connects students through Interest Groups, Learning Circles, "
            "and campus chapters.\n\n"
            "Learn more at https://mulearn.org"
        ),
    },
    {
        "keywords": ["interest group", "ig ", "igs", "what are igs", "join ig", "join interest group", "ai interest group", "ai ig"],
        "answer": (
            "Interest Groups (IGs) are domain-specific communities within µLearn "
            "where learners passionate about a particular field collaborate. "
            "Popular IGs include:\n\n"
            "• AI/ML\n• Web Development\n• UI/UX Design\n"
            "• Cyber Security\n• IoT & Robotics\n• Cloud Computing\n\n"
            "Each IG is led by an Interest Group Lead who organizes activities "
            "and mentors members. Join one that matches your passion through the µLearn platform!"
        ),
    },
    {
        "keywords": ["karma", "points", "karma points", "earn karma", "how to earn"],
        "answer": (
            "Karma points are µLearn's gamification system — visible proof of your "
            "learning effort and community contribution. You earn them by:\n\n"
            "• Completing coding tasks and projects\n"
            "• Participating in challenges and bootcamps\n"
            "• Helping peers and contributing to open source\n"
            "• Submitting proof of work (reviewed by peers/mentors)\n\n"
            "Karma points drive leaderboards and reflect on your µID profile, "
            "which employers can review."
        ),
    },
    {
        "keywords": ["join", "sign up", "register", "how to join", "get started"],
        "answer": (
            "To join µLearn:\n\n"
            "1. Visit https://mulearn.org and click 'Join' or 'Get Started'\n"
            "2. Create your account to get your µID\n"
            "3. Join Interest Groups that match your interests\n"
            "4. Find or create a Learning Circle at your campus\n"
            "5. Start earning Karma points!\n\n"
            "If your college has a campus chapter (like µLearn CHN), "
            "connect with your campus lead for local activities."
        ),
    },
    {
        "keywords": ["campus chapter", "college", "chn", "chengannur", "cec"],
        "answer": (
            "Campus chapters are college-level µLearn communities that operate "
            "autonomously under the µLearn umbrella. µLearn CHN is the campus "
            "chapter at the College of Engineering Chengannur (CEC), part of the "
            "broader GTech µLearn network.\n\n"
            "Campus chapters organize local events, learning circles, and "
            "Interest Group activities with their own leads and coordinators."
        ),
    },
    {
        "keywords": ["learning circle", "circle", "peer group", "study group"],
        "answer": (
            "Learning Circles are small peer groups (typically 3–7 members) who "
            "study, build projects, and solve challenges together. They're the "
            "fundamental unit of collaborative learning in µLearn.\n\n"
            "Each circle focuses on a specific topic and meets regularly to "
            "share progress and review each other's work."
        ),
    },
    {
        "keywords": ["muid", "µid", "mu id", "digital profile", "profile"],
        "answer": (
            "Your µID is a permanent digital profile on µLearn — a living portfolio "
            "that tracks your Karma points, completed projects, events attended, "
            "Interest Groups joined, and proof of work submitted.\n\n"
            "Unlike a static resume, it's a verifiable timeline that employers "
            "and recruiters can review to gauge your practical capabilities."
        ),
    },
    {
        "keywords": ["event", "hackathon", "workshop", "bootcamp", "program"],
        "answer": (
            "µLearn regularly organizes events including:\n\n"
            "• Hackathons and buildathons\n"
            "• Tech bootcamps and workshops\n"
            "• Community challenges with Karma rewards\n"
            "• Orientation sessions for new members\n"
            "• Industry mentorship sessions\n\n"
            "Check https://mulearn.org and the µLearn Discord for the latest events."
        ),
    },
    {
        "keywords": ["discord", "community", "chat", "server"],
        "answer": (
            "The µLearn Discord server is the primary real-time communication hub. "
            "It hosts announcements, Interest Group channels, help channels, and "
            "community hangouts.\n\n"
            "Join here: https://discord.gg/5xdYHfjFt"
        ),
    },
    {
        "keywords": ["news", "latest", "announcement", "update", "what's new", "whats new", "recent"],
        "answer": (
            "For the latest µLearn news and announcements, check:\n\n"
            "• The µLearn website: https://mulearn.org\n"
            "• The µLearn Discord #announcements channel\n\n"
            "This concierge also pulls news from the central GTech µLearn announcements feed."
        ),
    },
    {
        "keywords": ["lead", "ig lead", "interest group lead", "become lead", "apply lead"],
        "answer": (
            "Interest Group Leads are student volunteers who organize activities, "
            "mentor members, and drive their IG's learning community. They play a "
            "key role in shaping the learning experience within their domain.\n\n"
            "To learn about becoming an IG Lead, check with your campus chapter "
            "or visit the µLearn platform for current openings."
        ),
    },
]

# Offline mode message for general off-topic queries
OFFLINE_GENERAL_RESPONSE = (
    "I'm currently running in offline knowledge mode, where I specialize in µLearn topics! "
    "General chat, coding help, and open-ended Q&A require the online AI mode (Gemini). "
    "For now, feel free to ask me anything about µLearn, Interest Groups, Karma points, "
    "or campus chapters!"
)

# Default uncertain response when query seems related but lacks context
DEFAULT_RESPONSE = (
    "I'm not certain about that. Please check "
    "https://mulearn.org or the µLearn Discord (https://discord.gg/5xdYHfjFt) "
    "for the latest information."
)


def _normalize(text):
    """Normalize text and µLearn variants for robust keyword matching."""
    cleaned = text.strip()
    cleaned = re.sub(r'(?i)\b(mulearn|µlearn|ulearn|\u00b5learn|\u03bclearn)\b', 'mulearn', cleaned)
    return cleaned.lower()


def fallback_answer(message, chunks=None):
    """Generate a response in offline mode.

    Handles:
    1. Small talk intents (greetings, thanks, jokes, who are you) -> returns friendly reply with NO sources.
    2. µLearn FAQ matches -> returns answer WITH sources (used_sources=True).
    3. Retrieved knowledge chunks -> returns grounded answer WITH sources (used_sources=True).
    4. General off-topic queries -> informs user that general Q&A needs AI mode, with NO sources.

    Args:
        message: The user's message.
        chunks: Optional retrieved knowledge chunks.

    Returns:
        Tuple of (reply_text, sources_list, used_sources_bool).
    """
    msg_raw = message.strip()
    norm_msg = _normalize(msg_raw)
    words = set(re.findall(r'[a-z0-9]+', norm_msg))

    # 1. Check small-talk intents first (no sources attached)
    for intent in SMALL_TALK_INTENTS:
        for kw in intent["keywords"]:
            if " " in kw:
                if kw in norm_msg:
                    return intent["answer"], [], False
            else:
                if kw in words or norm_msg == kw:
                    return intent["answer"], [], False

    # 2. Check µLearn FAQ entries (sources attached)
    best_match = None
    best_score = 0
    for entry in FAQ_ENTRIES:
        score = 0
        for kw in entry["keywords"]:
            if kw in norm_msg:
                score = max(score, len(kw))
        if score > best_score:
            best_score = score
            best_match = entry

    if best_match:
        sources = [{"label": "µLearn Website", "url": "https://mulearn.org"}]
        answer = best_match["answer"]
        if chunks:
            for chunk in chunks[:2]:
                if chunk.get("source") == "discord":
                    sources.append({
                        "label": "µLearn Discord #announcements",
                        "url": "https://discord.gg/5xdYHfjFt",
                    })
        return answer, sources, True

    # 3. Check retrieved chunks if available
    if chunks:
        sources = [{"label": "µLearn Website", "url": "https://mulearn.org"}]
        parts = []
        for chunk in chunks[:3]:
            text = chunk["text"].strip()
            text = text.replace("## ", "**").replace("# ", "**")
            if len(text) > 300:
                text = text[:300].rsplit(" ", 1)[0] + "…"
            parts.append(text)
            if chunk.get("source") == "discord":
                sources.append({
                    "label": "µLearn Discord #announcements",
                    "url": "https://discord.gg/5xdYHfjFt",
                })
        if parts:
            return "Here's what I found from µLearn:\n\n" + "\n\n".join(parts), sources, True

    # 4. Off-topic query in offline mode: explain that general chat needs online AI mode
    return OFFLINE_GENERAL_RESPONSE, [], False
