# Current Repository Audit vs Spider OS 1.0

This audit compares the existing repository on `main` to the Spider OS 1.0 master implementation specification.

## Executive summary

The current repository is a useful prototype and contains several concepts worth preserving, but it is architecturally incompatible with the Spider OS 1.0 direction in several major areas. It should be treated as a source of reusable logic and experiments, not as the final distribution architecture.

## Major mismatches

### 1. Distribution base

Current state:

- Aurora KDE / Universal Blue / bootc image model
- Fedora Atomic host
- bootc-image-builder / Anaconda ISO workflow

Spider OS 1.0 target:

- Ubuntu 26.04.1 LTS foundation
- selected Ubuntu Studio creative/audio stack
- KDE/Plasma foundation
- Spider-owned installer, packages, repository policy, recovery, and release images

Action:

- Retire the current bootc/Aurora release pipeline from the 1.0 path.
- Preserve it only as historical reference until the Ubuntu-based installer reliably replaces it.

### 2. The visible desktop

Current state:

- `index.html`, `app.js`, and `styles.css` implement The Web as an installable browser-style command center.
- The existing shell is useful as a UI prototype but still presents the old browser/dashboard architecture.

Spider OS 1.0 target:

- The Web is a native workspace shell over KDE/Plasma technologies.
- Browser technology may be used internally for specific surfaces, but Spider OS must not feel like a web page or localhost dashboard.

Action:

- Preserve the current UI as a design/reference prototype.
- Move workspace behavior and shell integration into `web/` with native desktop integration.

### 3. Spider Core naming and architecture

Current state:

- Documentation and UI refer to `Spider Core` / `Core online`.

Spider OS 1.0 target:

- The platform is named **The Weave**.
- The Weave contains the event bus, capability registry, permission broker, Context Engine, Knowledge Bridge, System Gateway, and audit layer.

Action:

- Migrate reusable core logic into the new `weave/` structure.
- Stop introducing new `Spider Core` identifiers.
- Preserve compatibility aliases only where temporarily necessary during migration.

### 4. Search and research

Current state:

- The repository includes local search/research experiments and a `ResearchEngine` concept.
- Search is still part of the old command-center architecture.

Spider OS 1.0 target:

- Search is named **Forage**.
- Deep external research is **Deep Forage**.
- Forage is a first-class system capability with local, semantic, knowledge, and external research layers.

Action:

- Move/rewrite search and research implementation under `forage/`.
- Preserve source scoring, provenance, and proactive research ideas where useful.

### 5. Knowledge model

Current state:

- SQLite-based life-space/item model and learning records.
- Existing Personal Knowledge Web concepts distinguish facts, observations, inferences, and corrections.

Spider OS 1.0 target:

- Relationship-aware graph of Anchors, Threads, projects, files, courses, songs, repositories, research, devices, people, and other typed objects.
- Provenance and privacy classes remain mandatory.

Action:

- Preserve provenance and correction semantics.
- Expand the storage model into `knowledge/` rather than coupling it directly to the old dashboard database.

### 6. Webbie

Current state:

- Resident service concept already exists.
- Wake phrases, screen-awareness restrictions, proactive behavior, local-first model usage, and approval concepts are present.

Spider OS 1.0 target:

- Webbie is mandatory, voice-first, resident, context-aware, and acts through The Weave.
- Default voice direction is female Australian.
- Webbie has Everyday, Creative, Developer, Research, Security, and System profiles.
- Actions must be verified after execution.

Action:

- Reuse resident-runtime concepts where practical.
- Move implementation into `webbie/`.
- Replace direct/legacy core coupling with The Weave capabilities.

### 7. Permissions

Current state:

- Observe/Routine/Sensitive/Critical graduated authority model.

Spider OS 1.0 target:

- Open/Contextual/Confirm/Elevated/Restricted capability classes.
- Workspace and project context are part of authorization decisions.

Action:

- Preserve the principle that unknown writes fail upward into confirmation.
- Implement the new capability-level model inside The Weave Permission Broker.

