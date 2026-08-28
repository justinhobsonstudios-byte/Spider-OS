# Spider OS decisions

## Distribution base

Spider OS uses Aurora KDE on Universal Blue's bootc image pattern. This gives
the project an atomic host, transactional upgrades, rollback, and a polished
desktop while keeping Spider OS as an original image rather than a package pile
on a mutable security-testing distribution.

The default image targets Intel and AMD graphics. An Aurora NVIDIA Open image
can be selected at build time after the Dell GPU is identified.

Ubuntu Studio is a reference for future creative and low-latency audio setup,
not the host base. Kali is an isolated Security Lab container, not the desktop.

## AI model and authority

The first release is local-first and talks to Ollama over loopback. It remains
usable when no model is installed. Models may read data through a narrow tool
catalog, but model-requested writes become proposals that the user approves or
rejects. The model has no arbitrary shell tool.

## Life structure

Spider OS is a whole-life system. Broken Sorrow stays inside Music. The Social
Work Path is a permanent first-class space alongside school, present work,
personal life, recovery, creative work, finances, relationships, and home.

## Visual identity

The official mark is the user's original angular spider emblem, previously used
for their tattoo studio. Spider OS uses a clean geometric version for system
icons and a distressed version for large-format artwork. The emblem's canonical
color is crimson (`#DC143C`) on a near-black field. The supporting palette is black, graphite, and bone with crimson as the signature accent. The custom wordmark direction is architectural Gothic, distressed texture is reserved for artwork and key moments, the signature startup motion is Web Assembly, and the sound language is subtle/dark with restrained industrial weight. The canonical tagline is `YOUR LIFE. ONE WEB.`

## Security tools

Kali tools live in a rootless Podman container without host-directory mounts.
The default profile is headless and deliberately small. Security work is
restricted to systems the user owns or has explicit permission to test.

## Web continuous learning and authority

- Webbie continuously learns from Cory, study materials, and the internet.
- Internet learning is broad but source-scored and provenance-preserving.
- Learning updates Webbie's reviewable knowledge/memory, never silently retrains the base model or alters locked guardrails.
- Cory's explicit corrections outrank inferred preferences.
- Webbie uses graduated authority: observe -> routine automatic -> sensitive confirmation -> critical explicit approval.
