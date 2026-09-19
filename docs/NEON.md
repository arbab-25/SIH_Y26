# Neon environment

This workspace is linked to the `production` branch of Neon project `misty-term-18610406` (`FINAL`) in `aws-ap-southeast-1`.

## Deployed function

- Slug: `api`
- Source: `hello.ts`
- Runtime: Node.js 24
- URL: https://br-damp-fire-b3m4492q-api.compute.c-4.ap-southeast-1.aws.neon.tech/
- Verified response: `Hello from Neon Functions`

## Commands

```text
neon status
neon config plan
neon deploy
neon functions get api -o json
```

`.neon` identifies the linked project and branch. `.env.local` contains Neon-managed connection and service variables. Both are ignored and must never be committed or shared.

The existing CODE MAZE FastAPI deployment remains the application API. The current Neon Function is a verified platform integration endpoint; migrating or duplicating the FastAPI API into it requires a separately scoped backend migration.
