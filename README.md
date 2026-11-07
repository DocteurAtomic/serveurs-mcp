# Serveurs MCP en Python

Labo et projet du cours en ligne
[« Serveurs MCP en Python »](https://www.docteuratomic.com) de Docteur Atomic : on y écrit
`pachatraining-mcp`, un serveur MCP en Python sur la base SQL Server `PachadataTraining`,
qu'on branche ensuite sur Claude Code.

## Ce qu'il faut sur le poste

- Python 3.13 et [`uv`](https://docs.astral.sh/uv/), Git, `curl` et un shell bash (sous
  Windows, WSL2) ;
- Docker (ou Podman) avec `compose`, 2 Go de mémoire libre pour SQL Server et environ 9 Go de
  disque (la base de référence et ses deux copies de travail) ;
- pour les modules qui les emploient : Node.js 24.22.1 ou plus récent dans la 24, ou 22.23.4 dans la 22 (MCP Inspector) et
  Claude Code ;
- pour le module 12 : 1 Go de mémoire de plus pour Keycloak, et un accès Internet depuis son
  conteneur (Keycloak lit sur claude.ai le document qui décrit Claude Code comme client).

Le pilote `mssql-python` (Microsoft, licence MIT) s'installe par `uv` sans pilote ODBC
système : il apporte le sien, `mssql-python-odbc`, le pilote ODBC 18 de Microsoft, gratuit
mais sous licence propriétaire.

## Le labo

    git clone https://github.com/DocteurAtomic/serveurs-mcp.git
    cd serveurs-mcp
    ./setup/install.sh
    uv sync
    uv run python setup/check_lab.py

`install.sh` écrit `.env` avec des mots de passe tirés au hasard (le fichier n'est jamais
versionné ; `.env.example` montre ce qu'il contient), télécharge la sauvegarde de
`PachadataTraining` (626 Mo) et vérifie sa somme SHA-256, démarre SQL Server 2025 Developer
dans le conteneur `mcpcourse` (2 Go de mémoire), restaure la base, crée les comptes
`pacha_app` et `mcp_reader` et le schéma `Mcp` (vues et procédures du serveur), puis les copies
`PachadataTraining_m07` et `PachadataTraining_m09` sur lesquelles écrivent les modules 7 et 9.
Il se relance sans danger : ce qui existe déjà est gardé. `check_lab.py` se connecte depuis le
poste avec les deux comptes et compare ce qu'il lit aux nombres des vidéos.

Avec Podman : `COMPOSE="podman compose" ENGINE=podman ./setup/install.sh` (`podman compose`
demande `podman-compose` ou `docker-compose` ; sans eux, `COMPOSE="uvx podman-compose"`).

Se connecter : `127.0.0.1,14733`, avec l'un des comptes et son mot de passe lus dans `.env`.
Le serveur MCP ne se connecte jamais en `sa`, qui ne sert qu'à `setup/`. Le conteneur n'a qu'un
certificat auto-signé : cochez *Trust server certificate* dans SSMS.

Une copie de travail se recrée par `./setup/reset-copy.sh m07` (quelques secondes) et se
supprime par `./setup/reset-copy.sh m07 --drop`, ce qui libère 2,4 Go.

## Keycloak (module 12)

    uv run python setup/keycloak.py

Le serveur d'autorisation du module 12 est un service à part de `compose.yaml`, dans le profil
`oauth` : `install.sh` et la CI ne le démarrent pas. `setup/keycloak.py` tire au hasard, dans
`.env`, le mot de passe de l'administrateur de Keycloak, ceux des deux comptes du royaume
(`alice`, qui peut écrire, et `carol`, qui ne fait que lire) et les secrets de ses deux clients
confidentiels, puis démarre Keycloak 26.8.2 en mode développement sur `127.0.0.1:8080` et attend
le royaume `pachadata` (environ 20 secondes). Le royaume est importé de
`setup/keycloak/pachadata-realm.json`, sans un clic dans la console, ses `${...}` lus dans
`.env`. Il ne s'importe qu'à la création du conteneur : après un changement du fichier ou d'un
secret, `docker rm -f mcpcourse-keycloak`, puis relancer le script. Avec Podman :
`COMPOSE="podman compose" uv run python setup/keycloak.py`. La console :
`http://127.0.0.1:8080/admin`, compte `admin`.

## Dépannage

- Mac à puce Apple : l'image SQL Server n'existe que pour `linux/amd64` ; le `compose.yaml` le
  dit (`platform: linux/amd64`), et Docker Desktop l'émule par Rosetta. Si le conteneur
  s'arrête au démarrage, activez « Use Rosetta for x86_64/amd64 emulation on Apple Silicon »
  dans les réglages de Docker Desktop.
- `TCP Provider: Error code 0x2749` à la connexion : le serveur est nommé `localhost`, qui se
  résout d'abord en `::1`, alors que le port n'est publié que sur `127.0.0.1`. Écrivez
  `127.0.0.1,14733`, comme dans `.env.example`.
- Le port 14733 est pris : `SQLPORT` dans `.env` le change, avant le premier démarrage, et
  `PACHA_SQL_SERVER` doit le suivre.

## La base

`PachadataTraining` est la base de démonstration anglaise de Pachadata : un organisme de
formation fictif, ses stages, sessions, inscriptions, factures et formateurs. Les personnes
sont fictives. Sa documentation est dans le dépôt
[rudi-bruchez/formations](https://github.com/rudi-bruchez/formations/tree/main/bases-exemples/PachadataTraining).
La sauvegarde n'est pas dans ce dépôt, le script la télécharge.

## Licence

Le code est sous licence MIT ([`LICENSE`](LICENSE)).

---

# Building MCP Servers in Python

Lab and project of the Docteur Atomic online course on building MCP servers in Python: you
write `pachatraining-mcp`, a Python MCP server over the SQL Server database
`PachadataTraining`, and plug it into Claude Code. Run `./setup/install.sh`, then `uv sync` and
`uv run python setup/check_lab.py` (Python 3.13 with uv, Docker or Podman with compose, curl,
bash, 2 GB of free memory, about 9 GB of disk). The script writes `.env` with random passwords
(never committed), downloads the backup and checks its SHA-256, starts SQL Server 2025
Developer in the `mcpcourse` container, restores the database, creates the `pacha_app` and
`mcp_reader` accounts and the `Mcp` schema, then the copies the modules 7 and 9 write to.
Connect to `127.0.0.1,14733` (not `localhost`, which resolves to `::1` first). On an Apple
silicon Mac, Docker Desktop emulates the `linux/amd64` image; enable Rosetta emulation in its
settings if the container stops at startup. The `mssql-python` driver brings Microsoft's ODBC
Driver 18 (`mssql-python-odbc`), free but under a proprietary license. Module 12 adds Keycloak, a service of the
`oauth` profile of `compose.yaml` that neither `install.sh` nor the CI starts:
`uv run python setup/keycloak.py` draws its secrets into `.env` and starts it on
`127.0.0.1:8080` (1 GB more memory, and Internet access from its container). The
code is released under the MIT license.
