# PAIS V2 — Temporal Intelligence Contract

**Milestone:** V2.3.4.1 — Temporal Semantics and Consistency Rules  
**Status:** Specification  
**Scope:** Define temporal meaning and consistency requirements before implementing temporal behavior.

## 1. Purpose

PAIS stores facts, tasks, commitments, decisions, memories, and relationships that can change over time. Temporal intelligence must distinguish when information was recorded from when it applies, preserve uncertainty about dates and timezones, and support historical reasoning without treating the current state as the complete history.

This document establishes the semantics that later V2.3.4 milestones must follow.

This milestone does not change database models, generate migrations, or alter runtime behavior.

## 2. Core Temporal Concepts

### 2.1 Recorded Time

Recorded time describes when PAIS persisted or updated a record.

Examples:
- `created_at`: when the database record was created.
- `updated_at`: when the record was last updated.
- A source or provenance record's creation timestamp: when PAIS recorded that provenance link.

Recorded time is not proof of when a real-world fact became true.

For example, if PAIS records a commitment on October 20 that was agreed upon on October 15, its record creation time is October 20. The agreement date remains October 15 only if the source supports that date.

Do not infer a fact's valid time from its record creation time unless the domain explicitly defines that behavior.

### 2.2 Valid Time

Valid time describes when a fact or relationship applies in the real world or in the domain represented by PAIS.

Where supported by evidence, validity may have:
- `valid_from`: the beginning of the period during which a fact applies.
- `valid_until`: the end of that period.

Valid time and recorded time answer different questions:

- **Recorded time:** When did PAIS know or record this?
- **Valid time:** When did this fact apply?

A fact may be recorded after it became valid. A correction may also be recorded after the period it corrects.

Do not treat every existing entity as if it has a known valid-time interval. Add temporal meaning only where the domain and evidence support it.

### 2.3 Historical State

Historical state means the information that was valid or recorded at a particular point in time, subject to the temporal information PAIS actually retained.

A current status field alone cannot reconstruct every historical state.

For example, if a memory is marked `superseded`, that status describes its lifecycle in the current stored state. It does not prove that the memory was invalid before its replacement was recorded.

Historical queries must distinguish:
- what PAIS had recorded by a specified time, where recording history is available;
- what a fact is known to have been valid at a specified time;
- what remains uncertain because timestamps or historical versions are missing.

PAIS must not claim a complete historical reconstruction when the retained data cannot support it.

## 3. Temporal Interval Semantics

### 3.1 Boundary Convention

When a feature uses a validity interval, its convention is:

**`[valid_from, valid_until)` — start inclusive, end exclusive.**

A fact applies at its `valid_from` instant, if known, and no longer applies at its `valid_until` instant, if known.

For example, an interval from 10:00 to 11:00 includes 10:00 but excludes 11:00.

Use this convention consistently for temporal comparisons and interval overlap logic.

### 3.2 Missing Boundaries

A missing boundary means that the boundary is not specified in the stored data. It must not be silently replaced with a fabricated timestamp.

For interval evaluation, an unspecified boundary may be treated as an unbounded side for candidate matching only when the query semantics explicitly allow that interpretation. The result must not be presented as proof that the fact was valid indefinitely.

Keep these concepts distinct:
- a known start or end;
- an unspecified start or end;
- an explicitly open-ended period, if the domain later needs to represent that distinction.

If the implementation cannot distinguish an unknown boundary from an intentionally open-ended boundary, temporal results must preserve that limitation rather than claim certainty.

### 3.3 Interval Consistency

When both boundaries are known, `valid_until` must be strictly later than `valid_from`.

Reject invalid intervals rather than silently swapping, clamping, or correcting their boundaries.

An interval with equal boundaries is empty under the chosen convention and must not be accepted as a positive validity period unless a future domain-specific requirement explicitly defines otherwise.

## 4. Timezone and Timestamp Rules

### 4.1 Instants Must Be Unambiguous

A timestamp intended to represent an absolute instant must include timezone or UTC-offset information before conversion to an instant.

Examples of unambiguous timestamps include:
- `2026-10-31T12:00:00Z`
- `2026-10-31T17:30:00+05:30`

A timestamp such as `2026-10-31 12:00:00` has no timezone information by itself. Do not assume that it means UTC, the server's timezone, or the user's timezone.

### 4.2 Preserve Source Timezone Context When Available

When a source provides a timezone or UTC offset, retain enough information to interpret the timestamp correctly.

A timezone-aware database timestamp represents an instant; it does not necessarily retain the original timezone name supplied by the source.

If later features require the source's named timezone—for example, to interpret recurring local schedules or explain the original source context—store that information separately using an explicit, validated representation such as an IANA timezone identifier.

Do not introduce timezone metadata fields without establishing which entities and ingestion paths need them.

### 4.3 Unknown Timezones

When a source supplies a local date-time without timezone information:
- preserve the fact that the timezone is unknown;
- do not silently label the value as UTC;
- do not invent a timezone from the server, machine, user's presumed location, or project location;
- do not compare it with an absolute instant as if both were unambiguous;
- do not claim precise ordering across timezones unless the available data supports it.

A future implementation must choose an explicit representation and validation policy for such values. It must not rely on implicit database or host timezone behavior.

