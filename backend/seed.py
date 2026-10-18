"""Seed data.

* Categories and SAMPLE QUIZZES (educational content written for this project)
  so the platform is usable immediately. No attempts, users, scores or
  statistics are fabricated – all metrics start at zero.
* TQM baseline records:
    - FMEA: an *initial risk assessment* (ratings are engineering judgements
      to be reviewed by the project team, not measurements).
    - Defect log: genuine defects found and fixed while this codebase was
      being developed and reviewed (source = "development").
    - PDCA: improvement cycles derived from those defects.
    - Version log: the actual v1.0.0 release notes.
"""
from __future__ import annotations

import json
from datetime import date

from .extensions import db
from .models import (AnswerOption, Category, ChangelogEntry, Defect, FMEAItem, PDCAAction, Question, Quiz,
                     QuizQuestion)
from .utils import slugify, utcnow

CATEGORIES = [
    ("Quality Management", "#8B5CF6", "trophy", "TQM principles, quality tools and continuous improvement."),
    ("Python Programming", "#3B82F6", "code", "Core Python syntax, data types and problem solving."),
    ("Computer Science", "#06B6D4", "atom", "Computer fundamentals, data structures and networks."),
    ("General Knowledge", "#F97362", "globe", "Geography, history, culture and current affairs."),
    ("Science", "#14B8A6", "flask", "Physics, chemistry and biology essentials."),
    ("Mathematics", "#F59E0B", "calculator", "Arithmetic, algebra and quantitative aptitude."),
    ("Business & Management", "#EC4899", "briefcase", "Management concepts, communication and strategy."),
    ("English & Communication", "#22C55E", "book", "Grammar, vocabulary and professional communication."),
]

