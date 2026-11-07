# Exercice du module 6

Le service planification veut, pour une période, les sessions encore `PLANNED` ou `OPEN` qui
sont remplies à moins de la moitié, celles qu'il faut surveiller. Sur la fin de l'année, il y
en a des dizaines : l'outil les rend par pages, comme `unpaid_invoices`.

## Le départ

Partez de la fin du module, votre branche `module-06`, ou l'étiquette du dépôt :

```bash
git switch -c exercise-06 module-06-end
uv sync
```

Le labo doit tourner (`./setup/install.sh`, puis `uv run python setup/check_lab.py`, qui
finit par `lab ok`).

## La demande

Dans `src/pachatraining_mcp/server.py`, un outil
`sessions_to_watch(from_date: date, to_date: date, cursor: str | None = None)` :

1. Il rend les sessions dont la date de début est entre `from_date` et `to_date` (les deux
   comprises), au statut `PLANNED` ou `OPEN`, dont les inscriptions non annulées occupent
   moins de la moitié des places du cours (`Course.Course.MaxAttendees`).
2. Une sortie structurée : `total` (toutes pages comprises), `sessions` (une ligne par
   session : `session_id`, `start_date`, `course_code`, `status`, `enrolled`,
   `max_attendees`) et `next_cursor`, absent ou `null` sur la dernière page.
3. 20 sessions par page au plus, dans l'ordre de la date de début, puis de l'identifiant.
4. Un curseur fabriqué par le serveur, qu'il refuse s'il ne peut pas le lire, par un
   `ToolError` dont le message contient le mot `cursor`.
5. Une période de plus de 92 jours entre `from_date` et `to_date` est refusée par un
   `ToolError` dont le message contient `92`. Une période de 92 jours est acceptée.
6. Les tests du module passent toujours (`uv run pytest -q`).

La requête de référence, en `sa` dans le conteneur, comme les contrôles de `setup/` :

```bash
docker compose exec sql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -d PachadataTraining -Q "
SELECT s.SessionId, s.StartDate
FROM Course.Session AS s
JOIN Course.Course AS c ON c.CourseId = s.CourseId
WHERE s.StartDate BETWEEN '2026-11-16' AND '2026-12-31'
  AND s.StatusCode IN ('PLANNED', 'OPEN')
  AND (SELECT COUNT(*) FROM Enrollment.Enrollment AS e
       WHERE e.SessionId = s.SessionId AND e.CancellationDate IS NULL) * 2 < c.MaxAttendees
ORDER BY s.StartDate, s.SessionId"
```

Avec Podman, `podman exec -i mcpcourse` à la place de `docker compose exec sql`. Elle rend
74 lignes : quatre pages, de 20, 20, 20 et 14 sessions.

## Le critère

```bash
bash exercises/module_06/check.sh
```

Le script lance pytest sur `exercises/module_06/test_sessions_to_watch.py`, avec le client du
SDK en mémoire, sans modèle ni Node. Il attend cinq tests passés et échoue sur tout autre
nombre :

1. la première page du 16 novembre au 31 décembre 2026 a 20 sessions, un `next_cursor` et
   `total` vaut 74 ;
2. les pages mises bout à bout donnent les identifiants de la requête de référence, dans son
   ordre, sans doublon ni trou ;
3. les pages font 20, 20, 20 et 14 sessions, et la dernière n'a pas de `next_cursor` ;
4. un curseur dont la fin est remplacée par `AAAA` rend un résultat `is_error` qui parle du
   curseur ;
5. du 16 novembre 2026 au 16 février 2027 (92 jours) est accepté ; jusqu'au 17 février
   (93 jours), refusé avec un message qui contient `92`.

La dernière ligne doit être `All 5 checks passed.` Une solution est dans
`exercises/module_06/solution/`.

---

# Module 6 exercise

The planning team wants, for a period, the sessions still `PLANNED` or `OPEN` that are less
than half full, the ones to watch. Toward the end of the year there are dozens of them: the
tool returns them in pages, like `unpaid_invoices`.

## Starting point

Start from the end of the module, your `module-06` branch, or the tag of the repository:

```bash
git switch -c exercise-06 module-06-end
uv sync
```

The lab must be running (`./setup/install.sh`, then `uv run python setup/check_lab.py`, which
ends with `lab ok`).

## What to do

In `src/pachatraining_mcp/server.py`, a tool
`sessions_to_watch(from_date: date, to_date: date, cursor: str | None = None)`:

1. It returns the sessions that start from `from_date` to `to_date` (both included), in status
   `PLANNED` or `OPEN`, whose enrollments, cancelled ones left out, fill less than half of the
   seats of the course (`Course.Course.MaxAttendees`).
2. A structured output: `total` (over all pages), `sessions` (one row per session:
   `session_id`, `start_date`, `course_code`, `status`, `enrolled`, `max_attendees`) and
   `next_cursor`, absent or `null` on the last page.
3. At most 20 sessions per page, by start date, then by id.
4. A cursor minted by the server, which refuses one it cannot read with a `ToolError` whose
   message contains the word `cursor`.
5. A period of more than 92 days between `from_date` and `to_date` is refused with a
   `ToolError` whose message contains `92`. A period of 92 days is accepted.
6. The tests of the module still pass (`uv run pytest -q`).

The reference query, as `sa` in the container, like the checks of `setup/`: see the French
section above. With Podman, `podman exec -i mcpcourse` instead of `docker compose exec sql`.
It returns 74 rows: four pages of 20, 20, 20 and 14 sessions.

## The check

```bash
bash exercises/module_06/check.sh
```

The script runs pytest on `exercises/module_06/test_sessions_to_watch.py`, with the SDK
client in memory, without a model or Node. It expects five passed tests and fails on any
other number:

1. the first page from 16 November to 31 December 2026 has 20 sessions and a `next_cursor`,
   and `total` is 74;
2. the pages put end to end give the ids of the reference query, in its order, with no
   duplicate and no gap;
3. the pages hold 20, 20, 20 and 14 sessions, and the last one has no `next_cursor`;
4. a cursor whose end is replaced by `AAAA` returns an `is_error` result that mentions the
   cursor;
5. from 16 November 2026 to 16 February 2027 (92 days) is accepted; up to 17 February
   (93 days), refused with a message that contains `92`.

The last line must be `All 5 checks passed.` A solution is in `exercises/module_06/solution/`.