### 4.4 Date-Only Values

A calendar date without a time is not an absolute instant.

Do not automatically convert a date-only deadline or event into midnight UTC or midnight in an assumed local timezone. Keep date-only semantics distinct from timestamp semantics where the domain requires them.

The appropriate representation must be decided for each affected field before schema changes are made.

### 4.5 Existing Data

Do not reinterpret existing naive timestamps as UTC or convert them to another timezone without evidence of their original meaning.

Before changing a timestamp column's type or semantics:
1. Inspect the current schema and migration history.
2. Determine how existing values were written.
3. Establish whether the source timezone is known.
4. Define an explicit backfill or preservation strategy.
5. Test the migration against representative existing values.

If the original timezone cannot be recovered, the implementation must acknowledge that uncertainty instead of fabricating precision.

## 5. Entity and Relationship Semantics

### 5.1 Entity Lifecycle Is Not Validity

An entity's status and its valid-time interval are separate concepts.

For example:
- a task may be marked completed now;
- the task may have been open at an earlier point;
- the current status alone does not establish when the task was completed.

Do not infer historical status transitions unless the system retains evidence for them.

### 5.2 Relationship Lifecycle

A knowledge relationship currently represents a directed edge between two user-owned entities, with record timestamps and evidence provenance.

Future temporal relationship support must distinguish:
- when the relationship record was created or updated;
- when the relationship is known to apply;
- the evidence supporting the relationship;
- whether the relationship is currently considered applicable or was applicable historically.

Adding validity intervals must not change the existing directed-edge identity or silently turn a duplicate relationship into a different relationship.

The same logical relationship may have evidence recorded at different times. Adding evidence must not automatically rewrite its validity interval unless an explicit, tested domain rule requires it.

### 5.3 Relationship Removal and Correction

Absence of a relationship is not, by itself, evidence that the relationship never existed.

If a relationship is later corrected or no longer applies, the system must not imply a historical conclusion that the stored data cannot establish.

The specific mechanism for ending, correcting, or versioning relationships is deferred to the implementation milestone. This contract does not authorize a graph redesign or a change to relationship identity.

### 5.4 Provenance

Temporal conclusions should remain traceable to their supporting evidence wherever provenance is available.

The time when PAIS attached a provenance link is not necessarily the time when the source event occurred.

Do not use provenance creation timestamps as substitutes for source-event timestamps.

## 6. Memory Supersession and Expiration

Memory lifecycle status and memory validity are related but distinct.

- `active`, `superseded`, and `expired` describe the stored memory lifecycle.
- `valid_from` and `valid_until` describe the period during which the memory's content applies, when known.
- `created_at` and `updated_at` describe the record's persistence lifecycle.
- `supersedes_id` links a memory to the memory it replaces, when applicable.

Marking a memory as superseded must not erase the fact that its content may have been valid earlier.

A historical memory query must not equate "not currently active" with "never valid at the requested time."

Likewise, a memory marked active must not automatically be treated as historically valid for every past date. Historical applicability must use available validity and lifecycle evidence.

If the available fields are insufficient to answer a historical question reliably, PAIS should expose that limitation rather than produce an unsupported historical answer.

## 7. Temporal Query Requirements

Future temporal queries must follow these requirements:

1. **Explicit reference time:** Use an explicit `as_of` instant when historical evaluation is requested.
2. **Unambiguous instants:** Validate timezone awareness before comparing timestamps intended to represent absolute instants.
3. **Consistent intervals:** Use the `[start, end)` convention.
4. **No fabricated precision:** Preserve unknown boundaries, timezones, and date-only semantics.
5. **Historical versus current state:** Do not use current status as a substitute for historical state.
6. **Evidence-aware conclusions:** Preserve source provenance when temporal conclusions depend on source evidence.
7. **User isolation:** Apply the existing user-scoping guarantees to temporal retrieval and relationship traversal.
8. **Deterministic behavior:** Equivalent inputs and stored state must produce consistent temporal filtering results.
9. **Explicit limitations:** Do not claim full temporal reconstruction when the required history was not retained.
10. **No implicit migration:** Existing data must not be reinterpreted without a reviewed migration and data-preservation strategy.

## 8. Out of Scope

This milestone does not:
- add relationship validity columns;
- change task or commitment deadline column types;
- add timezone columns or alter timestamp storage;
- change memory retrieval or supersession behavior;
- introduce temporal versions of entities;
- add event sourcing, a graph framework, or a shared entity registry;
- create or apply Alembic migrations;
- promise full bitemporal history.

These decisions require subsequent implementation milestones and repository-specific review.

## 9. Acceptance Criteria

V2.3.4.1 is complete when:

- [ ] Recorded time, valid time, and historical state are defined distinctly.
- [ ] Validity intervals consistently use `[valid_from, valid_until)`.
- [ ] Missing boundaries and unknown timezones are not treated as known facts.
- [ ] Absolute instants, date-only values, and local date-times are distinguished.
- [ ] The limitations of timezone-aware database timestamps are documented.
- [ ] Memory supersession is explicitly distinguished from historical validity.
- [ ] Relationship validity and provenance semantics are documented.
- [ ] The scope excludes schema changes and migrations at this stage.
- [ ] The document has been reviewed against the current V2.3.3 codebase.