# Spider OS safety model

## Authority levels

| Level | Examples | Default |
| --- | --- | --- |
| Observe | Search local items, summarize selected notes, show a calendar | Automatic |
| Draft | Draft an email, treatment-team note, paper outline, release plan | Automatic, unsent |
| Organize | Create a task, save a note, reschedule a personal item | Approval |
| External action | Send, publish, upload, invite, order, pay, or share | Explicit preview and approval |
| Destructive action | Delete, overwrite, revoke, uninstall, or erase | Strong confirmation and recovery path |
| High-stakes judgment | Diagnosis, disposition, observation level, emergency response, legal or financial decision | Never autonomous |

## Health and social-work boundary

Spider OS may support education, administrative workflow, documentation
templates, supervision preparation, resource lists, and evidence review. It
must not independently diagnose a person, decide suicide or violence risk,
select observation level, choose clinical disposition, or substitute for
facility policy, licensed supervision, emergency services, or direct clinical
assessment.

Protected client information is not entered into general AI memory. A future
clinical module requires a separate restricted vault, role-based access,
retention rules, redaction, audit review, and an approved deployment context.

## Recovery boundary

Recovery tools are supportive, not coercive. Check-ins remain private by
default. Spider OS does not shame, threaten, contact another person, or trigger
an intervention without a deliberately configured plan and immediate user
confirmation. Crisis interfaces must show direct human and emergency options.

## Security Lab boundary

Kali tooling is isolated from personal and restricted Spider OS spaces. It is
intended for defensive learning and authorized assessment. The AI does not
choose targets, scan third-party systems, obtain credentials, deploy
persistence, evade monitoring, or expand network access autonomously. Target
scope and any privileged or hardware access must be deliberately configured by
the user.

## Technical controls in 0.1

- Service binds only to loopback.
- Mutation requests require a per-run request token.
- Browser framing, cross-origin access, camera, microphone, location, and
  payment APIs are denied by response policy.
- AI receives a small allowlist of tools, never arbitrary shell access.
- AI writes are stored as proposals.
- Approval claims are atomic to prevent duplicate execution.
- Every mutation and decision is recorded in the local audit log.
- The data directory and database are owner-only.
- Atomic OS updates provide a known-good rollback deployment.

## Still required before production

- Independent security review and threat modeling
- Encrypted application vault using the operating-system keyring
- Backup, restore, export, and deletion workflows
- Strict verification policy for signed image updates
- Module permission manifests and a graphical permission manager
- Restricted-data retention settings
- Automated dependency and supply-chain scanning

## Always-on AI boundaries

"Always active" means the assistant service is continuously available, not that it
stores continuous microphone audio or receives unrestricted access to user activity.
Wake-word recognition must be local by default and discard non-activated audio.
Proactive adapters are opt-in per source. High-impact actions remain permissioned
through the Action Broker even when suggested proactively.


## Continuous screen awareness

Webbie may continuously inspect the active display context only when screen awareness is enabled. Processing is local by default. A persistent visible indicator is required whenever this capability is active. Users can exclude applications, windows, or Anchors. Continuous frames are ephemeral and are not written to history or memory unless the user explicitly saves or approves a derived memory.