### 8. Kali Bay

Current state:

- Small/rootless Kali container.
- Host mounts and privileged capabilities restricted.

Spider OS 1.0 target:

- **Full Kali Linux toolset** in an isolated environment.
- Dedicated virtual disk, snapshots, controlled networking, explicit host/share/device passthrough, and Webbie Security profile.

Action:

- Replace the reduced-container design with the new Kali Bay VM/isolation architecture.
- Keep the existing least-privilege thinking for bridge design.

### 9. Branding

Current state:

- Crimson (`#DC143C`) is documented as canonical.

Spider OS 1.0 target:

- Purple/violet is the approved current Spider OS visual direction.
- Each major workspace has its own approved graphical wallpaper while preserving a unified dark Spider design language.
- The exact approved spider-and-dragon image is the canonical Kali Bay wallpaper.

Action:

- Retire crimson as the default system accent from the 1.0 branch.
- Add approved wallpaper assets to the theme package before ISO qualification.

### 10. Applications/workspaces

Current state:

- Life spaces and modules are represented mainly as command-center data categories.

Spider OS 1.0 target:

- Persistent graphical operating contexts: The Web, Forage, Studio, Art Lab, Dev Bay, Study, Media, Kali Bay, System, Recovery.
- Each workspace has its own apps, Webbie profile, layout state, widgets, capabilities, and wallpaper.

Action:

- Define workspace manifests under `web/workspaces/`.
- Move life/project categorization into Anchors/Threads rather than treating all categories as desktop modules.

## Build pipeline audit

### Current ISO workflow strengths

Keep the following ideas:

- repeatable CI-built ISO artifacts
- SHA-256 generation
- boot evidence capture
- serial-log failure detection
- explicit installer identity checks
- artifact retention controls

### Current ISO workflow blockers

The current build workflow:

- explicitly builds `ghcr.io/ublue-os/aurora:stable`
- builds a bootc image
- uses bootc-image-builder to generate an Anaconda installer ISO
- can fall back to `Spider_OS_v0.7_GitHub_ISO_Ready.zip` as source material

These mechanisms belong to the old architecture and must not become the Spider OS 1.0 foundation.

### Current smoke test limitation

The current smoke workflow boots the installer ISO, captures screens, checks that the VM remains running, and scans for fatal early-boot errors. It does **not** install Spider OS to the QEMU disk, eject the ISO, reboot from the installed system, reach The Web, or verify The Weave/Webbie/Forage.

Spider OS 1.0 qualification must perform the full install/reboot/verify sequence.

## Reusable current implementation areas

Candidate logic to preserve or port after review:

- local-first AI patterns
- resident Webbie service concepts
- action/audit concepts
- provenance-aware learning records
- source quality/confidence handling
- proactive alerts
- screen-context privacy restrictions
- life-space/item logic that can inform Anchors/Threads
- current web UI as a visual/interaction prototype

## Components that should be considered legacy for 1.0

- Aurora/Universal Blue/bootc distribution base
- `Containerfile` as the final OS image definition
- Anaconda/bootc ISO pipeline
- the ISO-ready ZIP as canonical source
- browser shell as the final native desktop
- `Spider Core` naming
- crimson as the default accent
- reduced Kali container
- smoke testing that stops before installed-system qualification

## Migration rule

Do not delete legacy code simply because it is old. First classify it as:

- PORT: reusable logic to move into the new architecture
- REFERENCE: useful design/prototype material that should remain until replacement lands
- RETIRE: superseded build/runtime code removable after the replacement passes qualification

No legacy component should be removed from `main` until the new Spider OS 1.0 path has a tested replacement.

## Immediate implementation milestones

1. Create the new top-level source structure.
2. Add workspace manifests and theme asset contract.
3. Add package/application manifest.
4. Define The Weave service API/capability contract.
5. Define the Ubuntu-based distro builder.
6. Produce a minimal installer ISO.
7. Add installed-system qualification.
8. Only then begin retiring the Aurora/bootc path.
