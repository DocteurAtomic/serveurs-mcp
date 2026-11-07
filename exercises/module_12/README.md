# Exercice du module 12

À la fin du module, le serveur vérifie les jetons de Keycloak avec les clés publiques du
royaume : pas d'appel à Keycloak par requête, pas de secret de son côté. Le prix : un jeton
signé reste bon jusqu'à son expiration. Quand Keycloak ferme la session d'un utilisateur (il se
déconnecte, un administrateur coupe ses sessions), son jeton d'accès continue d'ouvrir le
serveur pendant quelques minutes. L'équipe veut pouvoir choisir l'autre façon : demander à
Keycloak, pour chaque requête, si le jeton est encore actif. À vous d'ajouter cette
vérification, l'introspection de la RFC 7662.

## Le départ

Partez de la fin du module, votre branche `module-12`, ou l'étiquette du dépôt :

```bash
git switch -c exercise-12 module-12-end
uv sync
uv run python setup/use_account.py mcp_reader
uv run python setup/keycloak.py
```

Le labo doit tourner (`./setup/install.sh`, puis `uv run python setup/check_lab.py`, qui finit
par `lab ok`), et Keycloak aussi : `setup/keycloak.py` tire ses secrets dans `.env` s'ils
manquent, démarre le service `keycloak` de `compose.yaml` et attend le royaume (environ 20
secondes, 1 Go de mémoire de plus ; avec Podman, `COMPOSE="podman compose"` devant). Rien
n'est écrit dans la base.

## La demande

Dans `src/pachatraining_mcp/server.py` :

1. avec `PACHA_OAUTH_VERIFY=introspection` (et `PACHA_OAUTH_ISSUER`), le serveur demande à
   Keycloak, pour chaque requête, ce qu'il sait du jeton : un `POST` du jeton sur le point
   d'introspection du royaume, `<émetteur>/protocol/openid-connect/token/introspect`,
   authentifié comme le client `pacha-mcp` avec le secret `KEYCLOAK_MCP_SECRET` du `.env` ;
2. sans la variable, ou avec `jwks`, rien ne change : la vérification par les clés du module ;
3. un jeton que Keycloak dit inactif (`"active": false`), ou qui n'a pas été émis par
   `PACHA_OAUTH_ISSUER` pour l'adresse du serveur, reçoit `401` ; un jeton actif donne le même
   `AccessToken` qu'avec les clés : les scopes, l'utilisateur, l'émetteur ;
4. `--http` refuse de démarrer, code 2, avec un message qui nomme `KEYCLOAK_MCP_SECRET`, quand
   l'introspection est demandée et que le secret est vide ;
5. le journal du serveur nomme l'utilisateur de chaque requête et ne contient jamais un jeton,
   ni un morceau de jeton.

`issued_token()` construit déjà l'`AccessToken` à partir des claims d'un jeton : la réponse de
l'introspection en a la même forme. Le client HTTP est `httpx2`, installé avec le SDK. La
documentation du SDK renvoie à un `IntrospectionTokenVerifier`, dans
`examples/servers/simple-auth/` de son dépôt.

## Le critère

```bash
bash exercises/module_12/check.sh
```

Le script lance pytest sur `exercises/module_12/test_introspection.py`, sans modèle ni Node. Le
test demande lui-même ses jetons à Keycloak, par le client `pacha-check` du royaume (le flux
« mot de passe », réservé aux contrôles : Claude Code passe par le navigateur), puis lance
`pachatraining-mcp --http` sur un port libre de `127.0.0.1` avec
`PACHA_OAUTH_VERIFY=introspection`, et l'interroge par HTTP. Il attend cinq tests passés et
échoue sur tout autre nombre :

1. sans jeton, `401`, et la métadonnée du serveur renvoie à Keycloak ; les jetons d'alice et de
   carol sont acceptés ; un jeton émis pour un autre service, non ;
2. carol, qui ne fait que lire, se voit refuser `postpone_session` sans demande de
   confirmation ; alice la reçoit ;
3. alice se déconnecte, et Keycloak ferme sa session : le jeton d'accès qu'elle avait, encore
   loin de son expiration, reçoit `401` à la requête suivante. C'est le test que la vérification
   par les clés ne passe pas ;
4. sans `KEYCLOAK_MCP_SECRET`, `--http` ne démarre pas, code 2 ;
5. le journal nomme alice et carol, et aucun morceau de 12 caractères d'un jeton n'y paraît.

