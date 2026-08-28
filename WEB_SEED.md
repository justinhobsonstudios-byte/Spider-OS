# Web Seed

Spider OS ships with a versioned preload for Webbie's reviewable knowledge layer.

## What is preloaded

- Spider OS architecture, branding, privacy, authority, voice, presence and learning decisions.
- Webbie's identity, wake phrases, context-specific names, proactivity and idle-research rules.
- Education and study workflow preferences.
- Durable creative-project canon for Broken Sorrow, House of Echoes, Broken City, Therapy & Downz, The Gold Album and The Platinum Album.
- Software-building preferences and major project context.
- Recurring briefing interests and creative/technical interests.

## Provenance and confidence

Every seed record stores a source description, confidence value, category metadata, `preloaded=true`, and a seed version. User corrections should override inferred or stale information.

## Update behavior

The seed is idempotent. Database initialization records the installed seed version and will not duplicate already-applied seed data. Future seed versions can add or revise durable context.

## Deliberate exclusions

Secrets, credentials, account numbers, authentication material, and other data that should not become a bundled persistent memory are not included. Webbie may learn additional information later under the normal reviewable-memory and privacy policies.
