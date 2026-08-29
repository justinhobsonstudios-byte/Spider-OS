from __future__ import annotations

from typing import Final

APP_NAME: Final = "Spider OS"
DESKTOP_NAME: Final = "The Web"
AI_NAME: Final = "Webbie"
AI_ALIASES: Final = ("Webbie", "Web")
MEMORY_NAME: Final = "Personal Knowledge Web"
STARTUP_NAME: Final = "Web Assembly"
SECURITY_NAME: Final = "Kali Bay"
ANCHOR_NAME: Final = "Anchor"
ANCHORS_NAME: Final = "Anchors"
THREAD_NAME: Final = "Thread"
THREADS_NAME: Final = "Threads"
DEFAULT_WAKE_PHRASES: Final = ("Hey Webbie", "Webbie", "Hey Web", "Web")
DEFAULT_ADDRESS_NAMES: Final = {"default": "Cory", "studio": "Justin", "security-lab": "Spider"}
DEFAULT_HOST: Final = "127.0.0.1"
DEFAULT_PORT: Final = 8765

DEFAULT_SPACES: Final = [
    {
        "id": "today",
        "name": "Today",
        "description": "One honest view of what matters now.",
        "icon": "sun",
        "color": "#f3b562",
        "parent_id": None,
        "sort_order": 0,
    },
    {
        "id": "personal",
        "name": "Personal",
        "description": "Life administration, goals, documents, and private notes.",
        "icon": "person",
        "color": "#9a8cff",
        "parent_id": None,
        "sort_order": 10,
    },
    {
        "id": "recovery",
        "name": "Recovery",
        "description": "Check-ins, meetings, supports, plans, and reflection.",
        "icon": "pulse",
        "color": "#4cc9a4",
        "parent_id": None,
        "sort_order": 20,
    },
    {
        "id": "school",
        "name": "School",
        "description": "Courses, assignments, study sessions, and research.",
        "icon": "book",
        "color": "#52a8ff",
        "parent_id": None,
        "sort_order": 30,
    },
    {
        "id": "work",
        "name": "Work & Career",
        "description": "Current work, professional growth, credentials, and career planning.",
        "icon": "shield",
        "color": "#61d6d6",
        "parent_id": None,
        "sort_order": 40,
    },
    {
        "id": "behavioral-health-work",
        "name": "Behavioral Health Work",
        "description": "Administrative workflow, education, handoffs, and resources.",
        "icon": "shield",
        "color": "#61d6d6",
        "parent_id": "work",
        "sort_order": 41,
    },
    {
        "id": "social-work",
        "name": "Social Work Path",
        "description": "Graduate school, field placement, competencies, supervision, licensure, and continuing education.",
        "icon": "path",
        "color": "#77d6b8",
        "parent_id": "work",
        "sort_order": 42,
    },
    {
        "id": "creative",
        "name": "Creative",
        "description": "The parent space for visual art and making.",
        "icon": "spark",
        "color": "#e57ac8",
        "parent_id": None,
        "sort_order": 50,
    },
    {
        "id": "art",
        "name": "Art & Painting",
        "description": "Drawings, paintings, references, and works in progress.",
        "icon": "palette",
        "color": "#ef7b72",
        "parent_id": "creative",
        "sort_order": 51,
    },
    {
        "id": "tattoo",
        "name": "Tattoo Studio",
        "description": "Designs, sessions, consent workflow, and portfolio.",
        "icon": "needle",
        "color": "#df6e9d",
        "parent_id": "creative",
        "sort_order": 52,
    },
    {
        "id": "music",
        "name": "Music",
        "description": "Songs, recordings, instruments, releases, and shows.",
        "icon": "wave",
        "color": "#ef5350",
        "parent_id": None,
        "sort_order": 60,
    },
    {
        "id": "broken-sorrow",
        "name": "Broken Sorrow",
        "description": "Band songs, albums, archive, release work, and studio assets.",
        "icon": "heart",
        "color": "#d63f48",
        "parent_id": "music",
        "sort_order": 61,
    },
    {
        "id": "therapy-downz",
        "name": "Therapy & Downz",
        "description": "Gold, Platinum, songwriting, artwork, and release work.",
        "icon": "duo",
        "color": "#d7b85a",
        "parent_id": "music",
        "sort_order": 62,
    },
    {
        "id": "solo",
        "name": "Solo Work",
        "description": "Justin Therapy songs, albums, publicity, and performance.",
        "icon": "guitar",
        "color": "#b889ff",
        "parent_id": "music",
        "sort_order": 63,
    },
    {
        "id": "development",
        "name": "Development",
        "description": "Apps, code, experiments, and Spider OS itself.",
        "icon": "code",
        "color": "#79a8ff",
        "parent_id": None,
        "sort_order": 70,
    },
    {
        "id": "security-lab",
        "name": "Kali Bay",
        "description": "Authorized security testing in an isolated Kali environment, sealed from unrelated Anchors by default.",
        "icon": "terminal",
        "color": "#6fb7ff",
        "parent_id": "development",
        "sort_order": 71,
    },
    {
        "id": "finances",
        "name": "Finances",
        "description": "Budgets, bills, income, goals, and business records.",
        "icon": "wallet",
        "color": "#8acb6f",
        "parent_id": None,
        "sort_order": 80,
    },
    {
        "id": "relationships",
        "name": "Relationships",
        "description": "People, important dates, conversations, and shared plans.",
        "icon": "people",
        "color": "#ff8fa3",
        "parent_id": None,
        "sort_order": 90,
    },
    {
        "id": "home",
        "name": "Home",
        "description": "Household tasks, equipment, repairs, and daily logistics.",
        "icon": "home",
        "color": "#d7a86e",
        "parent_id": None,
        "sort_order": 100,
    },
]

ITEM_KINDS: Final = {"task", "note", "event", "project", "checkin"}
ITEM_STATUSES: Final = {"open", "active", "waiting", "done", "archived"}
SENSITIVITY_LEVELS: Final = {"standard", "private", "restricted"}
