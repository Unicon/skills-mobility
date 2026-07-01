"""Resolution flow (design §5), scoped to what LearnCard REST supports.

store lookup -> Search Profiles by handle -> unresolved. There is no create
path: creating a learner's profile needs Profile-Manager provisioning, and
Search does not match email (both verified live in the #41 spike). Identifiers
that aren't a LearnCard handle (e.g. email) resolve to ``unresolved``.
"""

from __future__ import annotations

import logging

from learncard_api import LearnCardClient

from learncard_profile_resolver import resultmap, search
from learncard_profile_resolver.schemas import LearnerIdType, ResolvePayload, ResolveResponse
from learncard_profile_resolver.store import MappingStore

logger = logging.getLogger("learncard_profile_resolver")


def resolve(
    payload: ResolvePayload, store: MappingStore, client: LearnCardClient
) -> ResolveResponse:
    id_type = payload.learner_id_type
    id_value = payload.learner_id_value

    # 1. Mapping store: a previously resolved learner returns without any API call.
    cached = store.get(id_type, id_value)
    if cached is not None:
        return resultmap.stored(cached["profile_id"], cached["did"])

    # 2. Only a LearnCard handle (profileId) is resolvable via Search Profiles.
    if id_type is not LearnerIdType.PROFILE_ID:
        logger.info("unresolved: %s is not searchable in LearnCard", id_type.value)
        return resultmap.unresolved()

    # 3. Search, then keep only an exact handle match (search also matches
    #    displayName substrings, so a fuzzy hit is not a resolution).
    matches = search.search_profiles(client, id_value)
    match = next((m for m in matches if m.get("profileId") == id_value), None)
    if match is None:
        return resultmap.unresolved()

    profile_id = match["profileId"]
    did = match["did"]
    store.put(id_type, id_value, profile_id, did, "searched")
    return resultmap.searched(profile_id, did)
