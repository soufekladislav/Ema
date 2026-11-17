# EMA — chat jako hlavní pracovní prostředí (UX + funkční pilot)

**Zadání uživatele 17. 11. 2026:** Ema je **asistentka**, ne katalog firem, projektových formulářů ani samostatný týmový chat. Celou aplikaci (včetně přihlášení) vizuálně přiblížit Bobanovi. Každá konverzace může mít vybraný projekt, ale z hlavního chatu lze řešit i přehled všech přístupných projektů.

## Implementovaná etapa – PR tohoto návrhu

- Přihlášení: dark-mode, velký claim vlevo, kompaktní přihlašovací formulář vlevo, ilustrace Emy vpravo, logo a stejné základní vizuální prvky jako Boban.
- Úvod: hlavní AI chat uprostřed, projektový kontext a přístupné projekty vpravo. V levém menu jsou projekty pro rychlé přepnutí kontextu, ale uživatel **zůstává v jednom chatu Emy**.
- Kontext: `/?project=ID` = osobní konverzace o konkrétním projektu, `/` = osobní přehled všech přístupných projektů. Asistent nikdy neprohledává celou databázi a neodhaluje projekty bez explicitního členství/pozvánky. Na projektovém detailu zůstávají týmové poznámky oddělené od asistenta.
- Historie AI konverzace je oddělená v nové tabulce `assistant_turns`, ukládá se na uživatele a kontext projektu. Nepoužívá společné firemní poznámky `chat_messages`.
- Fresh AI Engine je integrován **server-side** přes `POST /v1/engine/run`, typ `general`, operace `assistant.project.chat`; 1 požadavek = 1 billable úloha, bez automatických retry. Odpověď se nezfalšuje, při chybě je viditelné hlášení.
- Jen čtení: pro AI se exportují pouze názvy/stavy/krátké popisy projektů uživatele + úkoly vybraného projektu a limitovaná historie. Žádné plné e-mailové zprávy, hesla, faktury nebo soukromá data cizích projektů. AI nesmí provádět automatické změny, schvalovací akce jsou samostatná budoucí etapa.
- Povolení AI vyžaduje jak `EMA_AI_ENGINE_API_KEY`, tak explicitně povolený e-mail v `EMA_AI_ALLOWED_EMAILS`. Výchozí nastavení je vypnuto.
- Migrace: `flask --app ema.web:create_app upgrade-db` přidá chybějící `mailboxes.smtp_username` a `mailboxes.signature_html` bez smazání obsahu a vytvoří tabulku AI historie. Je opakovatelná a neodstraňuje tabulky.
- Vizuální detaily lze dál ladit podle screenshotů lokálního nasazení.

## Lokální nasazení / oprava chyby sqlite „no such column: mailboxes.smtp_username“

Vypnout běžící Flask (`Ctrl + C`) a v Git repozitáři na Windows CMD:

```cmd
cd /d "C:\Users\ladis\Documents\GitHub\Ema"
git status
git pull --ff-only origin main
.venv\Scripts\activate.bat
copy ema_local.sqlite ema_local.backup.sqlite
python -m flask --app ema.web:create_app upgrade-db
python -m pytest -q
python -m flask --app ema.web:create_app run --port 5000 --debug
```

**Pozor:** Příkaz `copy ema_local.sqlite` platí pouze pokud SQLite soubor opravdu leží v kořenu repozitáře. Skutečnou cestu lze ověřit podle `DATABASE_URL` v místním `.env` bez zveřejňování hesel. Stávající uživatelská data a projekty se nemají mazat. Pokud je databáze umístěna jinde, zálohovat skutečný soubor.

**Test AI (volitelné):** v lokálním `.env` doplnit oddělený API klíč Emy, např. `EMA_AI_ALLOWED_EMAILS=soufek@freshcrackers.cz`. Nikdy neposílat klíč v chatu ani do Gitu. Restartovat Flask. Dokud není test AI schválený, klíč může zůstat prázdný a chat viditelně uvede „AI zatím není připojena“.

## Co tato etapa NEŘEŠÍ

- Samostatné AI workflow **navrhni → schval → proveď → ověř** pro vytváření projektů, e-maily nebo CRM.
- Automatické procházení mailů a připojení souvisejících e-mailových vláken ke klientovi/projektu.
- Více vláken chatu v jednom projektu, vyhledávání historie a přílohy.
- Správu tenantových AI kreditů a licencí zákazníků. Pilotní API klíč má sloužit pouze pro explicitně povolené testovací uživatele, nikoliv bez omezení všem zákazníkům.
- Produkční rate limiting, robustní fronta AI úloh a provozní monitoring. Před produkcí je nutné doplnit minimálně per-user kvóty/rate limits a bezpečnostní kontrolu.

**Hlavní princip:** Projekt určuje data, se kterými Ema pracuje; chat je ovládací rozhraní. Firma zůstává hranicí pro data, fakturaci a oprávnění.
