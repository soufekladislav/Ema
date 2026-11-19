# EMA – AI Engine a jednotný chat V1
**19. 11. 2026 · PR bude sloučen do main po zeleném CI**

## Vstupní kontrakt
Zdroj: uživatelem dodaná specifikace `https://aiengine.freshcrackers.cz/account/developer-api`. Ema používá **existující univerzální** `POST /v1/engine/run` s `Authorization: Bearer <API_KEY>`, `source=ema`, `task_type=chat`, `operation=assistant.project.chat`, `quality=balanced`, `max_cost_usd=0.20`, `max_output_tokens=1200`. Není požadován nový endpoint v Engine. `GET /v1/health` by neověřil přístupový klíč, proto **Ověřit spojení** provede jeden explicitní, potenciálně účtovaný synchronní request. Při timeoutu se automaticky neopakuje.

## Co je hotové v kódu
1. **Superadmin → Inteligence:** vložení/obnovení samostatného klíče konektoru EMA, zašifrování Fernetem (použije stávající `MAIL_ENCRYPTION_KEY`), maskování, zobrazování posledního ověření a stavu. Nový klíč vždy ruší předchozí ověření. Klíč ani v diagnostickém JSON, HTML, JavaScriptu nebo auditním targetu.
2. **Ověřit spojení:** explicitní autorizační test přes /v1/engine/run (může stát kredity), stav `ok` nebo `failed`. HTTP 401, 402 a síťové chyby se zobrazí bez tajných údajů. Čtení administrace samo test nevykonává.
3. **Hlavní chat po přihlášení:** názvy a výběr předchozích rozhovorů; nový rozhovor, uložení historie a volitelný kontext přístupného projektu. Původní historie z `assistant_turns` se aditivní migrací převede do soukromých vláken `Původní konverzace`.
4. **Plovoucí chat na každé přihlášené stránce:** stejně jako Boban, ale ne kopie jeho služby. Otevírá pravý drawer, historii `/assistant/threads`, stejnou databázi `assistant_turns`, společný odesílací endpoint `/assistant/api/message`. Desktop a mobil, bez nebezpečného `innerHTML`, text se vkládá pomocí `textContent`.
5. **Oprávnění:** vlákna jsou výhradně pro `user_id`, u projektového vlákna se znovu kontroluje ACL. Žádná pošta, přílohy ani neveřejné CRM údaje se neodesílají automaticky jako AI kontext; pouze omezený dostupný popis projektu a úkoly.
6. **Bez duplicitních účtovaných volání:** každý POST má jedinečný nonce uložený v `assistant_message_attempts` před voláním Engine; opakování stejného nonce se odmítne. U timeoutu nelze prokázat doručení – uživatel musí stav vyřešit bez automatického opakování.

## Důležitá omezení V1
- Ema stále **nic nemaže, neodesílá a nepřepisuje**; odpovídá a navrhuje. Návrhy úkolů / CRM zápisy přijdou až s řízeným schvalováním.
- Není implementovaná pokročilá asynchronní fronta `POST /v1/engine/jobs`, streaming, nákladové reporty po všech modelech, sdílení vláken mezi uživateli ani automatický export konverzací. Jen synchronní dialog.
- Jedna platformová konektorová identita znamená, že účtování AI Engine probíhá dle propojeného zákaznického účtu tohoto klíče, **nikoli** dle `user_id` z payloadu. Správce musí kontrolovat kredity a limity na straně Engine.
- Pro první ostrý test postačí **vlastní samostatný connector key aplikace EMA**. Fresh Key není nutná podmínka základního volání.
- Samotné úspěšné CI **není** ověření, že server Exon komunikuje s Engine nebo že je konektor dostatečně kreditovaný.

## Nasazení na Exon
1. Zálohuj aplikaci, MariaDB a produkční `.env`. Nasazuj jeden kompletní GitHub `main` po zeleném CI; nepřepisuj `MAIL_ENCRYPTION_KEY`, `DATABASE_URL` ani `SECRET_KEY`.
2. V produkčním Python/Passenger prostředí spusť idempotentní aditivní migraci:
   ```bash
   python -m flask --app 'ema.web:create_app' upgrade-db
   ```
   Přidá `ai_engine_connections`, `assistant_threads`, `assistant_message_attempts`, nullable `assistant_turns.thread_id` a převede existující zprávy do osobních vláken bez smazání.
3. Restartuj Passenger. Přihlas se jako superadmin, otevři `/superadmin#ops-intelligence`, vlož **klíč vytvořený v AI Engine → API konektory** (ne sem do chatu).
4. Klikni **Bezpečně uložit klíč**, potom vědomě **Ověřit spojení a kredity**. Jeden test může být účtován. Pokud je stav `failed`, diagnostikuj práva a kredity, nepřepínej nic automaticky.
5. Po úspěšném ověření otevři `/`, vytvoř rozhovor a odešli krátký test. Na `/mail` otevři plovoucí chat a ověř, že vidí tentýž rozhovor. Obnov stránku, vyber historii, založ nový rozhovor a ověř mobilní drawer.
6. Ověř 403/404 pro cizí vlákno, správnost kontextu projektu a žádné tajné údaje v HTML, logu nebo manifestu.
7. Teprve po skutečné přejímce označ napojení jako provozně funkční. Záložní vydání uchovat pro rollback, nové DB tabulky neodstraňovat.

## Další krok
Po přijetí dialogu: Ema rozpozná příchozí poptávku a **navrhne** CRM kontakt, obchodní příležitost, úkol a odpověď; uživatel samostatně schválí každou aktivní změnu. Následně propojení s Karlem a dalšími agentními aplikacemi přes oddělená oprávnění.