La dernière ligne doit être `All 5 checks passed.` Une solution est dans
`exercises/module_12/solution/`.

## À réfléchir

- Mesuré au labo Keycloak du cours : 0,8 ms par jeton avec les clés, 7 ms par introspection.
  Que coûte l'introspection quand Claude Code envoie dix requêtes pour une question, et que se
  passe-t-il quand Keycloak ne répond plus ?
- Keycloak 26.8 dit inactif tout jeton dont l'audience ne contient pas le client qui
  l'introspecte : c'est pourquoi le royaume ajoute `pacha-mcp` à l'audience. Que deviendrait
  l'introspection si le royaume ne mettait que l'adresse du serveur, comme le tutoriel de
  modelcontextprotocol.io ?
- Retirer le rôle `pacha-writer` à alice vaut au jeton suivant, dans les deux modes. Quel
  événement seul l'introspection voit-elle, et faut-il le payer à chaque requête ?

---

# Module 12 exercise

At the end of the module, the server checks Keycloak's tokens with the public keys of the
realm: no call to Keycloak per request, no secret on its side. The price: a signed token stays
good until it expires. When Keycloak ends a user's session (she signs out, an administrator
ends her sessions), her access token keeps opening the server for a few minutes. The team
wants to be able to choose the other way: ask Keycloak, for each request, whether the token is
still active. Your job is to add that check, the token introspection of RFC 7662.

## Starting point

Start from the end of the module, your `module-12` branch, or the tag of the repository:

```bash
git switch -c exercise-12 module-12-end
uv sync
uv run python setup/use_account.py mcp_reader
uv run python setup/keycloak.py
```

The lab must be running (`./setup/install.sh`, then `uv run python setup/check_lab.py`, which
ends with `lab ok`), and so must Keycloak: `setup/keycloak.py` draws its secrets into `.env`
when they are missing, starts the `keycloak` service of `compose.yaml` and waits for the realm
(about 20 seconds, 1 GB more memory; with Podman, prefix it with `COMPOSE="podman compose"`).
Nothing is written to the database.

## What to do

In `src/pachatraining_mcp/server.py`:

1. with `PACHA_OAUTH_VERIFY=introspection` (and `PACHA_OAUTH_ISSUER`), the server asks
   Keycloak, for each request, what it knows of the token: a `POST` of the token to the
   introspection endpoint of the realm, `<issuer>/protocol/openid-connect/token/introspect`,
   authenticated as the client `pacha-mcp` with the secret `KEYCLOAK_MCP_SECRET` of `.env`;
2. without the variable, or with `jwks`, nothing changes: the check by the keys of the module;
3. a token Keycloak says is inactive (`"active": false`), or that was not issued by
   `PACHA_OAUTH_ISSUER` for the address of the server, gets `401`; an active token gives the
   same `AccessToken` as with the keys: the scopes, the user, the issuer;
4. `--http` refuses to start, exit code 2, with a message that names `KEYCLOAK_MCP_SECRET`,
   when introspection is asked for and the secret is empty;
5. the server's log names the user of each request and never holds a token, nor a piece of
   one.

`issued_token()` already builds the `AccessToken` from the claims of a token: the answer of the
introspection has the same shape. The HTTP client is `httpx2`, installed with the SDK. The SDK
documentation points to an `IntrospectionTokenVerifier`, in `examples/servers/simple-auth/` of
its repository.

## The check

```bash
bash exercises/module_12/check.sh
```

The script runs pytest on `exercises/module_12/test_introspection.py`, without a model or Node.
The test asks Keycloak for its tokens itself, through the realm's `pacha-check` client (the
password grant, kept for the checks: Claude Code goes through the browser), then starts
`pachatraining-mcp --http` on a free port of `127.0.0.1` with
`PACHA_OAUTH_VERIFY=introspection`, and talks to it over HTTP. It expects five passed tests and
fails on any other number:

1. without a token, `401`, and the server's metadata points to Keycloak; the tokens of alice
   and carol open the door; a token issued for another service does not;
2. carol, who only reads, is refused `postpone_session` without a confirmation request; alice
   gets one;
3. alice signs out, and Keycloak ends her session: the access token she had, still far from its
   expiry, gets `401` at the next request. This is the test the check by the keys fails;
4. without `KEYCLOAK_MCP_SECRET`, `--http` does not start, exit code 2;
5. the log names alice and carol, and no piece of 12 characters of a token appears in it.

The last line must be `All 5 checks passed.` A solution is in `exercises/module_12/solution/`.
