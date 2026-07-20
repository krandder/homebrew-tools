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


@dataclass(frozen=True)
class State:
    canonical: Optional[Credential] = None
    follower: Optional[Credential] = None
    now: int = 0
    provider_cooldown_until: int = 0
    refresh_requests: int = 0


class Rejected(ValueError):
    pass


def _accept_generation(current, generation, refresh_token):
    if current is None:
        return
    if generation < current.generation:
        raise Rejected("stale generation")
    if generation == current.generation and refresh_token != current.refresh_token:
        raise Rejected("conflicting rotation")


def owner_sync(state, generation, refresh_token):
    _accept_generation(state.canonical, generation, refresh_token)
    return replace(state, canonical=Credential(generation, refresh_token, Authority.OWNER))


def vault_handoff(state, generation, refresh_token):
    _accept_generation(state.canonical, generation, refresh_token)
    return replace(state, canonical=Credential(generation, refresh_token, Authority.VAULT))


def explicit_takeover(state):
    if state.canonical is None:
        raise Rejected("no canonical credential")
    return replace(state, canonical=replace(state.canonical, authority=Authority.VAULT))


def refresh_success(state, generation, refresh_token):
    current = state.canonical
    if current is None or current.authority is not Authority.VAULT:
        raise Rejected("refresh attempted outside vault authority")
    if current.needs_relogin:
        raise Rejected("relogin required")
    if state.now < state.provider_cooldown_until:
        raise Rejected("provider cooldown active")
    if generation <= current.generation:
        raise Rejected("refresh did not advance generation")
    return replace(state, canonical=Credential(generation, refresh_token, Authority.VAULT))


def invalid_grant(state):
    current = state.canonical
    if current is None or current.authority is not Authority.VAULT:
        raise Rejected("invalid_grant outside vault authority")
    return replace(state, canonical=replace(current, needs_relogin=True))


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


def publish(state):
    current = state.canonical
    if current is None:
        raise Rejected("nothing to publish")
    follower = Credential(current.generation, None, Authority.FOLLOWER, current.needs_relogin)
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
    if state.follower is not None:
        if state.follower.refresh_token is not None:
            raise AssertionError("follower received a functional refresh token")
        if state.follower.authority is not Authority.FOLLOWER:
            raise AssertionError("published credential is not follower-authority")
        if state.canonical is None or state.follower.generation > state.canonical.generation:
            raise AssertionError("published generation is newer than canonical")
