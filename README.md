# Baze de date multimedia — mediul de laborator

Tot ce rulați în laboratoare stă în acest director: patru servicii în Docker (PostgreSQL cu pgvector, Garage pentru imagini, Qdrant, Jupyter) și scripturile pentru L1–L7.

Fișele de laborator (`L1.md` … `L7.md`) și fișierele precalculate le primiți pe Drive, în ziua fiecărui laborator. Unde le puneți: vezi secțiunea *Fișele și fișierele primite*.

---

## Ce vă trebuie

- Windows cu **WSL 2 și Ubuntu**, **Docker Desktop** și **VS Code** cu extensia *WSL* (pe macOS sau Linux: Docker și un terminal);
- **8 GB RAM**, **15 GB liberi** pe disc;
- setul de date **Fashion Product Images (Small)** de pe Kaggle;
- imaginile Docker de pe stick-ul de la laborator (sau conexiune la internet, pentru construirea lor).

Toate comenzile de mai jos se dau în **terminalul Ubuntu din VS Code**: `F1` → *WSL: Connect to WSL*; în colțul din stânga jos trebuie să scrie **WSL: Ubuntu**. Nu în PowerShell și nu în Command Prompt.

`NUME` este numele vostru de utilizator din Windows. Îl aflați cu `ls /mnt/c/Users/`.

---

## Prima pornire (o singură dată, ≈ 30 de minute)

**1. Dezarhivați pachetul în WSL**, nu pe `C:` și nu în OneDrive sau Google Drive:

```bash
cd ~
unzip /mnt/c/Users/NUME/Downloads/bdm-mediu-studenti.zip
cd ~/bdm-mediu
ls
```

Trebuie să vedeți `comun`, `garage`, `jupyter`, `L1-ingest` … `L7-hibrid`, `date`, `artefacte`, `docker-compose.yml`.

**2. Puneți setul de date în `date/`:**

```bash
cd ~/bdm-mediu/date
unzip -q /mnt/c/Users/NUME/Downloads/archive.zip
ls
ls images | wc -l
```

Trebuie să vedeți `styles.csv` și `images`, cu aproximativ 44.000 de imagini. Dacă dezarhivarea a creat un director în plus, mutați `styles.csv` și `images/` direct în `date/`.

**3. Încărcați imaginile Docker.** De pe stick (rapid):

```bash
docker load -i /mnt/d/bdm-imagini.tar
```

(`D:` e litera stick-ului; poate fi alta.) Fără stick, le construiți voi; durează 20–30 de minute și descarcă aproximativ 2 GB:

```bash
cd ~/bdm-mediu
docker compose --profile lab build jupyter
```

**4. Configurați object storage-ul (Garage):**

```bash
cd ~/bdm-mediu
bash comun/pregateste-garage.sh
```

Scriptul generează cheile, creează bucket-ul `imagini` și scrie fișierul `.env`. La final afișează `Gata.`

**5. Porniți tot și testați:**

```bash
docker compose --profile db --profile vect --profile lab --profile garage up -d --force-recreate
docker compose ps
docker compose --profile lab exec jupyter python /home/jovyan/proiect/comun/smoke_test.py
```

Trebuie să vedeți patru servicii pornite și, la final, `REZULTAT: toate componentele functioneaza.`

---

## În fiecare ședință

Porniți **Docker Desktop** și așteptați *Engine running*, apoi:

```bash
cd ~/bdm-mediu
docker compose --profile db --profile vect --profile lab --profile garage up -d
```

| Ce | Unde |
|---|---|
| JupyterLab | http://localhost:8890/lab?token=bdm |
| Consola Qdrant | http://localhost:6333/dashboard |
| PostgreSQL (DBeaver, pgAdmin) | `localhost:5432`, baza `bdm`, utilizator `bdm`, parola `bdm` |

La final:

```bash
docker compose --profile db --profile vect --profile lab --profile garage stop
```

---

## Fișele și fișierele primite

Le descărcați de pe Drive (ajung în *Downloads*) și le mutați în proiect:

| Fișierul | Unde |
|---|---|
| `L1.md` … `L7.md` | în directorul laboratorului: `L1-ingest/`, `L2-stocare/`, `L3-descriptori/`, `L4-indexare/`, `L5-clip/`, `L6-vectoriale/`, `L7-hibrid/` |
| `PROIECT.md` | `~/bdm-mediu/` |
| `PLAN.md` | `~/bdm-mediu/proiect/` |
| fișierele precalculate (`.npz`, `.csv`) | **`~/bdm-mediu/artefacte/`**: obligatoriu aici, scripturile le caută acolo |
| `metrici.py` (după L3) | `~/bdm-mediu/comun/` |

Exemplu:

```bash
cp /mnt/c/Users/NUME/Downloads/L3.md ~/bdm-mediu/L3-descriptori/
cp /mnt/c/Users/NUME/Downloads/L3_*.* ~/bdm-mediu/artefacte/
```

Fișa se citește cel mai comod în VS Code: deschideți-o din panoul din stânga, apoi `Ctrl+Shift+V` pentru vizualizarea formatată.

Fișierul `rezultate.csv` se completează singur la fiecare laborator. **Nu îl ștergeți:** e tabelul de rezultate din proiect.

---

## Probleme frecvente

| Mesajul | Cauza | Ce faceți |
|---|---|---|
| `no configuration file provided` | nu sunteți în proiect | `cd ~/bdm-mediu` |
| `Cannot connect to the Docker daemon` | Docker Desktop nu e pornit | îl porniți și așteptați *Engine running* |
| `port is already allocated` | alt program folosește portul (alt PostgreSQL, de exemplu) | îl opriți sau anunțați profesorul |
| `S3_ACCESS_KEY` gol, `NoSuchBucket`, `AccessDenied` | Garage neconfigurat sau `.env` necitit | `bash comun/pregateste-garage.sh`, apoi `up -d --force-recreate` |
| `ModuleNotFoundError: faiss` sau `open_clip` | imaginea Jupyter e veche | pasul 3 din *Prima pornire* |
| `Lipseste .../artefacte/...` | fișierul primit nu e în `artefacte/` | îl copiați acolo |
| comanda rămâne pe o linie care începe cu `>` | comanda lipită nu s-a terminat | `Ctrl+C` și o lipiți din nou, pe rând |

## Ce nu faceți

- `docker compose down -v` sau `docker system prune --volumes`: **șterg definitiv** baza și imaginile;
- editarea manuală a `.env` sau a `garage/garage.toml`: rulați din nou `bash comun/pregateste-garage.sh`;
- mutarea proiectului pe `C:`, în OneDrive sau în Google Drive: sincronizarea strică datele.
