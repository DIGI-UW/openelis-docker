# Deployment translation overrides

Files here override the UI's bundled translations, so this deployment can reword
any string in the interface without rebuilding the frontend image.

Nothing here takes effect until `OVERRIDE_DEFAULT_TRANSLATION=true` is set in
`../properties/SystemConfiguration.properties`. With it unset or false the UI
uses the shipped wording and does not even request these files.

## Files

One JSON file per locale, named exactly as the UI's own bundles — the
underscored form, which is also what Transifex emits:

```
en.json   fr.json   mg.json   fr_MG.json   en_GB.json   am_ET.json
```

Ship only the locales you customize. A locale with no file here keeps its
shipped bundle.

Overriding is **per message id**, not per file. `en.json` and `fr.json` here each
name a single id, so exactly one string changes and every other message keeps
the wording it shipped with. You never copy a whole bundle to change one line.

A regional locale also picks up its base language: a user on `fr_MG` gets
`fr.json` layered under `fr_MG.json`.

## How it is wired

`docker-compose.yml` mounts this directory into the frontend container at
`/usr/share/nginx/html/translation`, which the UI reads as
`/translation/<locale>.json`.

A change to a file that is already here takes effect on the next browser reload —
nginx serves it from disk on every request, so no restart and no rebuild. Adding
a locale file that was not here before is picked up the same way.

Point your own Transifex project at this directory to keep it in step with your
own translation workflow.
