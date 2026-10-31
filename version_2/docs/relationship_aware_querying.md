# Relationship-Aware Querying

## Scope

The query API can optionally receive an explicit seed entity (`entity_type` plus
`entity_id`) and include that user's stored relationships in the grounding
context. Entity resolution is not inferred from free-text query matching;
callers must resolve the entity before requesting graph context.

## Isolation and endpoint resolution

- Relationship retrieval is scoped by the authenticated `user_id`.
- Every endpoint label is loaded from the corresponding entity table with the
  same `user_id` filter.
- Edges whose polymorphic endpoint no longer resolves to a user-owned entity
  are omitted rather than shown with stale or ambiguous labels.
- Relationship provenance is loaded only from chunks whose parent document
  belongs to the requesting user.
- An invalid or foreign seed entity produces a generic HTTP 404 response so
  the API does not disclose whether another user's entity exists.

## Public query API

`POST /api/v1/query` accepts these optional request fields:

- `as_of`: an ISO-8601 timestamp with an explicit timezone or UTC offset.
  Naive timestamps are rejected with HTTP 422.
- `entity_type` and `entity_id`: an explicit seed entity pair. Supported types
  are `project`, `person`, `task`, `commitment`, `decision`, `risk`, `document`,
  and `memory`. Supplying only one field is rejected with HTTP 422.

The response includes a `relationships` array. Each item contains the stored
edge, resolved endpoint labels, validity boundaries, and attached source
chunks. Relationship edges use citations such as `[R1]`; attached source chunks
use citations such as `[R1-C1]`.

Each item in the `memories` array also exposes the memory's current `status`,
`valid_from`, and `valid_until`. These are persisted metadata, not a claim that
PAIS can reconstruct all historical state transitions.

## Valid-time semantics and limitations

When `as_of` is supplied, it is passed to both memory retrieval and relationship
retrieval. Stored validity intervals use `[valid_from, valid_until)` semantics:
the start is inclusive and the end is exclusive. Without `as_of`, memory
retrieval keeps the current active-only behavior; relationship retrieval uses
the current UTC instant for validity filtering.

Document-chunk retrieval is not temporally filtered because document chunks do
not currently have valid-time fields. Therefore, a historical query is not a
complete historical reconstruction across all evidence types.

Null validity boundaries are treated as candidate matches by the current
schema; they do not prove that a memory or relationship was valid indefinitely.
The query prompt explicitly marks incomplete memory and relationship validity
boundaries as unknown, and the API returns the stored memory boundaries so
clients can preserve that uncertainty. A memory's current lifecycle status is
also exposed, but must not be used as a substitute for historical validity.

The schema supports only one validity interval per directed relationship and
does not represent multiple disjoint validity periods or a full transaction-time
history. `as_of` is a valid-time query, not a reconstruction of exactly what
PAIS had recorded at that instant.

## Grounding rules

- A relationship without an attached source chunk is a stored graph assertion,
  not evidence that document provenance exists.
- Query generation must not infer additional edges or unsupported entity facts.
- The API does not add fuzzy entity resolution, multi-hop graph traversal, or a
graph framework.
- This stage requires no database migration.

## Regression coverage

The V2.3.5.4 regression suite covers inclusive `valid_from`, exclusive
`valid_until`, historical retrieval of memories whose current lifecycle status
is superseded or expired, user isolation, and explicit warnings for missing
validity boundaries. Run the focused query tests and the full suite with
`RUN_INTEGRATION_TESTS=1` before closing the milestone.
