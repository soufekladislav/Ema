# EMA Ops V1 – chráněný manifest a provozní konzole
**19. listopadu 2026 · produkční přejímka čeká po nasazení**

## Účel
Důsledně oddělujeme: (1) kód v GitHub main, (2) skutečně běžící soubory na Exonu a (3) funkce ověřené při provozním testu. Superadmin čte pouze provozní metadata, nikdy kompletní poštu, hesla, SQL parametry ani přílohy.

## Bezpečný přístup
Chráněný endpoint: **GET /internal/ops/manifest**. Přihlášený platform_superadmin jej může zobrazit a stáhnout v administraci. Externí integrace může přistoupit s vlastním **read-only tokenem v hlavičce Authorization: Bearer ...**. Na Exonu se nastaví jen **EMA_OPS_MANIFEST_TOKEN_SHA256**, tedy SHA-256 otisk tokenu; surový token uložit do Fresh Key nebo schváleného trezoru. Token nikdy nevkládat do URL, GitHubu, screenshotu ani chatu. Neoprávněný uživatel dostává HTTP 403. Machine token neotevírá /superadmin a nepovoluje zápisy.

Příkaz k vygenerování tokenu spustit neveřejně v konzoli:
```bash
python -c "import secrets,hashlib; t=secrets.token_urlsafe(48); print('VAULT_TOKEN:',t); print('EMA_OPS_MANIFEST_TOKEN_SHA256='+hashlib.sha256(t.encode()).hexdigest())"
```
Surový token uložit pouze do trezoru, otisk přidat na Exon do .env. Po nastavení restartovat Passenger. Bez schváleného konektoru/funkční autentizace ChatGPT nemůže manifest průběžně samo číst; lze ho bezpečně stáhnout a přiložit. Nepoužívat anonymní veřejnou URL ani nesdílet přihlašovací údaje.

**Pozor:** veřejný PWA soubor /manifest.webmanifest je samostatná věc a zůstává veřejný bez provozních dat. Operační manifest se nikdy neukládá jako veřejný soubor. Odpověď má no-store a noindex.

## Obsah manifestu
- deployed_code: čitelný Git checkout SHA, nebo pouze správcem zadaná deklarace EMA_DEPLOY_SHA, případně neznámý SHA; dále SHA-256 otisky konkrétních skutečně přítomných zdrojových souborů a celkový fingerprint
- database: živá SQL kontrola, očekávané tabulky/sloupce a chybějící migrace
- counts: agregované počty projektů, organizací, uživatelů, CRM, úkolů, schránek a indexovaných hlaviček pošty, bez identifikace klientů
- mail: poslední synchonizace, počty chyb, poslední IMAP/SMTP kontroly; žádné automatické přihlášení k IMAP při čtení manifestu
- sync_jobs: reálně zapsané provedené pokusy od nasazení evidence; nedokazuje, že je v cPanelu nakonfigurován cron
- recorded_deployments: pouze skutečně spuštěný záznam instalace na Exonu, s otiskem obsahu a časem; GitHub PR žádný záznam nevytváří
- recent_incidents: pouze ID, čas, endpoint a bezpečná kategorie nových HTTP chyb
- audit_summary: počty auditovaných akcí za posledních 24 hodin, bez textu auditovaných záznamů
- release_milestones: popis změn V1.2/V1.3/Ops V1; neoznačuje je za provozně potvrzené

**Omezení:** Manifest automaticky nestahuje GitHub ani serverový crontab, neprokazuje zálohu/obnovu DB, nesbírá staré logy a neukazuje raw traceback. Karel následně porovná souborové otisky se skutečným GitHub SHA, k čemuž bude potřebovat dva samostatné, schválené read-only přístupy.

## Nasazení na Exon
1. Záloha aplikace, databáze a původní konfigurace. Zapsat původní revizi pro rollback.
2. Po zeleném CI nasadit **kompletní aktualizovaný main**; zachovat SECRET_KEY, MAIL_ENCRYPTION_KEY, DATABASE_URL a uživatelská data.
3. Ve správném Python prostředí provést jednorázovou idempotentní migraci:
```bash
python -m flask --app 'ema.web:create_app' upgrade-db
```
Přidávají se pouze nové tabulky ops_incidents, ops_job_runs a ops_deployments; data pošty ani CRM se nepřepisují. Pokud migrace neproběhne, manifest zobrazí chybějící tabulky a nedojde k automatickému mazání či opravě.
4. Po aktualizaci aplikace a migraci zaznamenat skutečně přítomný kód:
```bash
python -m flask --app 'ema.web:create_app' ops-record-deploy --label main
```
Tento krok zjišťuje SHA a SHA-256 otisky přímo z právě nasazených souborů. Nedokončené vydání se nesmí označit za nasazené. Nový záznam nevzniká při opakování stejného fingerprintu.

5. Restartovat Passenger. Otevřít /health, /superadmin a /internal/ops/manifest pod přihlášeným superadminem. Zkontrolovat HTTP 403 při nepřihlášeném přístupu i se špatným tokenem.
6. Při nasazování bez .git lze správcem zadat EMA_DEPLOY_SHA a EMA_DEPLOYED_AT, při každém vydání znovu. Chybějící nebo neověřený SHA se nezastírá; souborové otisky zůstávají dostupné pro porovnání.
7. Pro ověření synchronizace testovací pošty lze jednorázově spustit sync-mailboxes --limit 1 a pak zkontrolovat skutečný záznam v admin konzoli. Samostatně ověřit cron v cPanelu.
8. Provést provozní přejímku poštovních funkcí a teprve poté změnit stav Issues. Vysypání produkčního Koše zde netestovat.

## Bezpečnost a rollback
Každý neočekávaný HTTP 500 má anonymizované ID a endpoint. Detaily jsou jen v chráněných serverových logách; do manifestu se nevkládají e-maily, SQL, hesla ani obsah zpráv. Nové záznamy se sbírají až od aktivace funkce.

Při chybě vrátit předchozí kompletní aplikaci a restartovat Passenger. Nové aditivní tabulky mohou zůstat. Rollback kódu **nevrací IMAP operace** již provedené na serveru.

## Co Ops V1 neuzavírá
- Ostrou přejímku Ema Mail na Exonu (#78)
- DB job queue, skutečné naplánování workeru a jeho recovery (#56)
- Zálohy a test obnovy (#59)
- Plný audit rolí/tenantů a bezpečnostní penetrační testy (#58)
- Google OAuth (#74)
- Workflow Karel / Fresh Key a automatický přístup AI bez uživatelského výslovného propojení
- Rozšíření projektů, akvizičních kampaní a AI Engine o schvalované akce

Nezaměňovat zelené testy za reálné nasazení a provozní ověření.