# t: single | multiple | truefalse | short | fill ;  c: correct option indexes ; a: accepted answers
QUIZZES = [
    {
        "title": "TQM Fundamentals", "category": "Quality Management", "difficulty": "easy", "time": 12,
        "pass": 50, "featured": True, "tags": "tqm,quality,bbat104",
        "description": "Test your understanding of Total Quality Management principles, the PDCA cycle and the "
                       "classic quality tools used in BBAT104.",
        "instructions": "Answer all 10 questions. Each correct answer earns the marks shown. There is no negative "
                        "marking. Results and explanations are shown immediately after submission.",
        "questions": [
            {"t": "single", "q": "What does PDCA stand for in continuous improvement?",
             "o": ["Plan-Do-Check-Act", "Prepare-Deliver-Control-Audit", "Plan-Design-Create-Assess",
                   "Process-Data-Control-Action"], "c": [0], "d": "easy", "topic": "PDCA",
             "e": "The Deming (Shewhart) cycle is Plan, Do, Check, Act — an iterative loop for Kaizen."},
            {"t": "single", "q": "A Pareto chart is primarily used to…",
             "o": ["Identify the vital few causes responsible for most problems",
                   "Show the process flow from supplier to customer", "Track a process mean over time",
                   "Calculate the risk priority number"], "c": [0], "d": "easy", "topic": "Pareto",
             "e": "Pareto analysis applies the 80/20 rule: roughly 80% of effects come from 20% of causes."},
            {"t": "fill", "q": "In FMEA, RPN = Severity × Occurrence × ___.", "a": ["Detection"], "d": "medium",
             "topic": "FMEA", "e": "The Risk Priority Number multiplies Severity, Occurrence and Detection ratings."},
            {"t": "truefalse", "q": "An Ishikawa diagram is also known as a fishbone or cause-and-effect diagram.",
             "c": True, "d": "easy", "topic": "Fishbone",
             "e": "Kaoru Ishikawa popularised the fishbone diagram for structured root-cause analysis."},
            {"t": "multiple", "q": "Which of the following are core TQM principles? (Select all that apply)",
             "o": ["Customer focus", "Continuous improvement", "Fact-based decision making",
                   "Inspection only at the end of production"], "c": [0, 1, 2], "m": 2, "d": "medium",
             "topic": "Principles",
             "e": "TQM emphasises prevention over final inspection, plus customer focus, Kaizen and data-driven decisions."},
            {"t": "single", "q": "What does SIPOC stand for?",
             "o": ["Suppliers, Inputs, Process, Outputs, Customers", "Systems, Inputs, Planning, Operations, Control",
                   "Standards, Inspection, Process, Output, Compliance", "Suppliers, Inventory, Production, Orders, Cost"],
             "c": [0], "d": "easy", "topic": "SIPOC",
             "e": "A SIPOC diagram maps a process at a high level from suppliers through to customers."},
            {"t": "short", "q": "What is the Japanese term for continuous improvement?", "a": ["Kaizen"],
             "d": "easy", "topic": "Kaizen", "e": "Kaizen (改善) means 'change for the better'."},
            {"t": "single", "q": "Poka-Yoke in software quality most closely means…",
             "o": ["Error-proofing so mistakes cannot easily occur", "Testing after deployment",
                   "Writing documentation", "Measuring customer satisfaction"], "c": [0], "d": "medium",
             "topic": "Poka-Yoke", "e": "Poka-Yoke is mistake-proofing — e.g. strict input validation and field masks."},
            {"t": "single", "q": "CTQ in Six Sigma and TQM stands for…",
             "o": ["Critical to Quality", "Cost to Quality", "Control the Quality", "Customer Total Quality"],
             "c": [0], "d": "easy", "topic": "CTQ",
             "e": "CTQs are the measurable characteristics a customer considers critical."},
            {"t": "truefalse", "q": "A check sheet is a structured form for collecting and tallying defect data.",
             "c": True, "d": "easy", "topic": "Check sheet",
             "e": "Check sheets standardise data collection — one of the seven basic quality tools."},
        ],
    },
    {
        "title": "Python Basics", "category": "Python Programming", "difficulty": "easy", "time": 15, "pass": 50,
        "featured": True, "tags": "python,programming,beginner",
        "description": "Variables, data types, operators, lists and functions — a friendly first check of your "
                       "Python fundamentals.",
        "instructions": "10 questions, 15 minutes. Read code snippets carefully. You may attempt this quiz up to "
                        "3 times; your best score counts on the leaderboard.",
        "max_attempts": 3,
        "questions": [
            {"t": "single", "q": "What is the output of print(type(3.0))?",
             "o": ["<class 'float'>", "<class 'int'>", "<class 'double'>", "<class 'number'>"], "c": [0],
             "d": "easy", "topic": "Data types", "e": "3.0 is a floating-point literal, so its type is float."},
            {"t": "single", "q": "Which keyword defines a function in Python?", "o": ["def", "func", "function",
                                                                                    "lambda only"],
             "c": [0], "d": "easy", "topic": "Functions", "e": "Functions are defined with def name(params):"},
            {"t": "short", "q": "What does len([1, 2, 3, 4]) return? (Type the number)", "a": ["4", "four"],
             "d": "easy", "topic": "Lists", "e": "len() returns the number of items: 4."},
            {"t": "multiple", "q": "Which of these are mutable built-in types?",
             "o": ["list", "dict", "tuple", "set"], "c": [0, 1, 3], "m": 2, "d": "medium", "topic": "Data types",
             "e": "Lists, dicts and sets can change in place; tuples are immutable."},
            {"t": "truefalse", "q": "Python uses indentation to define code blocks.", "c": True, "d": "easy",
             "topic": "Syntax", "e": "Indentation is syntactically significant in Python."},
            {"t": "single", "q": "What is the result of 7 // 2 in Python 3?", "o": ["3", "3.5", "4", "2"], "c": [0],
             "d": "easy", "topic": "Operators", "e": "// is floor division: 7 // 2 == 3."},
            {"t": "fill", "q": "To add an item to the end of a list you call my_list.___(item).", "a": ["append"],
             "d": "easy", "topic": "Lists", "e": "list.append(x) adds x to the end of the list."},
            {"t": "single", "q": "Which statement correctly opens a file and closes it automatically?",
             "o": ["with open('f.txt') as f:", "open('f.txt').auto_close()", "file('f.txt') as f:",
                   "using open('f.txt') as f:"], "c": [0], "d": "medium", "topic": "Files",
             "e": "The with statement uses a context manager that closes the file automatically."},
            {"t": "single", "q": "What does 'hello'[1] evaluate to?", "o": ["'e'", "'h'", "'el'", "IndexError"],
             "c": [0], "d": "easy", "topic": "Strings", "e": "Indexing starts at 0, so index 1 is 'e'."},
            {"t": "truefalse", "q": "A Python dictionary can have duplicate keys.", "c": False, "d": "medium",
             "topic": "Dictionaries", "e": "Keys are unique; assigning an existing key overwrites its value."},
        ],
    },
    {
        "title": "General Knowledge Challenge", "category": "General Knowledge", "difficulty": "medium", "time": 10,
        "pass": 40, "featured": True, "tags": "gk,india,world",
        "description": "A lively mix of geography, history and culture questions about India and the world.",
        "instructions": "8 questions in 10 minutes. Questions and options are shuffled for every attempt.",
        "shuffle_q": True, "shuffle_o": True,
        "questions": [
            {"t": "single", "q": "Which is the capital city of Karnataka?", "o": ["Bengaluru", "Mysuru", "Mangaluru",
                                                                                 "Hubballi"],
             "c": [0], "d": "easy", "topic": "India", "e": "Bengaluru is the capital of Karnataka."},
            {"t": "single", "q": "Which is the largest ocean on Earth?",
             "o": ["Pacific Ocean", "Atlantic Ocean", "Indian Ocean", "Arctic Ocean"], "c": [0], "d": "easy",
             "topic": "Geography", "e": "The Pacific covers about one-third of Earth's surface."},
            {"t": "single", "q": "In which year did India adopt its Constitution (come into effect)?",
             "o": ["1950", "1947", "1949", "1952"], "c": [0], "d": "medium", "topic": "History",
             "e": "The Constitution came into effect on 26 January 1950 (Republic Day)."},
            {"t": "short", "q": "Which planet is known as the Red Planet?", "a": ["Mars"], "d": "easy",
             "topic": "Space", "e": "Iron oxide on its surface gives Mars its reddish colour."},
            {"t": "truefalse", "q": "The Great Wall of China is located in Japan.", "c": False, "d": "easy",
             "topic": "World", "e": "The Great Wall is in northern China."},
            {"t": "single", "q": "Who wrote the Indian national anthem 'Jana Gana Mana'?",
             "o": ["Rabindranath Tagore", "Bankim Chandra Chatterjee", "Sarojini Naidu", "Muhammad Iqbal"], "c": [0],
             "d": "medium", "topic": "Culture", "e": "It was composed by Rabindranath Tagore."},
            {"t": "single", "q": "Which river is the longest in India?", "o": ["Ganga", "Godavari", "Krishna",
                                                                              "Narmada"],
             "c": [0], "d": "medium", "topic": "India", "e": "The Ganga is the longest river flowing within India."},
            {"t": "multiple", "q": "Which of these are UNESCO World Heritage Sites in India?",
             "o": ["Hampi", "Taj Mahal", "Qutub Minar", "Eiffel Tower"], "c": [0, 1, 2], "m": 2, "d": "medium",
             "topic": "Heritage", "e": "Hampi, the Taj Mahal and Qutub Minar are Indian UNESCO sites."},
        ],
    },
    {
        "title": "Everyday Science", "category": "Science", "difficulty": "easy", "time": 10, "pass": 50,
        "tags": "science,physics,biology",
        "description": "Core physics, chemistry and biology ideas you meet every day.",
        "instructions": "8 questions. Explanations are revealed after you submit.",
        "questions": [
            {"t": "single", "q": "What is the chemical formula of water?", "o": ["H2O", "CO2", "O2", "H2O2"],
             "c": [0], "d": "easy", "topic": "Chemistry", "e": "Two hydrogen atoms bonded to one oxygen atom."},
            {"t": "single", "q": "What is the SI unit of force?", "o": ["Newton", "Joule", "Watt", "Pascal"],
             "c": [0], "d": "easy", "topic": "Physics", "e": "1 newton = 1 kg·m/s²."},
            {"t": "short", "q": "Which gas do plants absorb from the atmosphere for photosynthesis?",
             "a": ["carbon dioxide", "CO2"], "d": "easy", "topic": "Biology",
             "e": "Plants use carbon dioxide, water and sunlight to make glucose."},
            {"t": "truefalse", "q": "Sound travels faster in a vacuum than in air.", "c": False, "d": "medium",
             "topic": "Physics", "e": "Sound needs a medium; it cannot travel through a vacuum."},
            {"t": "single", "q": "Which organ pumps blood around the human body?", "o": ["Heart", "Lungs", "Liver",
                                                                                         "Kidney"],
             "c": [0], "d": "easy", "topic": "Biology", "e": "The heart circulates blood through the body."},
            {"t": "fill", "q": "The powerhouse of the cell is the ___.", "a": ["mitochondria", "mitochondrion"],
             "d": "easy", "topic": "Biology", "e": "Mitochondria produce most of the cell's ATP."},
            {"t": "single", "q": "Approximately how fast does light travel in a vacuum?",
             "o": ["3 × 10^8 m/s", "3 × 10^5 m/s", "340 m/s", "1.5 × 10^6 m/s"], "c": [0], "d": "medium",
             "topic": "Physics", "e": "The speed of light is about 299,792 km/s ≈ 3 × 10^8 m/s."},
            {"t": "multiple", "q": "Which of these are noble gases?", "o": ["Helium", "Neon", "Oxygen", "Argon"],
             "c": [0, 1, 3], "m": 2, "d": "medium", "topic": "Chemistry",
             "e": "Helium, neon and argon are group-18 noble gases; oxygen is not."},
        ],
    },
    {
        "title": "Quick Maths Sprint", "category": "Mathematics", "difficulty": "medium", "time": 8, "pass": 60,
        "tags": "aptitude,arithmetic", "negative": True,
        "description": "Fast arithmetic and aptitude questions. Negative marking applies — think before you click!",
        "instructions": "8 questions in 8 minutes. Each wrong answer deducts 0.25 marks; unanswered questions score "
                        "zero. Your total can never go below zero.",
        "questions": [
            {"t": "single", "q": "What is 15% of 240?", "o": ["36", "24", "30", "40"], "c": [0], "n": 0.25,
             "d": "easy", "topic": "Percentages", "e": "0.15 × 240 = 36."},
            {"t": "short", "q": "What is the square root of 144?", "a": ["12"], "n": 0.25, "d": "easy",
             "topic": "Roots", "e": "12 × 12 = 144."},
            {"t": "single", "q": "If 3x + 5 = 20, what is x?", "o": ["5", "6", "4", "15"], "c": [0], "n": 0.25,
             "d": "easy", "topic": "Algebra", "e": "3x = 15, so x = 5."},
            {"t": "single", "q": "A train travels 300 km in 4 hours. What is its average speed?",
             "o": ["75 km/h", "70 km/h", "80 km/h", "1200 km/h"], "c": [0], "n": 0.25, "d": "easy",
             "topic": "Speed", "e": "Speed = distance / time = 300 / 4 = 75 km/h."},
            {"t": "truefalse", "q": "Every prime number greater than 2 is odd.", "c": True, "n": 0.25,
             "d": "medium", "topic": "Number theory", "e": "Any even number > 2 is divisible by 2, so not prime."},
            {"t": "single", "q": "What is the next number in the series 2, 6, 12, 20, 30, …?",
             "o": ["42", "40", "36", "44"], "c": [0], "n": 0.25, "d": "medium", "topic": "Series",
             "e": "Differences are 4, 6, 8, 10, 12 → 30 + 12 = 42."},
            {"t": "fill", "q": "The sum of the interior angles of a triangle is ___ degrees.", "a": ["180"],
             "n": 0.25, "d": "easy", "topic": "Geometry", "e": "Interior angles of any triangle sum to 180°."},
            {"t": "single", "q": "Simple interest on ₹5,000 at 8% per annum for 2 years is…",
             "o": ["₹800", "₹400", "₹832", "₹1,000"], "c": [0], "n": 0.25, "d": "medium", "topic": "Interest",
             "e": "SI = P × R × T / 100 = 5000 × 8 × 2 / 100 = ₹800."},
        ],
    },
    {
        "title": "Computer Fundamentals", "category": "Computer Science", "difficulty": "easy", "time": 10,
        "pass": 50, "tags": "computers,hardware,networks",
        "description": "Hardware, software, networking and data-storage basics every student should know.",
        "instructions": "8 questions. Correct answers are revealed after submission.",
        "questions": [
            {"t": "single", "q": "What does CPU stand for?",
             "o": ["Central Processing Unit", "Computer Personal Unit", "Central Program Utility",
                   "Control Processing Unit"], "c": [0], "d": "easy", "topic": "Hardware",
             "e": "The CPU executes program instructions."},
            {"t": "single", "q": "Which of these is volatile memory?", "o": ["RAM", "SSD", "Hard disk", "ROM"],
             "c": [0], "d": "easy", "topic": "Memory", "e": "RAM loses its contents when power is removed."},
            {"t": "short", "q": "How many bits make one byte?", "a": ["8", "eight"], "d": "easy",
             "topic": "Data", "e": "1 byte = 8 bits."},
            {"t": "single", "q": "Which protocol is used to load secure web pages?", "o": ["HTTPS", "FTP", "SMTP",
                                                                                         "SNMP"],
             "c": [0], "d": "easy", "topic": "Networking", "e": "HTTPS is HTTP over TLS encryption."},
            {"t": "truefalse", "q": "An operating system is an example of application software.", "c": False,
             "d": "easy", "topic": "Software", "e": "An OS is system software that manages hardware and resources."},
            {"t": "multiple", "q": "Which of the following are input devices?",
             "o": ["Keyboard", "Mouse", "Monitor", "Scanner"], "c": [0, 1, 3], "m": 2, "d": "easy",
             "topic": "Hardware", "e": "A monitor is an output device."},
            {"t": "single", "q": "What does SQL stand for?",
             "o": ["Structured Query Language", "Simple Query Logic", "Sequential Question Language",
                   "Standard Quality Language"], "c": [0], "d": "easy", "topic": "Databases",
             "e": "SQL is used to query and manage relational databases such as SQLite."},
            {"t": "fill", "q": "The binary number 1010 equals ___ in decimal.", "a": ["10", "ten"],
             "d": "medium", "topic": "Number systems", "e": "1×8 + 0×4 + 1×2 + 0×1 = 10."},
        ],
    },
    {
        "title": "Business Communication Essentials", "category": "Business & Management", "difficulty": "medium",
        "time": 8, "pass": 50, "tags": "communication,management,soft-skills", "release": "manual",
        "description": "Professional communication, email etiquette and management basics. Results are released "
                       "by the instructor after review.",
        "instructions": "6 questions. Your answers are recorded on submission; the instructor publishes results "
                        "later, and you will be notified.",
        "questions": [
            {"t": "single", "q": "Which is the most appropriate subject line for a formal email requesting leave?",
             "o": ["Leave request: 21–22 October", "hi", "URGENT!!!", "(no subject)"], "c": [0], "d": "easy",
             "topic": "Email", "e": "A clear, specific subject helps the reader understand and prioritise."},
            {"t": "truefalse", "q": "Active listening includes asking clarifying questions.", "c": True,
             "d": "easy", "topic": "Listening", "e": "Clarifying questions confirm understanding."},
            {"t": "single", "q": "SMART objectives are Specific, Measurable, Achievable, Relevant and…",
             "o": ["Time-bound", "Technical", "Tested", "Transparent"], "c": [0], "d": "easy", "topic": "Goals",
             "e": "SMART goals have a deadline: time-bound."},
            {"t": "multiple", "q": "Which of these are barriers to effective communication?",
             "o": ["Jargon", "Noise", "Clear feedback", "Assumptions"], "c": [0, 1, 3], "m": 2, "d": "medium",
             "topic": "Barriers", "e": "Feedback improves communication; the others are barriers."},
            {"t": "short", "q": "In a SWOT analysis, what does the 'O' stand for?", "a": ["Opportunities",
                                                                                         "Opportunity"],
             "d": "easy", "topic": "Strategy", "e": "Strengths, Weaknesses, Opportunities, Threats."},
            {"t": "single", "q": "Who is known as the father of scientific management?",
             "o": ["Frederick W. Taylor", "Henri Fayol", "Peter Drucker", "W. Edwards Deming"], "c": [0],
             "d": "medium", "topic": "Management", "e": "F. W. Taylor pioneered scientific management."},
        ],
    },
    {
        "title": "English Grammar Check", "category": "English & Communication", "difficulty": "easy", "time": 6,
        "pass": 50, "tags": "english,grammar",
        "description": "Articles, tenses, prepositions and common errors in everyday English.",
        "instructions": "6 quick grammar questions.",
        "questions": [
            {"t": "single", "q": "Choose the correct sentence.",
             "o": ["She doesn't like coffee.", "She don't like coffee.", "She not like coffee.",
                   "She doesn't likes coffee."], "c": [0], "d": "easy", "topic": "Agreement",
             "e": "Third-person singular uses 'doesn't' + base verb."},
            {"t": "fill", "q": "He is ___ honest man.", "a": ["an"], "d": "easy", "topic": "Articles",
             "e": "'Honest' begins with a vowel sound, so we use 'an'."},
            {"t": "single", "q": "What is the past tense of 'go'?", "o": ["went", "goed", "gone", "going"],
             "c": [0], "d": "easy", "topic": "Tenses", "e": "go → went → gone."},
            {"t": "truefalse", "q": "'Their', 'there' and 'they're' have the same meaning.", "c": False,
             "d": "easy", "topic": "Homophones", "e": "They sound alike but mean different things."},
            {"t": "single", "q": "Choose the correct preposition: The meeting is ___ Monday.",
             "o": ["on", "in", "at", "by"], "c": [0], "d": "easy", "topic": "Prepositions",
             "e": "We use 'on' with days of the week."},
            {"t": "short", "q": "Give the plural of 'child'.", "a": ["children"], "d": "easy", "topic": "Plurals",
             "e": "'Child' has the irregular plural 'children'."},
        ],
    },
]

