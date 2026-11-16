# EMA / Fresh HUB

AI obchodní a projektová asistentka Fresh Crackers: **chat-first pracovní prostor pro firmy, klienty, e-maily, obchodní příležitosti, nabídky a projekty.**

**Stav:** první implementace **EMA HUB V0.1** je uložena v `main` (sloučený PR #62); GitHub Actions V0.1 testy prošly. **Na serveru zatím nebyla nasazena ani provozně otestována.**

## Zdrojový kód a instalace

- [Aplikace V0.1](ema/)
- [Funkce a lokální spuštění](README_V0.1.md)
- [Nasazení na cPanel/Passenger](docs/DEPLOY_V0.1.md)
- [PR #62 – sloučená V0.1](https://github.com/soufekladislav/Ema/pull/62)
- **Potvrzená doména:** `hub.freshcrackers.cz`

## Dokumentace a řízení

- [Kompletní projektová mapa / PRD v1.1](docs/EMA_PROJECT_MAP.md)
- [Realizační backlog — všech 61 GitHub Issues](docs/IMPLEMENTATION_BACKLOG.md)
- [Řídicí Issue a fáze F0–F5](issues/1)
- [GitHub Project #10](https://github.com/users/soufekladislav/projects/10)

## Architektura a mantinely

- Python / Flask / Passenger na cPanel, MariaDB, Fresh AI Engine a Fresh Key dle ověřených rozhraní.
- Jeden login může pracovat ve více firmách. Každá má vlastní CRM, firemní chat, schránky a projekty; projektový host nemá implicitní práva firmy.
- IMAP je zdrojem pošty, SMTP pro odeslání. Synchronizace je metadata-first a nikdy automaticky nestahuje a nearchivuje všechny přílohy.
- AI připravuje návrhy; závazné akce se provádějí podle pravidel oprávnění a schvalování.
- Ema vlastní obchodní projekty; Karel jejich technickou/development realizaci; Eda faktury; Boban akvizici; Linda sítě; Viki produktové katalogy.
- UI vychází ze stylu Bobana: Poppins, levé menu, hlavní chat a pravé kontextové karty.

## Bezpečnostní upozornění

Nikdy neukládat do GitHubu historické produkční konfigurace, hesla, soubory .env, error logy ani klientskou poštu. Doména D-01 je potvrzena: `hub.freshcrackers.cz`. Před nasazením zajistit zálohu původní PHP Emy na stejné doméně.

**GitHub Project #10:** Issues jsou založené a propojené v epikách. Přidání existujících Issues do samotného project boardu vyžaduje hromadné přidání položek v GitHubu (postup v realizačním backlogu).
