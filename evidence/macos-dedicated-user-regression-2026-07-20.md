# Dedicated macOS canary regression — 2026-07-20

Physical provisioning exposed a release defect: `run-live-canary` rejected
every Darwin follower unconditionally, including a process running as the
approved dedicated `ai-token-canary` OS account. The published artifact could
therefore never complete its declared Mac follower leg.

Red commit `a30765f` added a contract that distinguishes a shared human login
from the exact dedicated kernel account and password-database home. It failed
because the runner had no OS-account identity check.

Green commit `0aa87f2` adds schema-2 Mac designation with `os_user`. Darwin
followers are admitted only when the configured user matches
`pwd.getpwuid(os.getuid()).pw_name`, the configured home matches that account's
real home, and the user is named `ai-token-canary*`. Schema 1, `kas`, and a
wrong home remain fail-closed. Linux schema-1 behavior is unchanged.

The targeted live-canary suite passed 13 tests. The complete release gate
passed 113 Python tests and four shell integration suites. No live credential
was read or written by these tests.
