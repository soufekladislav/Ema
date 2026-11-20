# EMA CRM F1 – kontakty z Fresh Core a CSV

**Status:** implementace v kódu, nutná reálná přejímka na Exon + WordPress. Nejde o modul hromadného odesílání.

## Reuse, UX, stabilita
- Využívá existující CRM (Company/Contact), CSV parser, firmová ACL. Jen dvě malé tabulky: contact_origins (více zdrojů jednoho kontaktu) a fresh_core_sources (URL, šifrovaný přístup, kurzory). Žádná duplicitní zákaznická databáze.
- Na obrazovce Databáze / CRM: hledání jména/e-mailu/firmy, filtrování vlastníka/webu/typu zdroje, připojení WP webu v jediné sbalené nabídce, náhled a synchronizace. CSV přes stávající funkci.
- HTTPS, pouze veřejné weby bez přesměrování, žádné klíče v JS ani URL, přístup po firmách, odolnost vůči opakovanému importu, neodesílá e-maily.

## Kontrakt
Fresh Core 0.7.9, existující povolený Accounting READ přístup pro Edu. Nezaměňovat s invoice WRITE klíčem.

GET /wp-json/fresh-core/v1/accounting/contacts?kind=users&after_id=0&limit=50
GET /wp-json/fresh-core/v1/accounting/contacts?kind=elementor_submissions&after_id=0&limit=50

HTTP hlavička: X-Fresh-Core-Accounting-Key. Odpověď ok, available, site, kind, items, next_after_id, has_more.

WordPress firemní administrátorské/editor účty se přeskočí. Elementor formuláře exportují jen rozpoznaná kontaktní pole (email, jméno, telefon, firma), nikoli plný text zpráv. **Pokud formulář používá nestandardní pole ID, je nutné na webu nastavit vhodné custom_id; neexportovat obecně všechny hodnoty.** Elementor Pro bez uchovávání submissions může vrátit available=false.

## Nasazení
1. Ověřit zelené CI obou repozitářů a zálohovat WP plugin i Emu + MariaDB.
2. Nasadit nejprve nový Fresh Core 0.7.9; zkontrolovat dosavadní Edu Accounting / objednávky. Nový kontaktní endpoint používá tentýž READ key.
3. Nasadit Emu z main a spustit na skutečném serveru ve stávajícím virtualenv:
   python -m flask --app 'ema.web:create_app' upgrade-db
   Migrace vytvoří jen pomocné tabulky, staré kontakty a e-maily nepoškodí.
4. Restartovat Passenger, v CRM zkontrolovat existující kontakty, připojit web + Accounting READ klíč (vyžaduje stávající MAIL_ENCRYPTION_KEY), zobrazit náhled a provést synchronizaci.
5. Jeden klik synchronizuje max. tři stránky po 50 řádcích pro každý zdroj. Je-li pokračování, kliknout znovu; kurzor je uložen spolu s daty.
6. CSV se shodným e-mailem musí kontaktu přidat nový původ, ne založit duplicitního člověka. Neodvozovat marketingový souhlas.

## Volitelná automatická synchronizace
Po reálné přejímce může Exon/cPanel cron ve 05:00 volat v aplikaci:
   python -m flask --app 'ema.web:create_app' sync-contacts --pages 3

Spouštět ze správného projektového adresáře a venv. Přesné cesty zjistit v Exon; nejsou zakódované. Příkaz vrací počty a stav bez osobních údajů. Při výpadku zdroje se dávka vrací a chyba zůstane v CRM.

## Přejímka testerem
- Připojení webu, náhled a import reálné testovací WP registrace + Elementor Submissions.
- Dvě shodné adresy z WP registrace a formuláře = 1 Contact, 2 originy.
- Import CSV se stejným e-mailem = 1 Contact, 3 originy.
- Druhý běh bez duplicit, filtr podle CSV/Web/formuláře, hledání dle jména a e-mailu.
- Dvě organizace nesmějí vidět data jedna druhé, projektový host nesmí získat celofiremní CRM.
- Chybné připojení a chyba uprostřed dávky: bez částečně potvrzeného importu.
- Telefon 360–430 px, tablet 768 px, desktop >1024 px: vyhledávání, formuláře a tabulky použitelné.
- Kontrola původní Eda fakturace, odesílání pošty a Superadmin.
- Výsledek na serveru potvrdit odděleně: CI není potvrzení nasazení.

## Mimo tento milník
Hromadné e-maily, jejich oprávnění, opt-out a schvalování, obchodní pipeline a dvousměrná editace zdrojů. Nikdy není automatický marketingový souhlas jen díky WP registraci či odeslání formuláře.
