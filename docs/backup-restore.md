# Back up and restore an installation

Use the same distribution release for backup and restore. This procedure preserves
installation keys; it is not a version upgrade or key rotation. Run commands from
the installation directory. Keep the backup on encrypted, access-controlled storage.

## Create a consistent backup

Choose a new backup directory. Restrict it before writing credentials or data:

```sh
umask 077
backup="$PWD/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup"
chmod 700 "$backup"
docker compose stop proxy frontend.openelis.org oe.openelis.org fhir.openelis.org openelis-analyzer-bridge
docker compose exec -T db.openelis.org pg_isready -h 127.0.0.1 -U clinlims
```

Continue only if the database is ready. If it is stopped, start that service and
wait for readiness; do not proceed without a successful database dump.

```sh
docker compose exec -T db.openelis.org pg_dump -U clinlims -d clinlims \
  -Fc --no-owner --no-acl > "$backup/database.dump"
docker compose run --rm --no-deps -T --entrypoint sh certs -ec \
  'tar -C / -cf - etc/openelis-global etc/ssl/private/apache-selfsigned.key etc/ssl/certs/apache-selfsigned.crt' \
  > "$backup/security.tar"
docker compose run --rm --no-deps -T --entrypoint sh openelis-analyzer-bridge -ec \
  'tar -C /data -cf - openelis-analyzer-bridge' > "$backup/bridge.tar"
sudo tar --exclude='./configs/database/data' --exclude='./configs/logs' \
  -cpf - ./.env ./secrets ./configs ./docker-compose.yml ./deployment-manifest.json \
  > "$backup/configuration.tar"
```

Every command must succeed. A file left by a failed command is not a usable backup.
Record any site overlay and back it up too. If browser certificates live outside
this directory or use external mount paths, back up those paths separately using
their certificate manager's procedure. Retain the initial administrator password
file even when it is empty; Compose still mounts it.

After checking the archives, restart with `docker compose up -d --no-build` and
verify application readiness and login. Rehearse a restore before relying on the
backup. Database and security archives must be retained together.

## Restore into an empty replacement installation

Check out the original distribution release, with Docker Compose installed. Do not
start application services before restoring their security material. Restore the
configuration archive in that directory and keep its private permissions. Adjust
external mount paths deliberately if the replacement server uses different paths.

```sh
sudo tar -xpf /path/to/backup/configuration.tar -C .
docker compose pull
docker compose run --rm --no-deps -T --user 0:0 --entrypoint sh certs \
  -ec 'tar -C / -xpf -' < /path/to/backup/security.tar
docker compose run --rm --no-deps -T --user 0:0 --entrypoint sh openelis-analyzer-bridge \
  -ec 'tar -C /data -xpf -' < /path/to/backup/bridge.tar
docker compose up -d --no-build db.openelis.org
docker compose exec -T db.openelis.org pg_isready -h 127.0.0.1 -U clinlims
```

Wait for TCP database readiness, then restore the dump. The initializer uses a
temporary socket-only server; a successful local socket check is not sufficient. These commands are for an
empty replacement, not an existing lab database. The image seeds an initial schema
that can contain legacy objects absent from the backup. Recreate only this empty
replacement database before restoring; do not overlay the dump onto that seed.
Restore as the database administrator so the historical native functions can be
created, and retain the dump's object owners so the application can access its tables:

```sh
docker compose exec -T db.openelis.org dropdb -U postgres --if-exists clinlims
docker compose exec -T db.openelis.org createdb -U postgres -O clinlims -T template0 clinlims
docker compose exec -T db.openelis.org pg_restore -U postgres -d clinlims \
  --exit-on-error --no-acl < /path/to/backup/database.dump
docker compose up -d --no-build
docker compose ps
```

Verify login with the original account, access to retained records, readable saved
connection credentials, Bridge pairing and pending deliveries. The initializer
must retain the restored keys. Missing security material is a restore error; do
not delete volumes or generate new keys to work around it. Application version
upgrades and deliberate encryption-key conversion have separate procedures.