FMEA_BASELINE = [
    ("Quiz submission", "Network drops during final submission", "Student loses answers / attempt not recorded",
     "Unstable mobile or Wi-Fi connection", "Autosave per answer, local backup, idempotent retry on submit",
     9, 4, 5, "Keep autosave + retry; monitor autosave success rate on Quality dashboard", 2, 2, 3),
    ("Quiz timing", "Timer manipulated on the client", "Unfair extra time; invalid results",
     "Timer enforced only in browser JavaScript", "Server-side deadline stored at attempt start + grace window",
     8, 3, 4, "Reject answers after deadline + grace; lazy server expiry", 8, 1, 2),
    ("Quiz submission", "Duplicate submission (double click / retry)", "Duplicate or inconsistent results",
     "Repeated POST requests", "Compare-and-set status update; unique attempt number constraint",
     7, 5, 3, "Idempotent submit endpoint returns the existing result", 7, 1, 2),
    ("Auto-grading", "Correct short answer marked wrong (spelling/case variant)", "Student under-scored",
     "Exact-match grading of free text", "Normalisation (case, spaces, punctuation) + multiple accepted answers",
     6, 6, 5, "Admin manual override with audit note; add accepted variants", 6, 3, 3),
    ("Quiz delivery", "Answer key exposed to the browser", "Cheating; results invalid",
     "API returns correct flags with questions", "Player API strips answer keys; review gated by release policy",
     9, 2, 6, "Code review + automated test asserting no key in payload", 9, 1, 2),
    ("Registration", "OTP brute-forced", "Account takeover of unverified email",
     "Short numeric codes without limits", "6-digit CSPRNG code, 10-min expiry, 5 attempts, hashed storage, rate limits",
     8, 3, 4, "Keep limits; monitor audit log for repeated failures", 8, 1, 3),
    ("Registration", "Verification email not delivered", "User cannot activate account",
     "SMTP misconfiguration / provider outage", "Clear error, resend with cooldown, admin test-email tool",
     6, 5, 3, "Configure SMTP with app password; document provider limits", 6, 3, 2),
    ("Question management", "Editing a question changes historical scores", "Disputes; loss of trust",
     "Results computed from live question rows", "Attempt snapshot freezes questions, options, marks and key",
     7, 4, 7, "Grading reproducibility check on Quality dashboard", 7, 1, 2),
    ("Data storage", "Database file lost or corrupted", "Loss of all users and results",
     "Disk failure / accidental deletion", "Automatic SQLite backups (interval configurable) + manual backups",
     10, 2, 6, "Store off-machine copies; test restore procedure", 10, 2, 3),
    ("Access control", "Student opens another student's attempt (IDOR)", "Privacy breach",
     "Missing ownership checks", "Ownership check on every attempt route; 404 for others",
     9, 3, 5, "Automated authorisation tests", 9, 1, 2),
    ("Profile", "Malicious file uploaded as profile photo", "Stored XSS / malware hosting",
     "Trusting extension or MIME type", "Pillow decode + re-encode to WebP, random names, size/pixel limits",
     8, 3, 5, "Keep uploads outside static folder; nosniff header", 8, 1, 2),
    ("Dashboards", "Slow dashboard under many attempts", "Poor user experience",
     "Unindexed aggregate queries", "Indexes on status/date columns; 30-second aggregate cache",
     4, 4, 4, "Monitor response times; paginate large tables", 4, 2, 3),
]

