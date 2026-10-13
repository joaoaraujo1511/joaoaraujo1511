# Activity updates

GitHub Actions refreshes the profile daily at 05:17 UTC and on manual dispatch.
The monthly graph always starts in September 2025. Long histories continue on
additional rows. Only changed generated images and their README references are
committed; failed API requests leave the last published card in place.

## Credential

Create a classic personal access token owned by `joaoaraujo1511` at
https://github.com/settings/tokens with **only `read:user`** checked.
Do not grant `repo`, `user`, or `workflow`. The updater rejects broader tokens.
Store it as `METRICS_READ_TOKEN` in this repository's Settings → Secrets and
variables → Actions. The token's value is shown only once and cannot be retrieved
from an Actions secret. Replace the secret when rotating or regenerating it.
Expiration stops refreshes until the secret is replaced; it does not remove the
last published card. GitHub sends workflow failure notifications according to
your account notification settings.

## Privacy and permissions

The query asks for profile contribution counts and calendar day counts, never
private repository nodes, names, code, commit messages, or issue/PR content.
Only month totals and lifetime counts are published. These reveal activity volume
and timing, but no private project identities. Language shares use owned public
non-fork repositories only, excluding the profile repository, with GitHub's own
language colors. They describe repository bytes, not time spent programming.

The read token is given only to the collection step. GitHub's separate, temporary
`GITHUB_TOKEN` writes generated files to this profile repository. There are no
pull-request triggers, third-party metric services, dependencies installed with
pip, or raw response logs. The approved historical count floor prevents an
unexpected public-only response from replacing the full card; if GitHub rewrites
history, review the change before adjusting that floor in the script.

## Run or troubleshoot

Open Actions → Update profile activity → Run workflow. A missing, expired, wrongly
scoped or wrong-owner token fails without overwriting existing images. For a count
floor failure, verify that GitHub still provides the owner's private contribution
totals with `read:user`; do not solve this by granting private repository access.
Scheduled runs can be delayed by GitHub. Public repository schedules may be
disabled after 60 days without repository activity; daily generated commits
normally keep this one active. Re-enable it in Actions if GitHub disables it.

Tests: `python3 -m unittest discover -s tests -v`.
