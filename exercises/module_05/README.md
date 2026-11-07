# Exercice du module 5

Le service planification veut la charge d'un formateur sur un mois sous la main, comme le
service commercial a la fiche d'un cours, et une revue de cette charge toujours faite de la
même façon. L'outil `trainer_load` existe depuis le module 3 : vous l'exposez aussi en modèle
de ressource, et vous écrivez le prompt de la revue.

## Le départ

Partez de la fin du module, votre branche `module-05`, ou l'étiquette du dépôt :

```bash
git switch -c exercise-05 module-05-end
uv sync
```

Le labo doit tourner (`./setup/install.sh`, puis `uv run python setup/check_lab.py`, qui
finit par `lab ok`).

## La demande

Dans `src/pachatraining_mcp/server.py` :

1. Un modèle de ressource `pachatraining://trainer/{trainer_id}/month/{month}`, de type
   `text/markdown`, qui réutilise `trainer_load`. Pour le formateur 38 en `2026-10`, le texte
   commence par la ligne `# Trainer 38, 2026-10` et contient les lignes `- Sessions: 3` et
   `- Days billed: 6.0`.
2. Un formateur inconnu rend l'erreur `-32602`, avec un message qui contient son identifiant.
   `trainer_load` lève un `ToolError` dans ce cas : un `ToolError` sorti d'une ressource
   arrive au client en `-32603`, avec un message qui ne nomme que l'URI.
3. Un prompt `trainer_review` à deux arguments requis, `trainer_id` et `month`, qui rend un
   message `user` : il nomme le formateur et le mois, et demande d'appeler `trainer_load`.
4. Les tests du module passent toujours (`uv run pytest -q`).

## Le critère

```bash
bash exercises/module_05/check.sh
```

Le script lance pytest sur `exercises/module_05/test_trainer_resources.py`, avec le client du
SDK en mémoire, sans modèle ni Node. Il attend cinq tests passés et échoue sur tout autre
nombre :

1. le modèle est dans `resources/templates/list`, et aucune ressource de formateur dans
   `resources/list` ;
2. `pachatraining://trainer/38/month/2026-10` rend un seul contenu `text/markdown`, à cette URI,
   avec les trois lignes de la demande ;
3. le formateur 999 rend `-32602`, et le message vient de votre fonction (pas
   « Unknown resource », que rend un serveur sans le modèle) et contient `999` ;
4. `trainer_review` est listé avec `trainer_id` et `month`, tous deux requis ;
5. `prompts/get` rend un seul message `user`, qui contient `38`, `2026-10` et `trainer_load`.

La dernière ligne doit être `All 5 checks passed.` Une solution est dans
`exercises/module_05/solution/`.

---

# Module 5 exercise

The planning team wants the load of a trainer over a month at hand, the way the sales team
has the sheet of a course, and a review of that load always done the same way. The
`trainer_load` tool exists since module 3: expose it as a resource template too, and write
the prompt of the review.

Start from the end of the module (`git switch -c exercise-05 module-05-end`, then `uv sync`),
with the lab running. In `src/pachatraining_mcp/server.py`, write a resource template
`pachatraining://trainer/{trainer_id}/month/{month}`, of type `text/markdown`, that reuses
`trainer_load`: for trainer 38 in `2026-10`, the text starts with the line
`# Trainer 38, 2026-10` and holds the lines `- Sessions: 3` and `- Days billed: 6.0`. An
unknown trainer returns the error `-32602`, with a message that contains its id; a `ToolError`
raised out of a resource reaches the client as `-32603`, with a message that names the URI
only. Then write a prompt `trainer_review` with two required arguments, `trainer_id` and
`month`, that returns one `user` message naming the trainer and the month and asking to call
`trainer_load`. The module tests keep passing.

The check is `bash exercises/module_05/check.sh`. It runs pytest on
`exercises/module_05/test_trainer_resources.py` with the in-memory SDK client, with no model
and no Node, and expects five passed tests, no more and no fewer: the template is listed as a
template and not as a resource; the month of trainer 38 is one `text/markdown` content at its
URI with the three lines; trainer 999 returns `-32602` with a message from your function (not
the "Unknown resource" of a server without the template) that contains `999`; `trainer_review`
is listed with its two required arguments; `prompts/get` returns one `user` message containing
`38`, `2026-10` and `trainer_load`. Its last line must read `All 5 checks passed.` A solution
is in `exercises/module_05/solution/`.
