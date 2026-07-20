from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional


class Authority(Enum):
    OWNER = "owner"
    VAULT = "vault"
    FOLLOWER = "follower"


@dataclass(frozen=True)
class Credential:
    generation: int
    refresh_token: Optional[str]
    authority: Authority
    needs_relogin: bool = False
    expires_at: int = 3600


@dataclass(frozen=True)
class State:
    canonical: Optional[Credential] = None
    follower: Optional[Credential] = None
    now: int = 0
    provider_cooldown_until: int = 0
    refresh_requests: int = 0


class Rejected(ValueError):
    pass


TRANSITIONS = (
    "owner-sync",
    "vault-handoff",
    "takeover",
    "refresh-success",
    "invalid-grant",
    "transient-failure",
    "refresh-attempt",
    "rate-limit",
    "advance-time",
    "publish",
    "follower-refresh",
    "relogin-recovery",
)


def _accept_generation(current, generation, refresh_token):
    if current is None:
        return
    if generation < current.generation:
        raise Rejected("stale generation")
    if generation == current.generation and refresh_token != current.refresh_token:
        raise Rejected("conflicting rotation")


def owner_sync(state, generation, refresh_token, expires_at=None):
    _accept_generation(state.canonical, generation, refresh_token)
    expires_at = state.now + 3600 if expires_at is None else expires_at
    return replace(state, canonical=Credential(
        generation, refresh_token, Authority.OWNER, expires_at=expires_at,
    ))


def vault_handoff(state, generation, refresh_token, expires_at=None):
    _accept_generation(state.canonical, generation, refresh_token)
    expires_at = state.now + 3600 if expires_at is None else expires_at
    return replace(state, canonical=Credential(
        generation, refresh_token, Authority.VAULT, expires_at=expires_at,
    ))


def explicit_takeover(state):
    if state.canonical is None:
        raise Rejected("no canonical credential")
    return replace(state, canonical=replace(state.canonical, authority=Authority.VAULT))


def refresh_success(state, generation, refresh_token, expires_at=None):
    current = state.canonical
    if current is None or current.authority is not Authority.VAULT:
        raise Rejected("refresh attempted outside vault authority")
    if current.needs_relogin:
        raise Rejected("relogin required")
    if state.now < state.provider_cooldown_until:
        raise Rejected("provider cooldown active")
    if generation <= current.generation:
        raise Rejected("refresh did not advance generation")
    expires_at = state.now + 3600 if expires_at is None else expires_at
    return replace(state, canonical=Credential(
        generation, refresh_token, Authority.VAULT, expires_at=expires_at,
    ))


def invalid_grant(state):
    current = state.canonical
    if current is None or current.authority is not Authority.VAULT:
        raise Rejected("invalid_grant outside vault authority")
    return replace(state, canonical=replace(current, needs_relogin=True))


def relogin_recovery(state, generation, refresh_token, authority, expires_at=None):
    current = state.canonical
    if current is None or not current.needs_relogin:
        raise Rejected("recovery requires needsRelogin")
    if authority is Authority.FOLLOWER:
        raise Rejected("follower cannot recover canonical credentials")
    if generation <= current.generation:
        raise Rejected("recovery did not advance generation")
    expires_at = state.now + 3600 if expires_at is None else expires_at
    if expires_at <= state.now + 60:
        raise Rejected("recovery credential is expired")
    return replace(state, canonical=Credential(
        generation, refresh_token, authority, needs_relogin=False, expires_at=expires_at,
    ))


def transient_failure(state):
    return state


def refresh_attempt(state):
    current = state.canonical
    if current is None or current.authority is not Authority.VAULT:
        raise Rejected("refresh attempted outside vault authority")
    if current.needs_relogin:
        raise Rejected("relogin required")
    if state.now < state.provider_cooldown_until:
        raise Rejected("provider cooldown active")
    return replace(state, refresh_requests=state.refresh_requests + 1)


def rate_limited(state, retry_after):
    if retry_after < 1:
        raise Rejected("invalid retry-after")
    return replace(state, provider_cooldown_until=state.now + min(retry_after, 86400))


def advance_time(state, seconds):
    if seconds < 0:
        raise Rejected("time cannot move backwards")
    return replace(state, now=state.now + seconds)


def access_is_fresh(state, credential):
    return credential is not None and credential.expires_at > state.now + 60


def publish(state):
    current = state.canonical
    if current is None:
        raise Rejected("nothing to publish")
    if not access_is_fresh(state, current):
        raise Rejected("expired credential cannot be published")
    follower = Credential(
        current.generation,
        None,
        Authority.FOLLOWER,
        current.needs_relogin,
        current.expires_at,
    )
    return replace(state, follower=follower)


def follower_refresh(state):
    raise Rejected("followers never refresh")


def check_invariants(state):
    if state.refresh_requests < 0 or state.provider_cooldown_until < 0:
        raise AssertionError("refresh accounting cannot be negative")
    if state.canonical is not None:
        if not state.canonical.refresh_token:
            raise AssertionError("canonical credential must retain a real refresh token")
        if state.canonical.authority is Authority.FOLLOWER:
            raise AssertionError("canonical credential cannot have follower authority")
        if state.canonical.expires_at < 0:
            raise AssertionError("canonical expiry cannot be negative")
    if state.follower is not None:
        if state.follower.refresh_token is not None:
            raise AssertionError("follower received a functional refresh token")
        if state.follower.authority is not Authority.FOLLOWER:
            raise AssertionError("published credential is not follower-authority")
        if state.canonical is None or state.follower.generation > state.canonical.generation:
            raise AssertionError("published generation is newer than canonical")
        if state.canonical is None or state.follower.expires_at > state.canonical.expires_at:
            raise AssertionError("published expiry is newer than canonical")
