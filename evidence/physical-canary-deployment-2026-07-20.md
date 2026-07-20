# Physical canary deployment — 2026-07-20

This is sanitized deployment evidence. No access token, refresh token, pairing
token, OAuth code, Keychain password, account cookie, or credential hash is
recorded here.

## Protected release

- Canonical commit: `17743041f1aa44561de190ac5216e8468689b810`
- Tree: `48a5861d387c92ecd62655c4ffcd636ac1653d06`
- Artifact: `ai-token-vault-17743041f1aa-7debc47fda04.zip`
- Archive SHA-256:
  `7debc47fda04bdde78754d1373599e49db8f8c152061597249dc4d63c8a1ac65`
- Protected main workflow run: `29779053567`, passed
- Release gate: 113 Python tests and four shell integration suites

The downloaded checksum and embedded manifest were verified before any host
received the bundle.

## farol leader

The release is selected from
`/home/kelvin/.ai-token-canary/release/releases/17743041f1aa-7debc47fda04`
under the mode-0700 isolated home. The isolated vault service is enabled and
healthy on loopback port 8232. Tailscale exposes only TCP 8232 to the private
fleet address; existing Serve routes were preserved. ACL scope is limited to
`claude:canary-claude`.

The installer selected the prior `0adb1ccd7813` release, promoted the protected
release, rolled back to the prior release, verified it, restored the protected
release, and verified it again. The daily canary timer and failure alert unit
exist but remain disabled until a real credential exists. Existing human
profiles and their live services were not selected or changed.

## agent-1 follower

The same artifact is selected from the isolated
`/home/kas/.ai-token-canary/release` root. The identical old/new rollback and
restore sequence passed. The follower paired to the isolated vault as
`canary-claude`; its mode-0600 configuration contains the private vault URL and
pairing token. Pull before leader publication failed closed with HTTP 404 and
created no local credential. The daily timer definition exists and remains
disabled. Existing human profiles were not changed.

## macOS follower

The dedicated standard account is `ai-token-canary`, UID 502, home
`/Users/ai-token-canary`, shell `/bin/zsh`. Password authentication and command
execution as that exact UID passed. Remote Login's ACL does not admit the
account, so deployment used an authenticated `su` transport through the
already-authorized `kas` account; the runner itself still executes as UID 502
and independently rejects any user/home mismatch.

The protected artifact is selected from
`/Users/ai-token-canary/.local/share/ai-token-release/releases/17743041f1aa-7debc47fda04`.
The same old/new rollback, verification, restore, and verification sequence
passed. The account owns a custom default Keychain at
`~/Library/Keychains/ai-token-canary.keychain-db`; the human login Keychain was
neither listed nor opened. Its private vault configuration is mode 0600 and the
pairing completed in explicit follower mode without reading or changing local
Claude credentials.

The first schema-2 preflight verified the pinned release, then failed at the
expected missing publication. Evidence
`20260720T212059.157435Z-Kelvins-MacBook-Air-follower-92724.json` is a regular
mode-0600 file owned by UID 502. It records `verify-release=0`, `pull=1`, and
`local.exists=false` both before and after. No credential was created.

macOS would not let a background `su` session bootstrap UID 502's LaunchAgent,
and its `crontab` install was rejected; neither partial scheduler was retained.
A login-session LaunchAgent therefore acts only as a dispatcher: at 01:20 it
invokes the password-fed UID switch and the canary-owned wrapper. A forced run
exited zero with the credential activation marker absent. The dispatcher is
loaded, contains no provider or vault credential, and every provider operation
still runs under UID 502 and the dedicated Keychain. Creating the mode-0600
activation marker is deferred until the first complete live pass.

## Identity boundary and remaining gate

No approved separate non-human Claude identity existed in the canonical wiki.
A plus-address login resolved to the existing human Futarchy Claude identity,
so authorization was declined. A dedicated domain address did not route to the
available mailbox. No OAuth grant was accepted, no credential was captured,
and all temporary Chrome profiles, cookies, and logs used for that check were
deleted afterward; that ephemeral cleanup is not recoverable.

Physical installation, rollback, vault pairing, Keychain isolation, and dormant
scheduling are complete. The live gate remains deliberately closed until a
separate non-human mailbox/account can complete Claude OAuth without billing or
credential reuse. Then the operator can publish once, run the leader and both
followers immediately, enable the three schedules, and begin the real 30-day
evidence clock.
