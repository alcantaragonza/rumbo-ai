# Despliegue

## Recursos

- **Base de datos**: proyecto Neon `rumbo-ai-db` (`shy-art-05870077`), base `rumbo`, región
  `aws-us-east-2`.
- **Aplicación**: Fly.io, app `rumbo-ai`, región `ord`, un contenedor que sirve la API y la SPA.
- **Repositorio**: `github.com/alcantaragonza/rumbo-ai`, rama `main`.

No se reutilizan `planubi-db` ni `planubi-api`.

## Secretos de Fly

```bash
flyctl secrets set \
  DATABASE_URL='postgresql+psycopg://USUARIO:PASSWORD@HOST/rumbo?sslmode=require' \
  SESSION_SECRET='un-secreto-largo-y-aleatorio' \
  -a rumbo-ai
```

Opcional para respuestas reales del LLM:

```bash
flyctl secrets set GROQ_API_KEY='...' -a rumbo-ai
```

La configuración versionada usa `ENV=production`, cookies `Secure` y el modelo
`openai/gpt-oss-20b`. `GROQ_API_KEY` debe existir como secreto de Fly.

## Despliegue manual

```bash
flyctl deploy --remote-only -a rumbo-ai
```

El `Dockerfile` construye el frontend y la imagen Python. El `release_command` de `fly.toml` ejecuta
`alembic upgrade head` antes de liberar la nueva versión. Si la migración falla, Fly no promueve el
despliegue.

Comprobación:

```bash
curl https://rumbo-ai.fly.dev/health
```

## CI/CD

`.github/workflows/ci-cd.yml` tiene dos jobs:

1. `quality`: en cada push y pull request ejecuta `ruff`, `mypy`, build del frontend, migraciones y
   `pytest` contra un servicio PostgreSQL con `pgvector`.
2. `deploy`: solo en push a `main` y solo si `quality` pasó. Usa `flyctl deploy --remote-only`.

Para habilitar el deploy, crea un token de despliegue y guárdalo como secreto de GitHub:

```bash
flyctl tokens create deploy -a rumbo-ai
gh secret set FLY_API_TOKEN -R alcantaragonza/rumbo-ai
```

Un commit con pruebas rojas no llega al job `deploy` porque depende de `quality`.

## Rollback

```bash
flyctl releases -a rumbo-ai
flyctl deploy --image <imagen-de-la-versión-anterior> -a rumbo-ai
```

Para revertir una migración:

```bash
DATABASE_URL='...' uv run alembic downgrade -1
```

Revisa siempre `alembic history` y el `release_command` antes de revertir en producción.