DEVELOPMENT_DEFECTS = [
    # (title, type, fishbone, severity, module, root cause, corrective, preventive)
    ("Leftover placeholder code in calendar view", "Other", "Software Code", "Low", "quiz.calendar_view",
     "Unfinished experimental timezone conversion left inside the view during drafting",
     "Removed dead code; event dates converted with the shared to_local() helper",
     "Code review checklist item: no placeholder/dead code before commit"),
    ("Preference checkboxes could not be switched off", "Validation", "Software Code", "Medium",
     "account.settings", "Incorrect condition meant absent checkboxes were never treated as False",
     "Checkbox values are applied only when the full settings form (hidden _full_form flag) is submitted",
     "Unit test for toggling every preference on and off"),
    ("App preview blocked inside embedding iframe", "Configuration", "Infrastructure", "Medium",
     "security headers", "X-Frame-Options/frame-ancestors were always SAMEORIGIN, including in development",
     "frame-ancestors is configurable (FRAME_ANCESTORS); SAMEORIGIN enforced by default in production",
     "Environment-specific security header matrix documented in DEPLOYMENT.md"),
    ("Session cookie not sent when site is embedded cross-site", "Authentication", "Infrastructure", "Medium",
     "config", "SameSite=Lax cookies are withheld in third-party iframes",
     "SESSION_COOKIE_SAMESITE made configurable (None + Secure for HTTPS embedding)",
     "Document cookie settings per environment in .env.example"),
    ("Fragile UTC conversion in admin date-range filter", "Data Integrity", "Software Code", "Low",
     "admin._date_range", "Timezone object re-instantiated via tz.__class__('UTC') instead of datetime.timezone.utc",
     "Replaced with datetime.timezone.utc", "Central time helpers in utils.py; review for ad-hoc tz code"),
    ("Every page crashed: current_user undefined inside imported macros", "UI / Layout", "Software Code", "Critical",
     "templates/macros", "Jinja macros imported with {% from %} do not receive the request context by default",
     "All macro imports use 'with context'", "Automated render test of every page for each role (pytest)"),
    ("Pagination macro failed to compile", "UI / Layout", "Software Code", "High", "templates/macros/ui.html",
     "Two **kwargs expansions in one url_for call, which Jinja does not support",
     "Merged keyword arguments into one dict before calling url_for",
     "Compile every template in the test suite before release"),
    ("Optional macro caller() guard failed under strict template checks", "UI / Layout", "Software Code", "Low",
     "templates/macros/ui.html", "Macros tested 'caller' truthiness instead of 'caller is defined'",
     "Use 'caller is defined'", "Strict-undefined template test mode (QM_STRICT_TEMPLATES=1)"),
    ("Redirect after marking notifications read trusted the Referer header", "Validation", "Software Code", "Medium",
     "student.api_notifications_read", "Unvalidated redirect target taken from request.referrer",
     "Redirect to the internal notifications page; admin redirects use same-host safe_back()",
     "Security review checklist: never redirect to unvalidated user-controlled URLs"),
    ("Quiz form crashed for new quizzes in strict template mode", "Validation", "Software Code", "Low",
     "admin.quiz_new", "View did not pass the 'problems' list that the template expects",
     "Pass an empty problems list for new quizzes", "Strict-undefined render tests for every admin page"),
    # --- found in the second build phase (TQM centre, extended test suite) ---
    ("Bug fix committed without re-running the test suite", "Other", "Process", "Medium", "workflow",
     "No rule required a green pytest run (normal + strict templates) before each commit",
     "Full suite re-run in both modes before the next commit; 130 tests passing at that point",
     "Pre-commit checklist in README: pytest -q and QM_STRICT_TEMPLATES=1 pytest -q must pass", "development"),
    ("Quality-goal feature mapping did not match the guideline wording", "Documentation", "People", "Medium",
     "TQM centre / SIPOC page", "Q01–Q20 mapping was first written from memory instead of the guideline PDF",
     "Q01–Q20 transcribed verbatim from the BBAT104 guideline into backend/quality_goals.py",
     "Traceability matrix always cites the source document; reviewed against the PDF", "development"),
    ("Test clients shared the logged-in user between independent sessions", "Authentication", "Software Code",
     "Medium", "tests/conftest.py", "Fixture kept one app context open, so Flask-Login's cached user in g leaked "
     "between test clients and hid redirect behaviour", "Requests now run outside a long-lived app context",
     "Auth tests assert role-based redirects with separate clients", "testing"),
    ("Dev-outbox notice revealed which emails have accounts", "Authentication", "Software Code", "Low",
     "auth.forgot_password", "Notice shown only when a reset email was actually written (existing accounts)",
     "Notice is shown for every request while in outbox mode", "Enumeration test compares responses", "testing"),
    ("Undefined icon names rendered a fallback glyph silently", "UI / Layout", "Software Code", "Low", "backend/icons.py",
     "Templates referenced 8 icons that icons.py did not define; icon() fell back to the help glyph",
     "Added the missing icons", "icon() records missing names; a test fails if any page requests one", "testing"),
    ("Generated Pareto/fishbone charts had broken and overlapping labels", "UI / Layout", "Software Code", "Low",
     "backend/services/charts.py", "Axis labels wrapped mid-word; fishbone cause labels crossed the neighbouring bone",
     "Word-safe wrapping; fishbone bones re-spaced with two-line cause labels",
     "Visual check of every generated PNG before release", "testing"),
]


