# EMA / Fresh HUB — funkční základ V0.1

Nová Python/Flask aplikace pro klienty, firemní a projektový chat, obchodní pipeline, úkoly, více poštovních účtů a oddělenou superadmin konzoli.

**Hlavní PRD:** [docs/EMA_PROJECT_MAP.md](docs/EMA_PROJECT_MAP.md) v repozitáři. **Instalace:** [docs/DEPLOY_V0.1.md](docs/DEPLOY_V0.1.md).

## Minimum pro vývoj

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Pro lokální test nastavit DATABASE_URL=sqlite:///ema_local.sqlite a EMA_HTTPS=0
flask --app 'ema.web:create_app' init-db
flask --app 'ema.web:create_app' bootstrap-admin
flask --app 'ema.web:create_app' run --debug
pytest -q
```

Důležité: `SECRET_KEY` musí být silný a jedinečný; `MAIL_ENCRYPTION_KEY` je samostatný Fernet klíč. Žádné skutečné heslo neukládat do repozitáře.

## Design a odpovědnosti

Barvy a typografie podle Bobana (Poppins, zelená `#9EC415`, růžová `#E40058`), levé menu, chat-first workflow. Ema vlastní obchodní data, Karel vývojové projekty. AI Engine bude přidán až nad ověřeným datovým základem.

## Stav funkčnosti

- ✅ Datový model s vazbami, oddělení firem a projektových hostů, superadmin účet, CRM, pipeline, projekty, úkoly, chat.
- ✅ IMAP metadata synchronizace, on-demand náhled max. 32 KiB, SMTP odeslání se základní ochranou proti duplicitě.
- ✅ Serverové formuláře, bezpečnostní CSRF, žádné automatické stahování příloh a žádné default produkční přihlášení.
- ⚠️ Lokální testy/CI a nasazení na hostingu musí potvrdit provoz; V0.1 není hotový plnohodnotný e-mailový klient ani SaaS.
- ⏳ AI Engine, plné MIME/HTML, nabídky a automatizace až v dalších verzích.