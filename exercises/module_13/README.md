# Exercice du module 13

À la fin du module, le serveur tourne dans son conteneur, publié sur `127.0.0.1:8000`, et le
service `mcp` de `compose.yaml` a un contrôle de santé : une requête sur la métadonnée de
ressource protégée, qui répond 200 sans jeton. Ce contrôle dit que le processus écoute, et rien
de plus. Quand SQL Server s'arrête, ou quand le mot de passe de `mcp_reader` change, le conteneur
reste « healthy » et chaque appel d'outil échoue. L'équipe veut un contrôle qui dise si le
serveur peut répondre, et pousser l'ensemble sur son propre dépôt, avec une CI verte.

## Le départ

Partez de la fin du module, votre branche `module-13`, ou l'étiquette du dépôt :

```bash
git switch -c exercise-13 module-13-end
uv sync
uv run python setup/use_account.py mcp_reader
```

Le labo doit tourner (`./setup/install.sh`, puis `uv run python setup/check_lab.py`, qui finit
par `lab ok`). Il vous faut aussi Docker ou Podman, et `gh`, la CLI de GitHub, connectée
(`gh auth login`) à un dépôt à vous, où vous poussez cette branche : un dépôt créé sur votre
compte, avec `origin` qui pointe vers lui (`git remote set-url origin <votre dépôt>`). Rien n'est
écrit dans la base.

## La demande

1. Dans `src/pachatraining_mcp/server.py`, une route `GET /health`, par
   `@mcp.custom_route("/health", methods=["GET"])` : `200` et `{"status": "ok"}` quand un
   `SELECT 1` passe avec le compte du serveur, `503` et `{"status": "unavailable"}` quand la
   base ne répond pas, en moins de dix secondes. Le SDK ne demande jamais de jeton sur une route
   à soi : la réponse ne dit ni le nom du serveur SQL, ni le compte, ni le texte de l'erreur, qui
   reste dans le journal.
2. Dans `compose.yaml`, le contrôle de santé du service `mcp` interroge `/health`.
3. L'image reste ce qu'elle est au module : elle se construit, le serveur y tourne sous un
   utilisateur sans droits, répond en 2026-07-28, refuse un `Host` étranger, et ne contient ni
   `.env` ni aucune valeur de `.env`.
4. Vous commitez, poussez sur votre dépôt, et attendez la fin de la CI.

La fonction du pilote est synchrone : appelez-la par `anyio.to_thread.run_sync`, comme le
gestionnaire de complétion du module 6, et bornez l'attente par `anyio.fail_after`.

## Le critère

```bash
bash exercises/module_13/check.sh                 # Docker
ENGINE=podman bash exercises/module_13/check.sh   # Podman
```

Le script lance pytest sur `exercises/module_13/test_container.py`, sans modèle ni Node. Le
test construit l'image depuis votre `Dockerfile`, la démarre sur le réseau du labo, port publié
sur `127.0.0.1` seulement, avec un jeton tiré pour la séance et passé par l'environnement, puis
supprime ses conteneurs et l'image. Il attend cinq tests passés et échoue sur tout autre
nombre :

1. l'image se construit et ne tourne pas en `root` ; le conteneur répond `401` sans jeton, et à
   `server/discover` en 2026-07-28 avec le jeton ;
2. un `Host: evil.example` reçoit `421`, une `Origin` étrangère `403` ;
3. `/health` rend `200` et `{"status": "ok"}` ; un second conteneur, dont la base ne répond pas
   (`PACHA_SQL_SERVER=sql,1`), rend `503` en moins de dix secondes, sans nommer le serveur, le
   compte ni le mot de passe ;
4. l'image ne contient aucun fichier `.env`, et aucun morceau de 12 caractères d'une valeur de
   votre `.env` (mots de passe, jetons, secrets), ni dans ses fichiers, ni dans son historique,
   ni dans sa configuration ;
5. votre arbre n'a aucune modification non commitée, et le dernier workflow de votre commit,
   lu par `gh run list --commit`, est terminé et vert.

La dernière ligne doit être `All 5 checks passed.` Une solution est dans
`exercises/module_13/solution/`.

