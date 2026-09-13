---
name: system-design
description: Guide architecture and code design by clarifying requirements, boundaries, interfaces, lifecycle, trade-offs, risks, and verification before implementation.
---

# System Design

Use this skill when designing, extending, refactoring, or reviewing a non-trivial software system. Apply judgment proportionally: a small local change may need only a short design check, while a cross-component change needs an explicit design record.

## Core principles

1. **The system is more than the sum of its parts.** Check emergent behavior, global invariants, operational constraints, and failure propagation—not only whether each module works in isolation.
2. **Design requirements before solutions.** State users, use cases, constraints, quality attributes, assumptions, and measurable acceptance criteria before choosing technologies or writing code.
3. **Decompose complexity, preserve integration.** Split the system into cohesive components with clear responsibilities, while documenting how data, control, errors, and ownership flow across them.
4. **Manage interfaces explicitly.** Define API/event/CLI/file boundaries, schemas, preconditions, postconditions, versioning, compatibility, timeouts, retries, and error semantics. Do not rely on undocumented coupling.
5. **Consider the entire lifecycle.** Include construction, deployment, configuration, observability, upgrades, migration, rollback, backup/recovery, deprecation, and removal.
6. **Optimize trade-offs, not local metrics.** Compare alternatives across correctness, complexity, latency, throughput, cost, security, reliability, and maintainability; state what is being sacrificed and why.
7. **Manage uncertainty and risk.** Identify unknowns, dependencies, single points of failure, security/privacy concerns, and irreversible decisions. Use prototypes, feature flags, staged rollout, or reversible choices where useful.
8. **Verify and validate continuously.** Turn requirements into tests and checks at the right levels: unit, contract, integration, end-to-end, load, failure, and operational validation. Verify implementation against the design and validate the design against real usage.
9. **Prefer evolution over perfection.** Start with the smallest coherent architecture that leaves safe extension points. Record decisions and migration paths; avoid speculative abstractions.

## Workflow for coding tasks

Before implementation, produce a compact design note containing:

- problem statement, scope, non-goals, assumptions, and acceptance criteria;
- current system map and the proposed component/data-flow changes;
- interfaces and invariants, including compatibility and failure behavior;
- alternatives considered, key trade-offs, risks, and reversible decisions;
- verification plan and rollout/rollback or migration plan.

During implementation:

- keep module boundaries aligned with responsibilities and ownership;
- validate boundary inputs and make failure behavior explicit;
- keep configuration, side effects, and external dependencies visible;
- add tests and observability alongside the code, not as an afterthought;
- update the design note when implementation decisions or assumptions change.

When reviewing code, ask whether it satisfies the requirements and system invariants, whether interfaces are explicit and stable, whether lifecycle and failure modes are covered, and whether the change makes future evolution safer or harder. Report the highest-risk issues first and distinguish confirmed defects from unresolved design questions.