def _ensure_categories() -> dict:
    cats = {c.name: c for c in Category.query.all()}
    for name, color, icon, desc in CATEGORIES:
        if name not in cats:
            c = Category(name=name, slug=slugify(name), color=color, icon=icon, description=desc)
            db.session.add(c)
            cats[name] = c
    db.session.flush()
    return cats


def _add_question(spec: dict, cat: Category) -> Question:
    q = Question(qtype=spec["t"], text=spec["q"], explanation=spec.get("e"), topic=spec.get("topic"),
                 difficulty=spec.get("d", "medium"), marks=float(spec.get("m", 1)),
                 negative_marks=float(spec.get("n", 0)), category_id=cat.id, tags=None)
    if spec["t"] in ("single", "multiple"):
        for i, text in enumerate(spec["o"]):
            q.options.append(AnswerOption(text=text, is_correct=i in spec["c"], position=i))
    elif spec["t"] == "truefalse":
        q.options.append(AnswerOption(text="True", is_correct=spec["c"] is True, position=0))
        q.options.append(AnswerOption(text="False", is_correct=spec["c"] is False, position=1))
    else:
        q.accepted_answers = json.dumps(spec["a"])
    db.session.add(q)
    db.session.flush()
    return q


def seed_content(force: bool = False) -> int:
    cats = _ensure_categories()
    if Quiz.query.count() and not force:
        db.session.commit()
        return 0
    created = 0
    now = utcnow()
    for spec in QUIZZES:
        if Quiz.query.filter_by(title=spec["title"]).first():
            continue
        cat = cats[spec["category"]]
        quiz = Quiz(title=spec["title"], slug=slugify(spec["title"]), description=spec["description"],
                    instructions=spec["instructions"], category_id=cat.id, difficulty=spec["difficulty"],
                    tags=spec.get("tags"), time_limit_minutes=spec["time"], pass_percentage=spec["pass"],
                    max_attempts=spec.get("max_attempts", 0), negative_marking=spec.get("negative", False),
                    shuffle_questions=spec.get("shuffle_q", False), shuffle_options=spec.get("shuffle_o", False),
                    result_release=spec.get("release", "immediate"), show_correct_answers=True,
                    show_explanations=True, featured=spec.get("featured", False), status="published",
                    published_at=now)
        db.session.add(quiz)
        db.session.flush()
        for pos, qs in enumerate(spec["questions"]):
            q = _add_question(qs, cat)
            db.session.add(QuizQuestion(quiz_id=quiz.id, question_id=q.id, position=pos))
        created += 1
    db.session.commit()
    return created


