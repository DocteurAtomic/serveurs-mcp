# Exercice du module 11

À la fin du module, le serveur HTTP n'accepte que les jetons de `PACHA_TOKENS`, et chacun de
ces jetons peut tout faire, `postpone_session` et `cancel_enrollment` compris. L'équipe veut
deux sortes de jetons : la plupart des collègues lisent, quelques-uns seulement reportent une
session ou annulent une inscription. À vous d'ajouter les jetons de lecture.

## Le départ

Partez de la fin du module, votre branche `module-11`, ou l'étiquette du dépôt :

```bash
git switch -c exercise-11 module-11-end
uv sync
uv run python setup/use_account.py mcp_reader
```

Le labo doit tourner (`./setup/install.sh`, puis `uv run python setup/check_lab.py`, qui finit
par `lab ok`). Rien n'est écrit dans la base : le contrôle répond « decline » à la seule
confirmation qu'il reçoit.

## La demande

Dans `src/pachatraining_mcp/server.py` :

1. le serveur lit une seconde variable, `PACHA_READ_TOKENS`, de la même forme que
   `PACHA_TOKENS` (des paires `nom:jeton` séparées par des virgules), dans l'environnement ou
   dans `.env` ;
2. un jeton de `PACHA_READ_TOKENS` est accepté : `tools/list` rend tous les outils, et les
   outils qui lisent lui répondent ;
3. `postpone_session` et `cancel_enrollment` refusent ce jeton par une erreur d'outil
   (`isError`) qui dit pourquoi, et le refusent avant la confirmation : le lecteur ne reçoit
   jamais de demande de confirmation (`input_required`) ;
4. un jeton de `PACHA_TOKENS` garde tous les droits ;
5. le journal du serveur, sur stderr, nomme le collègue de chaque requête, lecteur compris,
   et ne contient jamais un jeton, ni un morceau de jeton.

`AccessToken` a un champ `scopes` : c'est l'endroit où dire ce qu'un jeton peut faire, par
exemple `pacha:read` pour tous et `pacha:write` pour ceux de `PACHA_TOKENS`. Le résolveur
`writer()` le lit par `get_access_token()`. Le module 12 garde ces deux noms de scope.

Pour essayer à la main, `setup/new_token.py` écrit dans `PACHA_TOKENS` ; ajoutez-lui une
option `--read` si vous voulez tirer un jeton de lecture de la même façon.

## Le critère

```bash
bash exercises/module_11/check.sh
```

Le script lance pytest sur `exercises/module_11/test_read_tokens.py`, sans modèle ni Node. Le
test lance lui-même `pachatraining-mcp --http` sur un port libre de `127.0.0.1`, avec un
rédacteur dans `PACHA_TOKENS` et un lecteur dans `PACHA_READ_TOKENS`, dont il tire au hasard
les noms et les jetons, et l'interroge par HTTP : le client en mémoire n'envoie pas de jeton,
et le serveur n'y connaît pas d'appelant. Le script attend quatre tests passés et échoue sur
tout autre nombre :

1. sans jeton, ou avec un jeton inconnu, `401` ; avec le jeton du rédacteur ou celui du
   lecteur, `200` ;
2. le lecteur liste les outils et lit les 36 sessions de la semaine du 16 novembre 2026, mais
   `postpone_session` et `cancel_enrollment` lui rendent une erreur, sans `input_required` ;
3. le rédacteur reçoit la demande de confirmation de `postpone_session`, et rien n'est
   reporté quand il répond « decline » ;
4. le journal du serveur nomme les deux collègues, et aucun morceau de 12 caractères d'un
   jeton n'y paraît.

La dernière ligne doit être `All 4 checks passed.` Une solution est dans
`exercises/module_11/solution/` ; `solution/tests/test_auth.py` ajoute à la suite un test sur
le lecteur.

---

# Module 11 exercise

At the end of the module, the HTTP server accepts the tokens of `PACHA_TOKENS` only, and each
of them may do anything, `postpone_session` and `cancel_enrollment` included. The team wants
two kinds of tokens: most colleagues read, a few only postpone a session or cancel an
enrollment. Add the read tokens.

## Starting point

Start from the end of the module, your `module-11` branch, or the tag of the repository:

```bash
git switch -c exercise-11 module-11-end
uv sync
uv run python setup/use_account.py mcp_reader
```

The lab must be running (`./setup/install.sh`, then `uv run python setup/check_lab.py`, which
ends with `lab ok`). Nothing is written to the database: the check answers "decline" to the
only confirmation it gets.

## What to do

In `src/pachatraining_mcp/server.py`:

1. the server reads a second variable, `PACHA_READ_TOKENS`, of the same form as
   `PACHA_TOKENS` (`name:token` pairs separated by commas), from the environment or from
   `.env`;
2. a token of `PACHA_READ_TOKENS` opens the door: `tools/list` returns every tool, and the
   tools that read answer it;
3. `postpone_session` and `cancel_enrollment` refuse that token with a tool error (`isError`)
   that says why, and refuse it before the confirmation: the reader never gets a
   confirmation request (`input_required`);
4. a token of `PACHA_TOKENS` keeps every right;
5. the server's log, on stderr, names the colleague of each request, readers included, and
   never holds a token, nor a piece of one.

`AccessToken` has a `scopes` field: that is where to say what a token may do, for instance
`pacha:read` for all of them and `pacha:write` for those of `PACHA_TOKENS`. The `writer()`
resolver reads it through `get_access_token()`. Module 12 keeps these two scope names.

To try it by hand, `setup/new_token.py` writes to `PACHA_TOKENS`; give it a `--read` option if
you want to draw a read token the same way.

## The check

```bash
bash exercises/module_11/check.sh
```

The script runs pytest on `exercises/module_11/test_read_tokens.py`, without a model or Node.
The test starts `pachatraining-mcp --http` itself on a free port of `127.0.0.1`, with a writer
in `PACHA_TOKENS` and a reader in `PACHA_READ_TOKENS`, whose names and tokens it draws at
random, and talks to it over HTTP: the in-memory client sends no token, and over it the server
knows no caller. The script expects four passed tests and fails on any other number:

1. without a token, or with an unknown one, `401`; with the writer's or the reader's token,
   `200`;
2. the reader lists the tools and reads the 36 sessions of the week of 16 November 2026, but
   `postpone_session` and `cancel_enrollment` return it an error, without `input_required`;
3. the writer gets the confirmation request of `postpone_session`, and nothing is postponed
   when it answers "decline";
4. the server's log names both colleagues, and no piece of 12 characters of a token appears
   in it.

The last line must be `All 4 checks passed.` A solution is in `exercises/module_11/solution/`;
`solution/tests/test_auth.py` adds a test on the reader to the suite.
