# Rapport — API Gateway et microservices sécurisés (NOVA SERVICES)

## 1. Environnement

| Élément | Version |
|---|---|
| Image de base des services | `python:3.12-slim` |
| FastAPI / Starlette | 0.162.0 / 1.10.0 |
| Uvicorn | 0.54.0 |
| httpx | 0.28.1 |
| pytest | 9.2.0 |
| Python local (tests) | 3.14.8 |

Les `requirements.txt` reprennent l'énoncé (non épinglés). Pour une mise en
production, il faudrait épingler les versions (ou un fichier de contraintes) afin
que l'image construite en CI soit reproductible.

## 2. Partie 1 — Microservices

`users/main.py` et `orders/main.py` reprennent le code de l'énoncé. Seul
changement : dans Users, l'import de `HTTPException` est remonté en tête de
fichier au lieu d'être fait dans la fonction.

### Dockerfiles (identiques pour les trois services)

L'énoncé ne donne pas leur contenu (image), mais en fixe les exigences :

| Exigence | Mise en œuvre |
|---|---|
| Image de base légère | `python:3.12-slim` |
| Pas de cache pip | `pip install --no-cache-dir` |
| Utilisateur non privilégié | `useradd --system --uid 10001 … app` puis `USER app` |
| Code non modifiable par le processus | `COPY --chown=root:root main.py .` (l'utilisateur `app` ne peut pas le réécrire) |
| Healthcheck | `HEALTHCHECK` qui appelle `/health` avec le module `urllib` de Python (pas besoin d'installer `curl` dans l'image) |
| Pas de `.pyc` ni de tampon | `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1` |

Uvicorn écoute sur `0.0.0.0` **dans le conteneur** : c'est nécessaire pour être
joignable sur le réseau Docker. L'exposition réelle est décidée par Compose
(aucun port publié pour Users/Orders, `127.0.0.1` pour la Gateway).

### Étape 3 — tests des services seuls

Les commandes `docker build` / `docker run -p 8001:8000 …` de l'énoncé sont à
exécuter avec Docker (voir « À faire par l'utilisateur »). Le même comportement a
été vérifié hors Docker avec Uvicorn (section 5).

## 3. Partie 2 — API Gateway

`gateway/main.py` reprend le code de l'énoncé (indentation corrigée).

| Protection demandée | Où |
|---|---|
| Jeton Bearer sur les routes métier | dépendance `require_token` sur `/users`, `/orders`, `/profile/{id}` |
| Comparaison en temps constant | `secrets.compare_digest` |
| Secret par variable d'environnement | `GATEWAY_TOKEN = os.getenv(...)` ; si absent → 500 « not configured » (on refuse plutôt que d'ouvrir l'accès) |
| Timeout | `httpx.AsyncClient(timeout=5.0)` |
| Erreurs internes masquées | toute erreur httpx / JSON → 502 « A backend service is unavailable », sans trace ni URL interne |
| Backend par le réseau privé | `USERS_SERVICE=http://users:8000`, `ORDERS_SERVICE=http://orders:8000` (noms DNS Compose) |
| BFF | `/profile/{id}` : appels parallèles avec `asyncio.gather`, filtre des commandes de l'utilisateur |

## 4. Partie 3 — Docker Compose

`docker-compose.yml` (validé par `docker compose config -q`) :

| Mesure | Détail |
|---|---|
| Un seul port publié | `gateway` : `127.0.0.1:3000:8000`. `users` et `orders` : **aucun** `ports:` |
| Réseau privé | `backend` en `internal: true` (pas de sortie Internet pour Users/Orders) ; la Gateway est aussi sur `frontend`, nécessaire à la publication du port |
| Secret externalisé | `GATEWAY_TOKEN: ${GATEWAY_TOKEN:?…}` : Compose refuse de démarrer si `.env` ne le définit pas |
| Système de fichiers en lecture seule | `read_only: true` + `tmpfs: /tmp` |
| Capacités Linux supprimées | `cap_drop: [ALL]` |
| Pas d'escalade de privilèges | `security_opt: [no-new-privileges:true]` |
| Démarrage ordonné | `depends_on: condition: service_healthy` sur Users et Orders |

Ces options sont factorisées dans une ancre YAML `x-hardening` pour que les trois
services aient exactement le même durcissement.

`.env` (jeton généré par `openssl rand -hex 32`) est exclu par `.gitignore` et
`.dockerignore` ; seul `.env.example` (valeur fictive) est versionné. Les
Dockerfiles ne copient que `requirements.txt` et `main.py`, donc aucun secret ne
peut se retrouver dans une image.

## 5. Tests des endpoints

Sortie complète : [`preuves/endpoints-local.txt`](preuves/endpoints-local.txt).
Exécution hors Docker (trois Uvicorn locaux, Gateway sur un port local), le
jeton y est remplacé par `$GATEWAY_TOKEN`.

| Requête | Attendu | Obtenu |
|---|---|---|
| `GET /users` sans jeton | 401 | ✅ 401 `Missing or invalid authentication token` |
| `GET /users` mauvais jeton | 401 | ✅ 401 `Invalid authentication token` |
| `GET /users` avec jeton | 200 | ✅ Alice, Bob |
| `GET /orders` avec jeton | 200 | ✅ 101, 102, 103 |
| `GET /profile/1` avec jeton | 200 + agrégat | ✅ Alice + commandes 101 et 103 |
| `GET /profile/999` avec jeton | 404 | ✅ 404 `User not found` |
| `GET /health` sans jeton | 200 | ✅ `{"status":"ok"}` |
| `GET /profile/1`, Orders arrêté | 502 sans détail | ✅ 502 `A backend service is unavailable` |

**Même série rejouée sur l'architecture Docker Compose** (`localhost:3000`) :
[`preuves/endpoints-docker.txt`](preuves/endpoints-docker.txt), résultats
identiques. [`preuves/compose-ps.txt`](preuves/compose-ps.txt) montre les trois
conteneurs (Users et Orders *healthy* avant le démarrage de la Gateway), le seul
port publié `127.0.0.1:3000->8000/tcp`, et l'échec d'un accès direct à un
microservice depuis l'hôte.

## 6. Partie 4 — Tests automatisés

Sortie : [`preuves/pytest.txt`](preuves/pytest.txt) — **8 passed**.

- `tests/test_gateway.py` : les 5 tests de l'énoncé.
- `tests/test_gateway_securite.py` : 3 tests ajoutés pour couvrir des points de la
  checklist que l'énoncé ne testait pas :
  - backend injoignable → 502 avec un message générique (pas de détail technique) ;
  - `GATEWAY_TOKEN` vide → 500, l'accès n'est **pas** ouvert ;
  - le client httpx est bien créé avec `timeout=5.0`.

`pytest.ini` déclare `pythonpath = .` pour que `from gateway import main`
fonctionne aussi avec `pytest` lancé directement (pas seulement `python -m pytest`).

Contrôles complémentaires exécutés localement : **Bandit** (aucun résultat) et
**pip-audit** sur les trois `requirements.txt` (aucune vulnérabilité connue).

## 7. Partie 5 — GitLab CI/CD

`.gitlab-ci.yml` :

| Stage | Job | Contenu |
|---|---|---|
| `test` | `test` | `python:3.12-slim`, installation des dépendances de la Gateway + pytest, `python -m pytest -q`, jeton fictif `ci-test-token` |
| `build` | `build` | `docker:27` + service `docker:27-dind` (TLS), `docker login` avec `$CI_REGISTRY_USER` / `$CI_REGISTRY_PASSWORD` / `$CI_REGISTRY`, puis build et push de `$CI_REGISTRY_IMAGE/{users,orders,gateway}:$CI_COMMIT_SHA` |

- `build` a `needs: [test]` : il ne démarre que si les tests réussissent.
- Le mot de passe est passé par `--password-stdin` (il n'apparaît pas dans la
  ligne de commande ni dans le journal).
- `build` ne tourne que sur la branche par défaut, pour ne pas publier d'images
  depuis des branches de travail.
- Docker-in-Docker exige un runner en mode privilégié : c'est le cas des runners
  partagés de GitLab.com. Sur un runner qui ne l'autorise pas, il faudrait passer
  à Kaniko ou Buildah.

Noms d'images attendus :
`registry.gitlab.com/<groupe>/<projet>/{users,orders,gateway}:<commit-sha>`.

## 8. Partie 6 — Checklist de sécurité

| # | Point | État | Preuve |
|---|---|:-:|---|
| 1 | `.env` exclu de Git | ✅ | `.gitignore`, `git ls-files` ne le liste pas |
| 2 | Jeton exigé sur les endpoints métier | ✅ | tests 401, `preuves/endpoints-local.txt` |
| 3 | Users et Orders ne publient aucun port | ✅ | `docker-compose.yml` (pas de `ports:`) |
| 4 | Communications internes sur un réseau Docker dédié | ✅ | réseau `backend` `internal: true` |
| 5 | Conteneurs non-root | ✅ | `USER app` dans les 3 Dockerfiles |
| 6 | Timeout vers les microservices | ✅ | `timeout=5.0`, test `test_fetch_json_uses_timeout` |
| 7 | Erreurs backend sans détail technique | ✅ | 502 générique, test + preuve curl |
| 8 | Variables prédéfinies du Registry GitLab | ✅ | `$CI_REGISTRY_*` dans `.gitlab-ci.yml` |
| 9 | Images taguées avec le SHA du commit | ✅ | `:$CI_COMMIT_SHA` |
| 10 | Images et dépendances analysées avant la production | ⚠️ partiel | pip-audit et Bandit lancés en local ; **pas encore dans la pipeline** (scan d'image type Trivy à ajouter) |

**Score : 9/10.** Le point 10 relève des améliorations optionnelles de l'énoncé :
il faudrait un job `pip-audit`, un scan d'image (Trivy ou le *Container Scanning*
de GitLab) et une analyse statique avant tout déploiement.

## 9. Limites assumées (rappelées par l'énoncé)

- **Authentification ≠ autorisation** : tout porteur du jeton peut lire tous les
  profils. Il faudrait des jetons par utilisateur (OIDC) et vérifier que l'appelant
  a le droit de lire `/profile/{id}`.
- **Jeton statique partagé** : acceptable en TP ; en production, fournisseur
  d'identité, jetons courts, rotation.
- **Pas de HTTPS** : acceptable sur `127.0.0.1` uniquement.
- **Agrégation sur listes complètes** : il faudrait utiliser
  `/orders/user/{id}` et `/users/{id}` (déjà exposés par les services) et paginer.
- **Pas de limitation de débit** ni de limites de ressources (`mem_limit`, `cpus`).
- **Users/Orders sans authentification propre** : un réseau privé n'est pas une
  authentification ; en production, mTLS ou jeton de service entre la Gateway et
  les microservices.

## 10. Questions de compréhension

**Q1 — Quels avantages l'API Gateway apporte-t-elle ?**
Elle offre un **point d'entrée unique** : le client ne connaît qu'une adresse
(`localhost:3000`) et ignore l'organisation interne. Elle **centralise les règles
transverses** (ici l'authentification Bearer, le timeout et la normalisation des
erreurs), qui ne sont écrites qu'une fois au lieu d'être dupliquées dans chaque
service. Elle **réduit la surface exposée** : seul son port est publié. Enfin,
elle peut **agréger** plusieurs appels (BFF) : `/profile/1` remplace deux
requêtes du client par une seule, exécutée en parallèle côté serveur.

**Q2 — Quels sont ses inconvénients ?**
- **Point de défaillance unique** si elle n'est pas redondée : si la Gateway
  tombe, tout le service est indisponible.
- **Latence supplémentaire** : un saut réseau de plus (et deux appels en aval pour
  `/profile`).
- **Risque de « Gateway obèse »** : si on y met de la logique métier, elle devient
  un monolithe couplé à tous les services.
- **Coût d'exploitation** : supervision, gestion du secret, mises à jour, et c'est
  une cible privilégiée puisqu'elle est exposée.

**Q3 — Comment gérer l'authentification et la sécurité ?**
À la Gateway : valider des **jetons d'accès** (en production OAuth 2.0/OIDC, jetons
courts signés, vérification de l'émetteur, de l'audience et de l'expiration),
**HTTPS** obligatoire hors local, **limitation de débit**, journalisation des
accès. Pour chaque ressource : vérifier l'**autorisation** (l'appelant a-t-il le
droit de lire ce profil ?). Les **secrets** passent par des variables protégées
et masquées GitLab ou un coffre (Vault), avec rotation. Côté réseau : services
internes non publiés, réseau dédié, et idéalement **authentification entre
services** (mTLS ou jeton de service), car les microservices doivent aussi
contrôler l'accès à leurs propres données sensibles. Côté conteneurs :
non-root, lecture seule, `cap_drop`, `no-new-privileges`, images analysées.

**Q4 — Quelle différence entre une API Gateway et un reverse proxy NGINX ?**
Un **reverse proxy** travaille surtout au niveau HTTP : routage par chemin ou
hôte, terminaison TLS, en-têtes, équilibrage de charge, cache, limitation de
débit simple. Une **API Gateway** est orientée **gestion d'API** : authentification
et autorisation des clients, quotas par client ou par clé, transformation et
**agrégation** de réponses (BFF), versionnement, documentation et analytique.
Les deux se recoupent : NGINX (avec modules ou NGINX Plus), Kong (bâti sur NGINX)
ou Traefik peuvent jouer le rôle de Gateway. Dans ce TP, la Gateway FastAPI fait
quelque chose qu'un NGINX simple ne fait pas : `/profile/{id}` compose une
nouvelle réponse à partir de deux services.

## 11. Livrables

| Livrable | Emplacement | État |
|---|---|:-:|
| 3 applications FastAPI | `users/`, `orders/`, `gateway/` | ✅ |
| 3 Dockerfiles | `*/Dockerfile` | ✅ |
| `docker-compose.yml` | racine | ✅ (validé par `docker compose config`) |
| `.gitlab-ci.yml` | racine | ✅ (YAML valide) |
| Tests pytest | `tests/` | ✅ 8/8, `preuves/pytest.txt` |
| Réponses des 3 endpoints | `preuves/endpoints-docker.txt`, `preuves/compose-ps.txt` (et `endpoints-local.txt` hors Docker) | ✅ |
| Capture de la pipeline GitLab réussie | — | ⏳ **utilisateur** (pousser sur GitLab) |
| Capture du Container Registry (3 images) | — | ⏳ **utilisateur** |
| Réponses aux 4 questions | §10 | ✅ |

## À faire par l'utilisateur

1. ~~Docker~~ : fait (preuves dans `preuves/`). Arrêter avec `sudo docker compose down`.
2. **GitLab** : créer un projet sur gitlab.com, ajouter la clé SSH, pousser
   (`git remote add gitlab …` puis `git push -u gitlab main`), vérifier
   *Build > Pipelines* puis *Deploy > Container Registry*, et faire les deux
   captures.
