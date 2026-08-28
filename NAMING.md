# Spider OS naming contract

These names are canonical and are used consistently in UI copy, documentation, APIs, and future features.

| Layer | Canonical name | Meaning |
| --- | --- | --- |
| Operating system | **Spider OS** | The whole operating system and product identity. |
| Desktop / shell | **The Web** | The user-facing desktop environment connecting every part of Spider OS. |
| Resident AI | **Webbie** | The always-available resident intelligence. |
| Personal memory | **Personal Knowledge Web** | Reviewable memory, provenance, relationships, observations, and inferences about the user. |
| Startup sequence | **Web Assembly** | Spider OS startup / session-entry sequence. |
| Security workspace | **Kali Bay** | Isolated authorized security-testing environment. |
| Major life areas | **Anchors** | Persistent domains such as School, Music, Work, Home, Finances, and Development. |
| Work objects | **Threads** | Tasks, notes, projects, events, ideas, conversations, research, and other work that can connect across Anchors. |

## Language examples

- “Webbie, what is due across my Anchors?”
- “Move this Thread to School.”
- “Connect this Music Thread to Development too.”
- “What did the Personal Knowledge Web remember about this?”
- “Open Kali Bay.”
- “Web Assembly complete.”

Internal database identifiers may retain legacy `space_id` names for schema compatibility, but user-facing language is **Anchor**. A migration can rename internal schema fields later without breaking stored data.
