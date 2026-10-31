#!/usr/bin/env bash
# Configureaza object storage-ul (Garage) pentru laborator:
#   secretele din garage/garage.toml, nodul, cheia de acces, bucket-ul
#   "imagini" si fisierul .env folosit de Jupyter.
#
# Se ruleaza O SINGURA DATA, din directorul proiectului:
#
#     bash comun/pregateste-garage.sh
#
# Scriptul e idempotent: rulat a doua oara, nu dubleaza nimic si reface .env
# din configuratia existenta.

set -euo pipefail
cd "$(dirname "$0")/.."

CHEIE_NUME="bdm-key"
BUCKET="imagini"
CONFIG="garage/garage.toml"

G() { docker compose --profile garage exec -T garage /garage "$@" 2>/dev/null; }
pas() { printf '\n==> %s\n' "$1"; }

if [ ! -f "$CONFIG" ]; then
  echo "Lipseste $CONFIG. Ai dezarhivat tot pachetul in ~/bdm-mediu?"
  exit 1
fi

# --- 1. Secretele din garage.toml ------------------------------------------
pas "Secretele de configurare"
if grep -q "INLOCUIESTE" "$CONFIG"; then
  RPC=$(openssl rand -hex 32)
  ADM=$(openssl rand -base64 32)
  # perl in loc de sed -i: aceeasi sintaxa pe Linux si pe macOS
  perl -pi -e "s|^rpc_secret = .*|rpc_secret = \"$RPC\"|" "$CONFIG"
  perl -pi -e "s|^admin_token = .*|admin_token = \"$ADM\"|" "$CONFIG"
  echo "    generate si scrise in $CONFIG"
else
  echo "    exista deja, le pastrez"
fi

# --- 2. Pornirea serviciului -------------------------------------------------
pas "Pornesc Garage"
docker compose --profile garage up -d garage >/dev/null
for i in $(seq 1 30); do
  if G status >/dev/null; then break; fi
  sleep 1
  if [ "$i" -eq 30 ]; then
    echo "    Garage nu raspunde dupa 30 de secunde."
    echo "    Vezi jurnalul: docker compose --profile garage logs garage"
    exit 1
  fi
done
echo "    raspunde"

# --- 3. Topologia: un singur nod, 10 GB --------------------------------------
pas "Aloc spatiul de stocare"
if G status | grep -q "NO ROLE ASSIGNED"; then
  NOD=$(G status | awk '/NO ROLE ASSIGNED/ {print $1; exit}')
  G layout assign -z lab -c 10G "$NOD" >/dev/null
  G layout apply --version 1 >/dev/null
  echo "    nodul $NOD configurat"
else
  echo "    deja configurat"
fi

# --- 4. Cheia de acces -------------------------------------------------------
pas "Cheia de acces"
if G key list | grep -q " $CHEIE_NUME\$"; then
  echo "    exista deja, o refolosesc"
else
  G key create "$CHEIE_NUME" >/dev/null
  echo "    creata"
fi
KEY_ID=$(G key list | awk -v n="$CHEIE_NUME" '$2 == n {print $1; exit}')
SECRET=$(G key info --show-secret "$KEY_ID" | awk '/Secret key:/ {print $3; exit}')

if [ -z "$KEY_ID" ] || [ -z "$SECRET" ]; then
  echo "    Nu am putut citi cheia. Rulati: docker compose --profile garage exec garage /garage key list"
  exit 1
fi

# --- 5. Bucket-ul si permisiunile --------------------------------------------
pas "Bucket-ul '$BUCKET'"
G bucket create "$BUCKET" >/dev/null || true
G bucket allow --read --write "$BUCKET" --key "$KEY_ID" >/dev/null
echo "    pregatit, cu drept de citire si scriere"

# --- 6. Fisierul .env, scris integral ----------------------------------------
pas "Fisierul .env"
cat > .env <<EOF
PGUSER=bdm
PGPASSWORD=bdm
PGDATABASE=bdm
S3_ENDPOINT=http://garage:3900
S3_ACCESS_KEY=$KEY_ID
S3_SECRET_KEY=$SECRET
S3_REGION=garage
S3_BUCKET=$BUCKET
EOF
echo "    scris (nu il editati de mana)"

cat <<FIN

Gata. Object storage-ul e configurat.

Recreati containerele, ca Jupyter sa citeasca noul .env:
    docker compose --profile db --profile vect --profile lab --profile garage up -d --force-recreate

Apoi testati mediul:
    docker compose --profile lab exec jupyter python /home/jovyan/proiect/comun/smoke_test.py
FIN
