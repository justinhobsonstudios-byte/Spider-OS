# The Weave

The Weave is the internal Spider OS platform. It owns the event bus, capability registry, permission broker, Context Engine, Knowledge Bridge, System Gateway, and audit interface.

Planned modules:

- `bus/` — typed internal events and subscriptions
- `capabilities/` — app/service capability registration and invocation
- `permissions/` — Open, Contextual, Confirm, Elevated, Restricted policy
- `context/` — system/workspace/project/Thread/immediate context
- `knowledge/` — bridge to Forage and Personal Knowledge Web
- `system/` — guarded Linux/system integration
- `api/` — versioned local API used by The Web, Webbie, and Spider apps

Rule: Webbie and Spider-aware applications act through declared Weave capabilities instead of arbitrary shell execution.
