# Spider OS Naming Contract

These names are canonical across Spider OS. User-facing copy, code constants, desktop integration, services, documentation, and tests should use them consistently.

| Concept | Canonical name |
| --- | --- |
| Operating system | Spider OS |
| Desktop environment / shell | The Web |
| Resident AI | Webbie |
| Personal memory system | Personal Knowledge Web |
| Startup sequence | Web Assembly |
| Security workspace | Kali Bay |
| Connected area, singular | Anchor |
| Connected areas, plural | Anchors |
| Project / task / idea, singular | Thread |
| Projects / tasks / ideas, plural | Threads |

## Webbie invocation

Only these wake phrases are canonical:

1. `Hey Webbie`
2. `Webbie`
3. `Hey Web`
4. `Web`

`Web` is the short-call alias for Webbie. Service environment overrides must preserve all four phrases rather than narrowing the runtime defaults.

## Naming behavior

- Use **Spider OS** for the operating system as a whole.
- Use **The Web** for the desktop shell and primary connected interface.
- Use **Webbie** when referring to the resident AI by name.
- Use **Web Assembly** for startup and first-session assembly behavior.
- Use **Kali Bay** for the isolated security workspace.
- Use **Anchors** for connected areas of the user's work and daily world.
- Use **Threads** for individual projects, tasks, ideas, and ongoing work.

When terminology changes, update constants, web UI text, desktop files, services, documentation, and naming tests together so stale wording cannot quietly return.