## À réfléchir

- Le contrôle 4 cherche les valeurs de votre `.env`, et non des motifs. Mesuré au cours :
  `gitleaks`, lancé sur le système de fichiers d'une image et sur son historique, signale le
  mot de passe d'un `.env` copié, mais ni la ligne des jetons, ni une chaîne de connexion
  `Server=...;PWD=...;` écrite dans un fichier de configuration. Que ne voit pas, à son tour,
  une recherche de valeurs ?
- `/health` ne demande pas de jeton. Que pourrait-on apprendre de l'extérieur avec une route
  qui rendrait le texte de l'erreur du pilote ?
- Le contrôle de santé de compose décide de l'ordre de démarrage (`depends_on` avec
  `condition: service_healthy`). Un service qui dépendrait de `mcp` démarrerait-il, avec la
  base arrêtée ?

---

# Module 13 exercise

At the end of the module, the server runs in its container, published on `127.0.0.1:8000`, and
the `mcp` service of `compose.yaml` has a health check: a request for the protected resource
metadata, which answers 200 without a token. That check says the process listens, and nothing
more. When SQL Server stops, or when the password of `mcp_reader` changes, the container stays
"healthy" and every tool call fails. The team wants a check that says whether the server can
answer, and to push the whole thing to its own repository, with a green CI.

## Starting point

Start from the end of the module, your `module-13` branch, or the tag of the repository:

```bash
git switch -c exercise-13 module-13-end
uv sync
uv run python setup/use_account.py mcp_reader
```

The lab must be running (`./setup/install.sh`, then `uv run python setup/check_lab.py`, which
ends with `lab ok`). You also need Docker or Podman, and `gh`, the GitHub CLI, signed in
(`gh auth login`) to a repository of yours, where you push this branch: a repository created on
your account, with `origin` pointing to it (`git remote set-url origin <your repository>`).
Nothing is written to the database.

## What to do

1. In `src/pachatraining_mcp/server.py`, a `GET /health` route, with
   `@mcp.custom_route("/health", methods=["GET"])`: `200` and `{"status": "ok"}` when a
   `SELECT 1` succeeds with the server's account, `503` and `{"status": "unavailable"}` when the
   database does not answer, in less than ten seconds. The SDK never asks for a token on a route
   of your own: the answer names neither the SQL server, nor the account, nor the text of the
   error, which stays in the log.
2. In `compose.yaml`, the health check of the `mcp` service asks `/health`.
3. The image stays what it is in the module: it builds, the server runs in it as a user without
   rights, answers in 2026-07-28, refuses a foreign `Host`, and holds neither `.env` nor any
   value of `.env`.
4. You commit, push to your repository, and wait for the CI to finish.

The driver's function is synchronous: call it through `anyio.to_thread.run_sync`, like the
completion handler of module 6, and bound the wait with `anyio.fail_after`.

## The check

```bash
bash exercises/module_13/check.sh                 # Docker
ENGINE=podman bash exercises/module_13/check.sh   # Podman
```

The script runs pytest on `exercises/module_13/test_container.py`, without a model or Node. The
test builds the image from your `Dockerfile`, starts it on the network of the lab, with its port
published on `127.0.0.1` only and a token drawn for the run passed through the environment, then
removes its containers and the image. It expects five passed tests and fails on any other
number:

1. the image builds and does not run as `root`; the container answers `401` without a token,
   and `server/discover` in 2026-07-28 with the token;
2. a `Host: evil.example` gets `421`, a foreign `Origin` `403`;
3. `/health` returns `200` and `{"status": "ok"}`; a second container, whose database does not
   answer (`PACHA_SQL_SERVER=sql,1`), returns `503` in less than ten seconds, without naming
   the server, the account or the password;
4. the image holds no `.env` file, and no piece of 12 characters of a value of your `.env`
   (passwords, tokens, secrets), neither in its files, nor in its history, nor in its
   configuration;
5. your tree has no uncommitted change, and the last workflow run of your commit, read with
   `gh run list --commit`, is completed and green.

The last line must be `All 5 checks passed.` A solution is in `exercises/module_13/solution/`.
