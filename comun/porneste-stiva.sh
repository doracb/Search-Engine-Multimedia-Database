#!/usr/bin/env bash
# Porneste o stiva izolata pentru un student, pe serverul de rezerva.
#
#   ./scripturi/porneste-stiva.sh 7 garage
#   ./scripturi/porneste-stiva.sh 7 garage jos      (opreste stiva)
#
# Fiecare student primeste un bloc de zece porturi, deci nu exista coliziuni.
# Volumele sunt separate automat, prin prefixul numelui de proiect.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Folosire: $0 <numar_student 1..99> [garage|seaweed] [jos]" >&2
  exit 1
fi

N="$1"
STOCARE="${2:-garage}"
ACTIUNE="${3:-sus}"

if ! [[ "$N" =~ ^[0-9]+$ ]] || (( N < 1 || N > 99 )); then
  echo "Numarul studentului trebuie sa fie intre 1 si 99." >&2
  exit 1
fi

BAZA=$(( 20000 + N * 10 ))

export COMPOSE_PROJECT_NAME="stud$(printf '%02d' "$N")"
export BIND_ADDR=127.0.0.1          # nimic expus public; accesul se face prin SSH
export PG_PORT=$(( BAZA + 0 ))
export QDRANT_PORT=$(( BAZA + 1 ))
export QDRANT_GRPC_PORT=$(( BAZA + 2 ))
export JUPYTER_PORT=$(( BAZA + 3 ))
export S3_PORT=$(( BAZA + 4 ))
export SEAWEED_FILER_PORT=$(( BAZA + 5 ))
export SEAWEED_MASTER_PORT=$(( BAZA + 6 ))
export GARAGE_ADMIN_PORT=$(( BAZA + 7 ))

if [[ "$STOCARE" == "garage" ]]; then
  export S3_ENDPOINT="http://garage:3900"
  export S3_REGION="garage"
else
  export S3_ENDPOINT="http://seaweedfs:8333"
  export S3_REGION="us-east-1"
fi

PROFILE=(--profile db --profile vect --profile lab --profile "$STOCARE")

if [[ "$ACTIUNE" == "jos" ]]; then
  docker compose "${PROFILE[@]}" down
  echo "Stiva $COMPOSE_PROJECT_NAME oprita. Volumele raman."
  echo "Pentru stergerea completa a datelor: docker compose ${PROFILE[*]} down -v"
  exit 0
fi

docker compose "${PROFILE[@]}" up -d

cat <<FIN

Stiva $COMPOSE_PROJECT_NAME a pornit. Stocare: $STOCARE

  Jupyter   localhost:$JUPYTER_PORT   (token: bdm)
  Postgres  localhost:$PG_PORT
  Qdrant    localhost:$QDRANT_PORT
  S3        localhost:$S3_PORT

Porturile sunt legate doar la interfata locala a serverului. Studentul se
conecteaza prin tunel SSH, de pe masina lui:

  ssh -N -L $JUPYTER_PORT:localhost:$JUPYTER_PORT \\
         -L $QDRANT_PORT:localhost:$QDRANT_PORT \\
         utilizator@server.universitate.ro

apoi deschide http://localhost:$JUPYTER_PORT/lab?token=bdm

FIN
