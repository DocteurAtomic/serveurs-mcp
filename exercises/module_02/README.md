# Exercice du module 2

Votre serveur répond à deux clients qui ne parlent pas la même révision du protocole : le
MCP Inspector, qui part par défaut sur la révision 2025-11-25, et Claude Code. Vous
enregistrez le fil de chacun avec `tools/wire.sh`, puis vous écrivez ce que vous y lisez.

## Le départ

Partez de la fin du module, votre branche `module-02`, ou l'étiquette du dépôt :

```bash
git switch -c exercise-02 module-02-end
uv sync
```

Le labo doit tourner (`uv run python setup/check_lab.py` finit par `lab ok`). Il vous faut
aussi Node.js (24.22.1 ou plus récent dans la 24, ou 22.23.4 dans la 22) pour l'Inspector, et
Claude Code.

## Les journaux

Les journaux s'écrivent dans `logs/`, un par étiquette, écrasés à chaque démarrage du serveur.

1. L'Inspector CLI, sans option d'ère (il part alors en `legacy`), sur l'étiquette `insp`,
   avec un appel d'outil :

   ```bash
   npx @modelcontextprotocol/inspector@2.14.0 --cli tools/wire.sh insp \
     --method tools/call --tool-name session_detail --tool-arg session_id=17719
   ```

2. Claude Code, sur l'étiquette `claude`. Dans `~/pachadata-host`, enregistrez le serveur
   derrière `tools/wire.sh` (chemin absolu de votre dépôt), puis posez une question en
   `claude -p` :

   ```bash
   claude mcp remove pachatraining
   claude mcp add pachatraining -- /chemin/absolu/serveurs-mcp/tools/wire.sh claude
   claude -p "Combien de stagiaires sont inscrits à la session 17719 ?" \
     --allowedTools mcp__pachatraining__session_detail
   ```

   Ne lancez ensuite plus rien sur l'étiquette `claude` : `claude mcp list` ou une session
   `claude` redémarreraient le serveur et écraseraient le journal.

## La demande

Copiez `exercises/module_02/answers.example.toml` en `exercises/module_02/answers.toml` et
remplissez-le, pour chaque client, avec ce que montre son journal :

| Clé | Ce qu'elle contient |
|---|---|
| `revision` | la révision du protocole employée : celle que rend la réponse à `initialize`, ou celle que chaque requête déclare dans `_meta` |
| `first_method` | la première méthode envoyée par le client |
| `tool_calls` | le nombre de `tools/call` du journal |

Lisez les fichiers `logs/wire-insp.in.jsonl` et `logs/wire-claude.in.jsonl` à la main, ou avec
`uv run python tools/wire_summary.py insp claude`.

## Le critère

```bash
bash exercises/module_02/check.sh
```

Le script lance pytest, sans modèle ni Node. Il lit vos deux journaux avec les types JSON-RPC du
SDK et les compare à vos réponses, pas à des valeurs fixes : Claude Code peut parler une autre
révision sur un autre poste. Il attend trois tests passés, et échoue sur tout autre nombre :

- la révision de chaque client est celle de son journal, et l'Inspector a bien été enregistré
  en `legacy` ;
- la première méthode de chaque client est celle de son journal ;
- chaque journal contient au moins un `tools/call`, et leur nombre est celui de vos réponses.

Chaque journal doit avoir été écrit par le bon client (`inspector-cli`, `claude-code`). La
dernière ligne doit être `All 3 checks passed.`

Une solution, celle de ma répétition, est dans `exercises/module_02/solution/answers.toml`.

## À réfléchir

- Claude Code envoie deux `server/discover` dans le même démarrage. Lequel est la sonde, et à
  quoi la reconnaissez-vous ?
- Le dernier message de `logs/wire-claude.out.jsonl` est une erreur. À quelle requête
  répond-elle, et quand le serveur l'a-t-il envoyée ?
- Relancez `claude mcp list`, puis relisez le journal `claude`. Combien de démarrages
  contient-il ?

---

# Module 2 exercise

Your server answers two clients that do not speak the same protocol revision: the MCP
Inspector, which starts on revision 2025-11-25 by default, and Claude Code. Record the wire of
each with `tools/wire.sh`, then write down what you read in it.

Start from the end of the module (`git switch -c exercise-02 module-02-end`, then `uv sync`),
with the lab running, Node.js (24.22.1 or later in 24, or 22.23.4 in 22) and Claude Code.

1. The Inspector CLI, without an era option (it then uses `legacy`), on the tag `insp`:
   `npx @modelcontextprotocol/inspector@2.14.0 --cli tools/wire.sh insp --method tools/call --tool-name session_detail --tool-arg session_id=17719`.
2. Claude Code, on the tag `claude`: in `~/pachadata-host`, register the server behind
   `tools/wire.sh` (`claude mcp add pachatraining -- /absolute/path/serveurs-mcp/tools/wire.sh claude`),
   then ask `claude -p "Combien de stagiaires sont inscrits à la session 17719 ?" --allowedTools mcp__pachatraining__session_detail`.
   Do not start anything else on that tag afterwards: each start overwrites the log.

Copy `exercises/module_02/answers.example.toml` to `exercises/module_02/answers.toml` and fill
in, for each client, the protocol revision used (`revision`), the first method it sent
(`first_method`) and the number of `tools/call` in the log (`tool_calls`).
`uv run python tools/wire_summary.py insp claude` summarizes both logs.

The check is `bash exercises/module_02/check.sh`: pytest, no model, no Node. It reads both logs
with the SDK's JSON-RPC types and compares them with your answers, not with fixed values, since
Claude Code may speak another revision on another machine. Three tests are expected, and any
other number fails. Its last line must read `All 3 checks passed.` A solution, from my own run,
is in `exercises/module_02/solution/answers.toml`.
