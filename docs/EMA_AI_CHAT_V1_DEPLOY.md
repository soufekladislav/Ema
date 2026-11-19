# EMA AI Chat V1 – Fresh AI Engine + konverzace napříč aplikací

**Datum:** 19. 11. 2026 · **Cíl:** zprovoznit skutečný dialog s Emou před dalšími projekty a automatizací.

## Co je v této verzi
1. **Superadmin → Inteligence / Fresh AI Engine** – jednorázové zadání samostatného API konektor klíče pro aplikaci EMA, šifrovaného v MariaDB pomocí existujícího serverového `MAIL_ENCRYPTION_KEY` (Fernet). Nikdy do JS, logu ani ops manifestu, zobrazuje se pouze stav.
2. **Ověřit přístup a kredity** – explicitní placené /v1/engine/run s `Authorization: Bearer`, `source=ema`, `task_type=general` pro samotný test. Veřejný `GET /v1/health` nelze použít pro ověření klíče. V případě 401/402/timeoutu se bezpečně uloží jen kategorie a HTTP kód. Nikdy automaticky neopakovat.
3. **Hlavní chat na úvodní stránce** – samostatné konverzace pro každého uživatele a projekt nebo celkový kontext; volba aktivního chatu, nová konverzace, historie a archivace.
4. **Plovoucí avatar Emy na každé přihlášené stránce** – historie, nový chat, kontext projektu a napsání zprávy. Všude se používá jedna databáze `assistant_threads` a `assistant_turns`, bez duplicitního chatu.
5. **API /v1/engine/run** – modelové odpovědi v češtině, context jen z oprávněných projektů a souvisejících úkolů. `task_type=chat`, `operation=assistant.project.chat`; role AI pouze radí, zatím nezapisuje do CRM, neposílá e-maily a nemění projekty.
6. **Ochrana plateb** – před každým AI voláním se uloží záznam s jedinečným `nonce`. Pokud se HTTP spojení přeruší nebo uživatel znovu odešle stejný požadavek, Ema ho znovu automaticky nespustí. Požadavky s nejasným stavem zůstávají označené jako nejisté.
7. **Stará historie** – původní `assistant_turns` jsou beze ztráty převedeny při prvním čtení daného uživatele/projektu do „Původní konverzace“.
8. **PWA** – servisní worker se aktualizuje, žádná AI data se neukládají do offline cache.

## Provozní nastavení

V AI Engine otevři **API konektory** a vytvoř **samostatný přístupový klíč pro EMA**. Nedávej jí Bobanův klíč. Ve Fresh AI Engine není potřeba vytvářet nový endpoint.

Po nasazení kompletního GitHub `main` na Exon:

1. Záloha kódu a MariaDB, zachovat `.env`, `MAIL_ENCRYPTION_KEY` a aktuální nastavení mailových účtů.
2. V produkčním Python venv:
   ```bash
   python -m flask --app 'ema.web:create_app' upgrade-db
   ```
   Aditivně vzniknou `ai_engine_connectors`, `assistant_threads`, `assistant_submissions` a nový sloupec `assistant_turns.thread_id`. Existující zprávy zůstávají.
3. Restartovat Passenger. Ověřit `/health`, potom `/superadmin`.
4. **Superadmin → Inteligence:** vložit nový API klíč a uložit. Ema jej zašifruje; zpět se nikdy nevypisuje.
5. Zvlášť kliknout **Ověřit přístup a kredity**. Jde o **skutečný účtovaný AI požadavek** s krátkým promptem (nevkládat soukromá data). Musí ukázat `verified` a čas.
6. Otevřít Chat / Nástěnka, napsat první dotaz; ověřit odpověď z AI Enginu. Otevřít e-maily → plovoucí Emu → stejná konverzace pod stejným projektem. Obnovit stránku: historie nesmí zmizet.
7. Ověřit nový chat, archivaci, mobilní PWA, přepnutí projektů a že nepřihlášený / jiný uživatel nevidí cizí vlákna.
8. Zaznamenat skutečné nasazení pomocí již existujícího `ops-record-deploy` a uložit otisk v Superadminu. Nestačí samotný PR v GitHubu.

## Důležité mantinely

- **Nesdělovat API klíč v konverzaci, ticketu ani GitHubu.** Stejný Fernet klíč jako pro poštu musí na Exonu zůstat stabilní; při jeho ztrátě se neobnoví ani uložený AI token.
- Klíč je **pro aplikaci EMA**, zatímco jednotlivé chaty a kontext jsou vždy vázány na přihlášeného uživatele a projektová práva. `user_id` v Engine není účetní identita; kredity se účtují k účtu příslušného API konektoru.
- Stávající `EMA_AI_ENGINE_API_KEY` v `.env` je pouze zpětně kompatibilní pilotní fallback a musí zůstat omezený nenulovým `EMA_AI_ALLOWED_EMAILS`. Ověřený klíč z adminu má přednost; explicitní odpojení blokuje i starý fallback.
- Při timeoutu POST Engine **nikdy automaticky neopakovat**. Uživatel může nejdřív ověřit historii / účtování a případně vědomě zadat novou zprávu.
- **Žádný přístup k obsahu celé pošty:** tento chat dostává jen přístupné projekty a úkoly, nikoliv všechny e-maily, přílohy nebo osobní data klientů.
- Nová vizuální vrstva a testy **nepotvrzují reálnou produkční komunikaci**, dokud ji neověříme přímo na Exonu s platným klíčem.
- Boban má navíc pokročilé chytré karty, hlasové funkce a řídicí akce. Ty nejsou bez rozmyslu překopírovány: Ema musí nejprve spolehlivě konverzovat a držet historii; **realizační kroky a schvalování** připravíme v dalším milníku.

## Zjištěná účtovací / chybová terminologie

- `401`: klíč neplatný
- `402`: nedostatek kreditů
- `400/422`: nesprávný požadavek / kontrakt
- `5xx` / timeout: výsledek nejistý, automatické opakování zakázáno

## Přejímka
Automatické testy pokrývají API kontrakt, přístupové role, šifrované uložení, falešný GET /health, 401/402, historii, archivaci, odmítnutí dvojího volání a umístění tlačítka. Ostrý produkční test po nasazení zůstává samostatný krok.

Další smysluplná etapa: **chat jako řízení práce** – navrhovat úkoly, přiřazení klientů a odpovědi, ve všech případech s potvrzením, auditem a ověřením skutečného výsledku.
