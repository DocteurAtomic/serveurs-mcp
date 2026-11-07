# Exercice du module 4

L'équipe veut pouvoir changer le serveur sans casser un client. Les tests du module
appellent le serveur en mémoire, dans le processus de pytest : ils ne disent rien de la
commande qu'un hôte lance, ni de l'environnement que ce processus reçoit. Vous écrivez une
suite qui lance le serveur comme un hôte le lance, par stdio, et qui vérifie les trois outils.

## Le départ

Partez de la fin du module, votre branche `module-04`, ou l'étiquette du dépôt :

```bash
git switch -c exercise-04 module-04-end
uv sync
```

Le labo doit tourner (`./setup/install.sh`, puis `uv run python setup/check_lab.py`, qui
finit par `lab ok`).

## La demande

Un fichier `tests/test_stdio.py`, avec trois tests, un par outil :

| Outil | Arguments | Ce que le test vérifie |
|---|---|---|
| `sessions_in_week` | `{"monday": "2026-11-16"}` | 36 sessions, la première est 17709 |
| `session_detail` | `{"session_id": 17709}` | `LNX-ADM2`, 6 inscrits |
| `trainer_load` | `{"trainer_id": 38, "month": "2026-10"}` | 3 sessions, 6.0 jours |

Les consignes :

1. Le serveur se lance par `Client(StdioServerParameters(...))`, avec la commande que vous
   avez donnée à `claude mcp add` : `uv --directory <dépôt> run pachatraining-mcp`. Calculez
   le chemin du dépôt à partir de `__file__`, pas du dossier courant.
2. Pas d'`env=os.environ`, ni d'autre copie de votre environnement. Le client du SDK ne
   transmet au processus que `HOME`, `LOGNAME`, `PATH`, `SHELL`, `TERM` et `USER`, comme
   l'Inspector ; le serveur doit trouver sa connexion dans son `.env`.
3. Chaque test vérifie que le résultat n'est pas en erreur, puis les valeurs du tableau. Un
   `assert result` est vrai aussi pour un résultat en erreur.
4. Les tests du module passent toujours (`uv run pytest -q`).

## Le critère

```bash
bash exercises/module_04/check.sh
```

Le script lance pytest deux fois sur `tests/test_stdio.py`, sans modèle ni Node :

1. tel quel : il attend trois tests passés, et échoue sur tout autre nombre ;
2. après avoir mis `.env` de côté et exporté ses variables `PACHA_SQL_*` dans son propre
   shell : un serveur lancé par stdio ne les reçoit pas, il ne joint plus la base, et les
   trois tests doivent échouer. Un test qui passe encore n'a pas lancé le serveur comme un
   hôte (il l'a appelé en mémoire, ou lui a passé l'environnement du shell), ou ne regarde
   pas le résultat.

Le script remet `.env` en place en sortant, même interrompu. La dernière ligne doit être
`All 3 checks passed, and all of them fail when the server cannot connect.`

Une solution est dans `exercises/module_04/solution/`.

---

# Module 4 exercise

The team wants to change the server without breaking a client. The module's tests call the
server in memory, inside the pytest process: they say nothing of the command a host starts,
nor of the environment that process receives. Write a suite that starts the server as a host
does, over stdio, and checks the three tools.

Start from the end of the module (`git switch -c exercise-04 module-04-end`, then `uv sync`),
with the lab running. Write `tests/test_stdio.py` with three tests, one per tool:
`sessions_in_week` for `2026-11-16` (36 sessions, the first is 17709), `session_detail` for
17709 (`LNX-ADM2`, 6 enrolled), `trainer_load` for trainer 38 in `2026-10` (3 sessions, 6.0
days). Start the server with `Client(StdioServerParameters(...))` and the command given to
`claude mcp add`, `uv --directory <repo> run pachatraining-mcp`, the repository path computed
from `__file__`. Do not pass `env=os.environ`: the SDK client hands the process `HOME`,
`LOGNAME`, `PATH`, `SHELL`, `TERM` and `USER` only, as the Inspector does, and the server must
find its connection in its `.env`. Check that each result is not an error, then its values:
`assert result` holds for an error result too. The module tests keep passing.

The check is `bash exercises/module_04/check.sh`. It runs pytest twice on
`tests/test_stdio.py`, with no model and no Node: as is, where three tests must pass, then with
`.env` moved aside and its `PACHA_SQL_*` variables exported in the script's shell, where all
three must fail. It puts `.env` back on exit, even when interrupted. Its last line must read
`All 3 checks passed, and all of them fail when the server cannot connect.` A solution is in
`exercises/module_04/solution/`.
