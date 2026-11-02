# NOVA SERVICES — API Gateway et microservices sécurisés

TP « API Gateway et microservices sécurisés avec Docker Compose et GitLab CI/CD ».
Boutique en ligne fictive : services **Users** et **Orders** (FastAPI) derrière une
**API Gateway** (FastAPI) qui applique l'authentification et agrège les données (BFF).

```
Client ──HTTP──▶ 127.0.0.1:3000 ──▶ gateway:8000 ─┬─▶ users:8000   (réseau backend interne)
                                                  └─▶ orders:8000  (aucun port publié)
```

## Structure

```
api/
├── users/      main.py · requirements.txt · Dockerfile
├── orders/     main.py · requirements.txt · Dockerfile
├── gateway/    main.py · requirements.txt · Dockerfile
├── tests/      test_gateway.py (énoncé) · test_gateway_securite.py (ajouts)
├── preuves/    sorties pytest et curl
├── docker-compose.yml · .dockerignore · .gitignore · .env.example
├── .gitlab-ci.yml
└── RAPPORT.md  choix de sécurité, checklist, réponses aux questions, livrables
```

## Démarrer

```bash
cp .env.example .env
sed -i "s/COLLER_ICI_LE_JETON_GENERE/$(openssl rand -hex 32)/" .env
docker compose config -q
docker compose up --build -d
docker compose ps                       # 3 services « healthy »

set -a; source .env; set +a
curl -i http://localhost:3000/users                                   # 401
curl -i -H "Authorization: Bearer $GATEWAY_TOKEN" http://localhost:3000/profile/1
docker compose down
```

## Tests

```bash
python -m venv .venv && . .venv/bin/activate
python -m pip install -r gateway/requirements.txt pytest
GATEWAY_TOKEN=ci-test-token python -m pytest -q    # 8 passed
```

Voir [`RAPPORT.md`](RAPPORT.md).
