# Modules

Drop an OpenELIS module JAR (built as described in the core's `docs/modules.md`)
in this directory and restart the webapp (`docker compose restart
oe.openelis.org`). OpenELIS reads every `*.jar` here at start-up: it validates
the manifest, runs the module's own migrations, registers its permissions and
menu entries and serves its pages. Rename a JAR to `<name>.jar.disabled` to
switch a module off, delete it to remove the module; the module's tables and
permission rows stay.

The directory is mounted read-only into the container at
`/var/lib/openelis-global/modules`. Module state and caches live inside the
container's own volumes.
