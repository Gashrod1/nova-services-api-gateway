#!/usr/bin/env bash
# Rejoue les requêtes du TP contre la Gateway et masque le jeton dans la sortie.
# Usage : ./test-endpoints.sh [URL]   (défaut : http://localhost:3000)
set -euo pipefail
BASE="${1:-http://localhost:3000}"
set -a; source .env; set +a

run() {
    echo
    echo "\$ curl -i $1 $BASE$2" | sed "s/$GATEWAY_TOKEN/\$GATEWAY_TOKEN/g"
    eval curl -si "$1" "$BASE$2" | tr -d '\r' | grep -vi '^date:'
    echo
}

AUTH="-H \"Authorization: Bearer $GATEWAY_TOKEN\""
{
    echo "# Gateway : $BASE"
    run "" /users
    run "-H \"Authorization: Bearer wrong-token\"" /users
    run "$AUTH" /users
    run "$AUTH" /orders
    run "$AUTH" /profile/1
    run "$AUTH" /profile/999
    run "" /health
} | sed "s/$GATEWAY_TOKEN/\$GATEWAY_TOKEN/g"
