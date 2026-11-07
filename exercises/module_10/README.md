# Exercice du module 10

À la fin du module, `uv run pachatraining-mcp --http` sert le serveur en Streamable HTTP sur
`127.0.0.1`, et le SDK n'accepte que les en-têtes `Host` de la machine : `127.0.0.1`,
`localhost` et `[::1]`, avec leur port. L'équipe atteindra le serveur par un nom, celui qu'un
proxy ou un DNS interne lui donnera, et ce nom reçoit aujourd'hui `421 Invalid Host header`.
À vous de faire accepter ce nom, et lui seul en plus de ceux de la machine.

## Le départ

Partez de la fin du module, votre branche `module-10`, ou l'étiquette du dépôt :

```bash
git switch -c exercise-10 module-10-end
uv sync
uv run python setup/use_account.py mcp_reader
```

Le labo doit tourner (`./setup/install.sh`, puis `uv run python setup/check_lab.py`, qui finit
par `lab ok`). La base reste telle quelle : ni objet à créer, ni écriture.

## La demande

Dans `src/pachatraining_mcp/server.py`, quand le serveur est lancé avec `--http` :

1. il lit `PACHA_HTTP_HOSTS`, une liste de noms séparés par des virgules (par exemple
   `mcp.pachadata.example`), dans l'environnement ou dans `.env` ;
