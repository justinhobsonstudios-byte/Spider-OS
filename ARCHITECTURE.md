# Spider OS architecture

## Product boundary

Spider OS is an image-based Linux distribution and personal command layer. It
does not replace the Linux kernel. Reinventing hardware drivers would add years
of work while producing no benefit to the user's actual life.

The distribution derives from the Aurora KDE workstation in the Universal Blue
ecosystem. Fedora Atomic and bootc provide hardware support, image delivery,
transactional updates, and rollback. KDE Plasma supplies the desktop. Spider OS
supplies the identity, command center, AI service, life-space model,
permissions, integrations, creative configuration, and signed image.

Ubuntu Studio remains a workflow reference for audio, PipeWire/JACK,
low-latency configuration, and curated creative tools. Spider OS does not clone
Ubuntu Studio or inherit its branding.

### Creative workstation layer

The host image supplies PipeWire's JACK compatibility layer, RtKit scheduling,
and Qpwgraph routing. Creative desktop applications remain outside the atomic
deployment as per-user Flatpaks grouped into audio, visual, video, and
publishing packs. The `spider-creative-pack` installer performs the explicit,
reviewable installation from Flathub. Ubuntu APT repositories are never added
to the Fedora host.

## Layers

1. Atomic Linux foundation
   - Aurora KDE / Universal Blue image
   - Fedora Atomic deployment and rollback
   - KDE Plasma desktop
   - PipeWire audio
   - Flatpak and containers for most applications
2. Spider Core
   - Local HTTP service bound only to loopback
   - SQLite personal data store with owner-only permissions
   - Life-space and item model
   - Audit log
3. Intelligence
   - Ollama-compatible local model endpoint
   - Explicit tool catalog
   - Read actions separated from write actions
   - Approval broker for AI-originated changes
4. Command center
   - Responsive installable web application
   - Today view, anchors, threads, search, projects, check-ins, Web, approvals
5. Modules
   - Personal
   - Recovery
   - School
   - Work & Career
   - Behavioral Health Work
   - Social Work Path
   - Creative, Art & Painting, Tattoo Studio
   - Music, Broken Sorrow, Therapy & Downz, Solo Work
   - Development
   - Security Lab with an isolated Kali container
   - Finances
   - Relationships
   - Home

## Why an image-based base

An AI-integrated operating system needs a reliable escape hatch. System updates
are assembled as complete images rather than mutating each computer one package
at a time. A failed update can return to a prior known-good deployment.
Applications and personal data stay separate from the system image, reducing
configuration drift.

## Why local first

The system will hold unusually sensitive material. A local model keeps ordinary
assistant traffic on the user's machine and allows the dashboard to operate
offline. Cloud models can later be optional providers, scoped by anchor and
disabled for restricted records.

## Data model

Spaces define boundaries and hierarchy. Items are intentionally general:
tasks, notes, projects, events, and check-ins share scheduling, priority,
status, sensitivity, and audit behavior. Specialized modules can extend item
metadata without fragmenting the core.

AI calls never write directly. The action broker stores a proposal, presents
the exact requested operation, and requires approval. The proposal is claimed
atomically before execution to prevent duplicate application.

## Integration contract

Future modules communicate with Spider Core through versioned local APIs and
declared permissions. A module must state whether it can read, write, launch,
send, publish, delete, spend, access health information, or use a network.
Unknown permissions are denied.

## Security Lab

Kali tools run in a rootless container derived from Kali's official image. The
container receives a separate home directory and does not mount Spider OS data
or the user's normal home by default. Hardware passthrough, host networking,
privileged execution, raw sockets, and shared folders require separate,
purpose-specific approval. The lab is for systems the user owns or is
explicitly authorized to assess.

## Resident Webbie intelligence

Webbie is a persistent user-session service, not merely a dashboard chat panel.
`spider-ai-resident.service` starts automatically and remains active for the whole
session. It coordinates presence, wake-word adapters, approved event sources, and
proactive suggestions while the core command center owns memory and action approval.

### Presence model

- Starts automatically with Spider OS and restarts if it crashes.
- Uses the local wake phrases **Hey Webbie**, **Webbie**, **Hey Web**, and **Web**.
- Wake-word detection is intended to run locally; ambient audio is never stored by
  the resident service.
- Proactive intelligence may read only explicitly approved event sources.
- Model-initiated writes continue through the Action Broker and require approval
  according to policy.
- The resident has no arbitrary shell execution capability.
- The microphone, proactive observation, and individual event sources must each be
  independently pausable.

Screen awareness is locally processed by default, visibly indicated, excludes selected applications, and does not archive frames unless explicitly enabled.

This produces a JARVIS-like presence without making invisible surveillance the price of convenience.

## Continuous learning

Webbie has three persistent learning streams: **user**, **study**, and **internet**. Learning writes reviewable knowledge records with source provenance, confidence, timestamps, and metadata. Corrections from Cory take precedence over Webbie's inferred preferences. Internet learning uses broad source access with source-quality scoring. It updates Webbie's knowledge store, not the base model weights or locked safety/personality rules.

## Graduated authority

Webbie uses four authority tiers:

1. **Observe** — read/search/context only; automatic.
2. **Routine** — local, reversible organization and UI actions; automatic.
3. **Sensitive** — private data, external communication, significant settings, or higher-impact actions; confirmation required.
4. **Critical** — destructive, financial, security-critical, credential, legal, or irreversible actions; explicit approval at execution time.

Unknown writes fail upward into confirmation rather than downward into autonomy.

## Personal Knowledge Web

The Personal Knowledge Web is distinct from generic learned knowledge. Each entry
is explicitly typed as a **fact**, **observation**, **inference**, or **correction**.
Inferences require evidence references and are never promoted to facts merely by
confidence. Corrections append a new provenance-bearing record instead of silently
rewriting history.

## Research Web

`ResearchEngine` gives Webbie an autonomous, reviewable research loop:

1. Notice or receive a knowledge gap.
2. Queue a research question with rationale, Anchor and priority.
3. Search through the local SearXNG service.
4. Preserve source URL, title, snippet, retrieval time and source-quality score.
5. Create a confidence-bearing finding.
6. Surface higher-value findings through the proactive alert layer.

The resident process may derive conservative questions from high-priority active
Threads even when the language model is offline. Search failures do not terminate
the resident process.

## Proactive awareness

`ProactiveEngine` scans due Threads and sourced research findings. Due-within-72h,
due-within-24h and overdue states are deduplicated into reviewable alerts. Important
and worth-knowing alerts are eligible for Webbie's attention cue and spoken summary;
quiet findings remain in the feed.

## Screen context

`ScreenContextBuffer` accepts only derived current-window context. It is process
memory, not a screenshot history. Raw pixels are never written by this component.
Sensitive markers such as password/authentication/incognito windows force exclusion.
The buffer disappears when Spider Core restarts unless the user explicitly chooses
to save a derived memory through a separate action.