def seed_quality() -> dict:
    out = {"fmea": 0, "defects": 0, "pdca": 0, "changelog": 0}
    if not FMEAItem.query.count():
        for row in FMEA_BASELINE:
            (step, mode, effect, cause, controls, s, o, d, action, ns, no, nd) = row
            db.session.add(FMEAItem(process_step=step, failure_mode=mode, effect=effect, cause=cause,
                                    current_controls=controls, severity=s, occurrence=o, detection=d,
                                    recommended_action=action, owner="Project team", action_status="Implemented",
                                    new_severity=ns, new_occurrence=no, new_detection=nd))
            out["fmea"] += 1
    # Each development defect is inserted once. Titles already seeded are remembered in
    # settings so a defect an admin deletes is not re-created on the next start-up.
    import json as _json
    from .models import Setting
    marker = db.session.get(Setting, "seeded_defect_titles")
    seeded = set(_json.loads(marker.value)) if marker and marker.value else set()
    if marker is None:  # databases created before this marker existed
        seeded |= {t for (t,) in db.session.query(Defect.title).all()}
    for row in DEVELOPMENT_DEFECTS:
        title, dtype, fish, sev, module, root, corr, prev = row[:8]
        source = row[8] if len(row) > 8 else "development"
        if title in seeded:
            continue
        seeded.add(title)
        d = Defect(title=title, defect_type=dtype, fishbone_category=fish, severity=sev, module=module,
                   root_cause=root, corrective_action=corr, preventive_action=prev, status="Resolved",
                   source=source, resolved_at=utcnow(),
                   description="Recorded during the initial development and code review of QuizMaster v1.0.0.")
        db.session.add(d)
        db.session.flush()
        d.code = f"DEF-{d.id:03d}"
        out["defects"] += 1
    if marker is None:
        marker = Setting(key="seeded_defect_titles")
        db.session.add(marker)
    marker.value = _json.dumps(sorted(seeded))
    if not PDCAAction.query.count():
        db.session.add(PDCAAction(
            title="Guarantee zero lost submissions", stage="Check",
            objective="CTQ: every started attempt ends with a recorded, correctly graded result.",
            plan="Risk identified in FMEA (network drop during submission, RPN 180). Target: 0 lost submissions, "
                 "autosave success ≥ 99%, p95 submission processing < 500 ms.",
            do="Implemented per-answer autosave, browser-side backup of unsent answers, idempotent submit endpoint "
               "and server-side deadline with automatic expiry grading.",
            check="Monitor autosave success rate, submission latency control chart and grading reproducibility on "
                  "the Quality Center once real attempts are recorded.",
            metric_name="Autosave success rate (%)", baseline_value="Not measured (new system)", target_value="≥ 99",
            owner="Project team"))
        db.session.add(PDCAAction(
            title="Reduce short-answer grading disputes", stage="Plan",
            objective="Fewer manual overrides on short-answer / fill-in-the-blank questions.",
            plan="Track manual overrides in the audit log; add accepted answer variants for questions that are "
                 "overridden more than once.",
            metric_name="Manual overrides per 100 attempts", baseline_value="To be measured", target_value="< 2",
            owner="Project team"))
        out["pdca"] = 2
    if not ChangelogEntry.query.count():
        db.session.add(ChangelogEntry(
            version="1.0.0", title="Initial QuizMaster release", change_type="feature", released_on=date.today(),
            changes="\n".join([
                "Student and administrator portals with role-based access",
                "Registration with email OTP verification and password recovery",
                "Quiz builder, question bank (5 question types), CSV/JSON import",
                "Timed quiz player with autosave, server-enforced deadline and auto-grading",
                "Results, history, leaderboard, calendar and certificates",
                "Quality Center: defect log, check sheet, Pareto, Fishbone, FMEA, PDCA, control chart",
                "Reports export to CSV, Excel and PDF; automatic backups; audit trail",
            ])))
        out["changelog"] = 1
    db.session.commit()
    return out


def seed_all(force: bool = False) -> dict:
    created = seed_content(force=force)
    quality = seed_quality()
    return {"quizzes_created": created, **quality}
