# skills-mobility-events

Shared **event contracts** for the Skills Mobility POC: the Canvas Live
Events-style envelope (`{ metadata, body }`) and the per-event-type body
schemas. The Mock Event Producer owns these; downstream consumers (Event
Consumer, Context Builder) treat them as the contract for events on the bus.

- `models.py` — `EventType`, `LiveEventEnvelope`, `EventMetadata`, body models, and the Canvas `event_name` mapping.
- `ids.py` — `event_id` / `emission_id` / `correlation_id` and UTC timestamp helpers.

See [docs/2_requirements/mock-event-producer.md](../../docs/2_requirements/mock-event-producer.md) §5.2 and [docs/3_design/mock-event-producer.md](../../docs/3_design/mock-event-producer.md) §3.
