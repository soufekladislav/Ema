# EMA / Fresh HUB

AI obchodní a projektová asistentka Fresh Crackers: **chat-first pracovní prostor pro firmy, klienty, e-maily, obchodní příležitosti, nabídky a projekty.**

**Stav produktu (19. 11. 2026):** EMA běží na `hub.freshcrackers.cz`, ale přesná revize nasazená na Exonu **zatím není ověřená**. Uživatel otestoval poštovní rozhraní a potvrdil **úspěšnou instalaci PWA**. **Jednotný release EMA Mail V1.3 je sloučený do `main`** (squash commit `5653800`, [PR #84](https://github.com/soufekladislav/Ema/pull/84)); poslední společná vývojová větev prošla **109 automatickými testy**. V1.3 obsahuje šest finálních úprav pošty. Vyžaduje jednorázovou aditivní migraci `upgrade-db` pro výsledky IMAP/SMTP. PWA instalace neznamená automatické potvrzení všech mailových operací, Gmail OAuth, bezpečného vysypání Koše ani kompletní mobilní přejímky. **[Podrobný aktuální stav a plán](docs/EMA_STATUS_2026-11-18.md)**.

## Zdrojový kód a instalace

- [Aplikace V0.1](ema/)
- [Funkce a lokální spuštění](README_V0.1.md)
- [Nasazení na cPanel/Passenger](docs/DEPLOY_V0.1.md)
- [PR #62 – původní sloučená V0.1](https://github.com/soufekladislav/Ema/pull/62)
- [PR #77 – sloučený poštovní základ](https://github.com/soufekladislav/Ema/pull/77)
- [PR #81 – sloučený EMA Mail V1.2 + mobil + PWA, provozní přejímka zbývá](https://github.com/soufekladislav/Ema/pull/81)
- **[PR #84 – sloučený EMA Mail V1.3 (šest závěrečných úprav)](https://github.com/soufekladislav/Ema/pull/84)**
- **Potvrzená doména:** `hub.freshcrackers.cz`

## Dokumentace a řízení

- **[Aktuální revize Emy – co existuje / co čeká na test / co chybí (19. 11. 2026)](docs/EMA_AUDIT_2026-11-19.md)**
- **[Provozní konzole a chráněný manifest – nasazení a bezpečnost](docs/EMA_OPS_V1_DEPLOY.md)**
- [Historická revize (18. 11. 2026)](docs/EMA_STATUS_2026-11-18.md)
- **[EMA Mail V1.3 – aktuální postup nasazení a závěrečné přejímky](docs/EMA_MAIL_V13_DEPLOY.md)**
- [EMA Mail V1.2 – předchozí historická verze](docs/EMA_MAIL_V12_DEPLOY.md)
- [Master produktové zadání / mapa v1.3](docs/EMA_PROJECT_MAP.md)
- [Původní realizační backlog (historický snímek 16. 11.)](docs/IMPLEMENTATION_BACKLOG.md)
- [Řídicí Issue #1](https://github.com/soufekladislav/Ema/issues/1)
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

**GitHub Project #10:** Issues jsou propojené v epikách, ale skutečný stav položek boardu není v této revizi ověřený. Z aktuálního obsahu repozitáře je ověřeno 47 otevřených a 20 uzavřených Issues; 18 budoucích podúkolů bylo archivováno pro tuto etapu, nikoliv označeno za hotové. Průběžně aktualizovat dnešní revizi a synchronizovat board až na základě skutečné provozní přejímky.
