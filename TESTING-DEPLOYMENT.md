Testing uses the published-image stack in `/home/ubuntu/openelis-docker`.
Application changes land in `OpenELIS-Global-2/develop`; infrastructure changes
land in this repository's `main`. The application publication workflow passes
the five tested DockerHub image digests and their source commit to the reusable
`deploy-testing.yml` workflow. A missing manifest fails before touching the VM.

The workflow preserves the server's existing `.env` and database volumes,
fast-forwards infrastructure, pulls the specified digests, and checks every
running container's image ID. It then waits up to 300 seconds for HTTP 200 JSON
with `status: UP` at the configured health endpoint. Redirects, login HTML,
container start alone, and a health response from an earlier image cannot pass.
Status, bounded backend/proxy logs, readiness results, and any verified identity
are attached to the Actions run. Successful readiness publishes
`https://testing.openelis-global.org/__review/target.json` atomically. A failure
leaves the previous ready identity intact; it does not claim the failed
candidate is ready or automatically roll back database migrations.

The existing server `.env` must contain its certificate paths and names. A
conflicting local infrastructure change stops deployment for inspection; the
workflow never resets the checkout or replaces credentials. The testing base
overlay provides deployment identity. The additional Review overlay injects
the widget only when explicitly enabled.

To repeat a deployment, download `testing-deployment-manifest` from the
application's successful Publish Images run and supply its JSON as
`image_manifest` to this repository's Deploy workflow. This repeats the same
digests, rather than whichever images the mutable `develop` tags now name.

Review is configured separately in `openelis-review-tooling/main`. First deploy
its testing submission route, public tooling identity, and dedicated Grist
checklist. Then set `TESTING_REVIEW_ENABLED=true` in the application's Actions
variables, or set `enable_review=true` for a manual deployment. Before changing
containers, deployment verifies that the served widget bytes match the published
Review tooling hash and that the testing checklist contains steps. The ready
target then includes both the application and Review tooling commits.

For the analyzer cutover incident, apply the application fix through develop.
The corrected original migration preserves demonstrably empty analyzer drafts
and still rejects unmigrated configuration. Do not delete analyzer rows, clear
Liquibase checksums, or reset the testing database to bypass the guard.

Local contract validation:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```
