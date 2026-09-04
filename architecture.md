project/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── dependencies.py
│   │   ├── router.py
│   │   └── v1/
│   │       ├── users.py
│   │       └── orders.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── logging.py
│   │
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── user.py
│   │   │   └── order.py
│   │   ├── repositories/
│   │   │   ├── user.py
│   │   │   └── order.py
│   │   └── exceptions.py
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   │   ├── session.py
│   │   │   ├── models/
│   │   │   │   ├── user.py
│   │   │   │   └── order.py
│   │   │   └── repositories/
│   │   │       ├── user.py
│   │   │       └── order.py
│   │   ├── cache/
│   │   └── external/
│   │
│   └── schemas/
│       ├── user.py
│       └── order.py
│
├── migrations/
│   └── versions/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docker/
│   ├── Dockerfile
│   └── entrypoint.sh
│
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
