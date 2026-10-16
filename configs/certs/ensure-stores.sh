#!/bin/bash
# Runs in the certs service at every `docker compose up`, before the webapp
# and the FHIR server start. The certgen image ships /etc/openelis-global with
# a keystore and truststore built with its own default passwords, and the
# named volume is seeded from it on the first start. This script makes the
# stores match the passwords in .env (KEYSTORE_PW is SSL_KEYSTORE_PASSWORD,
# TRUSTSTORE_PW is SSL_TRUSTSTORE_PASSWORD): stores that already open with
# them are left alone, so a restart changes nothing; stores that do not are
# rebuilt from the self-signed certificate, which itself is kept.
set -euo pipefail

STORE_DIR=/etc/openelis-global
CERT=/etc/ssl/certs/apache-selfsigned.crt
KEY=/etc/ssl/private/apache-selfsigned.key

: "${KEYSTORE_PW:?set SSL_KEYSTORE_PASSWORD in .env}"
: "${TRUSTSTORE_PW:?set SSL_TRUSTSTORE_PASSWORD in .env}"
export KEYSTORE_PW TRUSTSTORE_PW

mkdir -p "$STORE_DIR"

if [ ! -s "$CERT" ] || [ ! -s "$KEY" ]; then
    echo "certs: generating a self-signed certificate"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout "$KEY" -out "$CERT" \
        -subj "/C=US/ST=WA/L=Seattle/O=DIGI-UW/OU=DIGI/CN=localhost" \
        -addext "subjectAltName=DNS:*.openelis.org"
fi

opens_with() {
    keytool -list -storetype pkcs12 -keystore "$1" -storepass:env "$2" >/dev/null 2>&1
}

if [ -s "$STORE_DIR/keystore" ] && [ -s "$STORE_DIR/client_facing_keystore" ] \
    && opens_with "$STORE_DIR/keystore" KEYSTORE_PW \
    && opens_with "$STORE_DIR/client_facing_keystore" KEYSTORE_PW; then
    echo "certs: keystore opens with SSL_KEYSTORE_PASSWORD, keeping it"
else
    echo "certs: building the keystore with SSL_KEYSTORE_PASSWORD"
    openssl pkcs12 -export -inkey "$KEY" -in "$CERT" -out "$STORE_DIR/keystore.new" \
        -passout env:KEYSTORE_PW
    mv "$STORE_DIR/keystore.new" "$STORE_DIR/keystore"
    cp "$STORE_DIR/keystore" "$STORE_DIR/client_facing_keystore"
fi

if [ -s "$STORE_DIR/truststore" ] && opens_with "$STORE_DIR/truststore" TRUSTSTORE_PW; then
    echo "certs: truststore opens with SSL_TRUSTSTORE_PASSWORD, keeping it"
else
    echo "certs: building the truststore with SSL_TRUSTSTORE_PASSWORD"
    rm -f "$STORE_DIR/truststore.new"
    keytool -import -noprompt -alias oeCert -file "$CERT" -storetype pkcs12 \
        -keystore "$STORE_DIR/truststore.new" -storepass:env TRUSTSTORE_PW
    mv "$STORE_DIR/truststore.new" "$STORE_DIR/truststore"
fi

chmod a+rw "$STORE_DIR/keystore" "$STORE_DIR/client_facing_keystore" "$STORE_DIR/truststore"
echo "certs: stores ready in $STORE_DIR"