2. il accepte chacun de ces noms en `Host`, avec ou sans port (un proxy sur le port 443
   n'envoie pas de port), et en `Origin` sous la forme `http://` ou `https://` ;
3. il accepte toujours `127.0.0.1`, `localhost` et `[::1]` avec leur port : la liste que
   vous passez au SDK remplace la sienne, elle ne s'y ajoute pas ;
4. il refuse tout autre `Host` (421) et toute autre `Origin` (403), y compris un nom qui
   commence par celui de l'équipe ;
5. sans la variable, ou vide, il garde le réglage par défaut du SDK ;
6. il écoute toujours sur `127.0.0.1` et sur le port `PACHA_HTTP_PORT`.

Les noms passent par `TransportSecuritySettings` (`mcp.server.transport_security`), donné à
`mcp.run()` par `transport_security=`. Le motif `nom:*` accepte un nom suivi de n'importe quel
port.

Pour essayer avec Claude Code, `pachatraining.localhost` désigne la machine sur la plupart des
systèmes :

```bash
PACHA_HTTP_HOSTS=pachatraining.localhost uv run pachatraining-mcp --http
claude mcp add --transport http pachaname http://pachatraining.localhost:8000/mcp
claude mcp list
```

Sans la variable, `claude mcp list` affiche `HTTP 421: Error POSTing to endpoint: Invalid Host
header` ; avec elle, `Connected`.

## Le critère

```bash
bash exercises/module_10/check.sh
```

Le script lance pytest sur `exercises/module_10/test_team_names.py`, sans modèle ni Node.
Chaque test lance lui-même `pachatraining-mcp --http` sur un port libre de `127.0.0.1`, avec un
nom d'équipe tiré au hasard dans `PACHA_HTTP_HOSTS`, et l'interroge par HTTP : le client du SDK,
ou une requête `server/discover` dont les en-têtes `Host` et `Origin` sont ceux qu'enverrait un
proxy ou un navigateur. Le client en mémoire passe à côté du transport, donc des en-têtes que
ces tests regardent. Le script attend quatre tests passés et échoue sur tout autre nombre :

1. le nom de l'équipe est accepté, avec son port, sans port, et avec l'origine
   `https://<nom>` ;
2. les noms de la machine marchent toujours : `localhost:<port>`, et le client du SDK sur
   `127.0.0.1` obtient la révision 2026-07-28 et les 36 sessions de la semaine du 16 novembre
   2026 ;
3. `evil.example` et `<nom>.evil.example` sont refusés par 421, l'origine
   `http://evil.example` par 403 ;
4. relancé avec `PACHA_HTTP_HOSTS` vide, le serveur refuse le nom de l'équipe et
   `evil.example`, et accepte `127.0.0.1`.

La dernière ligne doit être `All 4 checks passed.` Une solution est dans
`exercises/module_10/solution/` ; `solution/tests/test_http.py` ajoute à la suite un test sur
le nom de l'équipe.

---

# Module 10 exercise

At the end of the module, `uv run pachatraining-mcp --http` serves the server over Streamable
HTTP on `127.0.0.1`, and the SDK accepts the `Host` headers of the machine only: `127.0.0.1`,
`localhost` and `[::1]`, with their port. The team will reach the server by a name, the one a
proxy or an internal DNS gives it, and that name gets `421 Invalid Host header` today. Make
the server accept that name, and only that one on top of the names of the machine.

## Starting point

Start from the end of the module, your `module-10` branch, or the tag of the repository:

```bash
git switch -c exercise-10 module-10-end
uv sync
uv run python setup/use_account.py mcp_reader
```

The lab must be running (`./setup/install.sh`, then `uv run python setup/check_lab.py`, which
ends with `lab ok`). Nothing to create in the database, and nothing is written to it.

## What to do

In `src/pachatraining_mcp/server.py`, when the server is started with `--http`:

1. it reads `PACHA_HTTP_HOSTS`, a list of names separated by commas (for instance
   `mcp.pachadata.example`), from the environment or from `.env`;
2. it accepts each of these names as `Host`, with or without a port (a proxy on port 443 sends
   no port), and as `Origin` in the `http://` or `https://` form;
3. it still accepts `127.0.0.1`, `localhost` and `[::1]` with their port: the list you give
   the SDK replaces its own, it does not add to it;
4. it refuses any other `Host` (421) and any other `Origin` (403), a name that starts with the
   team's one included;
5. without the variable, or with it empty, it keeps the SDK's default;
6. it still listens on `127.0.0.1` and on the port `PACHA_HTTP_PORT`.

The names go through `TransportSecuritySettings` (`mcp.server.transport_security`), given to
`mcp.run()` as `transport_security=`. The pattern `name:*` accepts a name followed by any port.

To try it with Claude Code, `pachatraining.localhost` names the machine on most systems:

```bash
PACHA_HTTP_HOSTS=pachatraining.localhost uv run pachatraining-mcp --http
claude mcp add --transport http pachaname http://pachatraining.localhost:8000/mcp
claude mcp list
```

Without the variable, `claude mcp list` shows `HTTP 421: Error POSTing to endpoint: Invalid
Host header`; with it, `Connected`.

## The check

```bash
bash exercises/module_10/check.sh
```

The script runs pytest on `exercises/module_10/test_team_names.py`, without a model or Node.
Each test starts `pachatraining-mcp --http` itself on a free port of `127.0.0.1`, with a team
name drawn at random in `PACHA_HTTP_HOSTS`, and talks to it over HTTP: the SDK client, or a
`server/discover` request whose `Host` and `Origin` headers are the ones a proxy or a browser
would send. The in-memory client goes through no transport and would see nothing here. The
script expects four passed tests and fails on any other number:

1. the team's name is accepted, with its port, without a port, and with the origin
   `https://<name>`;
2. the names of the machine still work: `localhost:<port>`, and the SDK client on `127.0.0.1`
   gets revision 2026-07-28 and the 36 sessions of the week of 16 November 2026;
3. `evil.example` and `<name>.evil.example` are refused with 421, the origin
   `http://evil.example` with 403;
4. started again with `PACHA_HTTP_HOSTS` empty, the server refuses the team's name and
   `evil.example`, and accepts `127.0.0.1`.

The last line must be `All 4 checks passed.` A solution is in `exercises/module_10/solution/`;
`solution/tests/test_http.py` adds a test on the team's name to the suite.
