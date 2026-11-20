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


## Oprava více webů: WordPress home_url / www (20. 11. 2026)

**Pozorované:** Adrenaline Race načetl kontakty, Fresh Crackers při připojování vracel „neplatná nebo neočekávaná kontaktní data“. Ema má podle ops manifestu 85 kontaktů, schéma OK; screenshot zároveň ukazuje filtr `org=1`, nikoli nutně organizaci, do které byly AR kontakty importovány. Není potvrzeno, že by existující kontakty zmizely.

**Identifikované slabé místo parseru:** Fresh Core odpovídá `site = home_url('/')` ze svého WordPress nastavení. Ema dříve vyžadovala doslovnou shodu `hostname` mezi URL použitou pro HTTPS API a deklarovanou URL webu. To odmítne běžné a bezpečné rozdíly `www.example.cz` ↔ `example.cz` a konfiguraci `http` za HTTPS reverzní proxy.

**Úprava:** Pouze Ema načítací parser. HTTPS a validace veřejné adresy zůstávají povinné pro síťové požadavky, žádné HTTP připojení s klíčem ani automatické přesměrování. URL uvedená v JSON je výhradně identifikační metadata a akceptuje pouze stejnou doménu se/bez jediného prefixu `www.`, nezávisle na schématu uložené WordPress adresy. Cizí domény stále odmítá. Neotevírá žádná nová oprávnění a nezasahuje do Fresh Core, fakturací ani CRM databáze.

**Diagnostika:** Chybný JSON, jiný typ dat, neoprávněný web, neplatné stránkování nebo jiné doménové jméno nyní vrací odlišné srozumitelné chyby bez výpisu obsahu kontaktů či klíče.

**Přejímka:** Připojit Fresh Crackers znovu pod správnou firmou, provést `Náhled` a `Synchronizovat`. Ověřit kontakty ve filtrech, opakovaný sync bez duplicit a stále funkční AR. Pokud chyba přetrvá, nové hlášení určí její kategorii; v takovém případě přiložit pouze hlášení, nikoli READ klíč či odpověď API s osobními údaji.

## CRM UI po importech (20. 11. 2026)

**Zjištěná chyba rozhraní:** CRM bylo ve stejné Jinja šabloně vykreslené dvakrát: nový filtr/seznam ve společné horní části a starý seznam klientských firem ve spodní části. Nešlo o dvě databáze, ale dvě neodstraněné prezentace stejných dat.

**Oprava bez databázové migrace:** nahoře čtyři statistiky (kontakty celkem, WordPress, Elementor, CSV) v rámci aktuálně zvolené vlastní firmy / všech přístupných firem. Statistické skupiny se mohou překrývat, protože jeden kontakt smí mít více zdrojů. Následuje jedna sbalená nabídka „Importy a propojení“ (existující weby, jejich synchronizace, CSV, správa klientských firem), potom jediné vyhledávání a tabulka po **50 kontaktech**, skutečné stránkování a zdroje seskupené do jedné značky na web/typ. Originální ContactOrigin řádky se nemažou ani nepřepisují.

**Přejímka:** desktop/tablet/mobil – statistiky se nelámou, ovládání sbalené nabídky funguje dotykem/klávesnicí, do tabulky se vejde max. 50 kontaktů včetně poslední krátké stránky, filtr funguje napříč stránkami, stejné formuláře jednoho webu jsou jako jeden čitelný štítek s počtem opakování, správa existujících klientských firem je zachována v rozbalovací nabídce. Celkem z ops manifestu 20. 11. 2026: 290 kontaktů pro čtyři organizace, ale produkční počty si musí uživatel po nasazení zkontrolovat (mohly se mezitím změnit).

**Spam není součástí tohoto CSS/UX PR.** Pro AI návrh, kontrolu a schvalovaný Trash existuje samostatné [EMA #95](https://github.com/soufekladislav/Ema/issues/95) a [WP-Fresh-Core #3](https://github.com/soufekladislav/WP-Fresh-Core/issues/3), aby nebyla nevratně smazána legitimní WordPress registrace nebo jiný původ stejného kontaktu.

## Mimo tento milník
Hromadné e-maily, jejich oprávnění, opt-out a schvalování, obchodní pipeline a dvousměrná editace zdrojů. Nikdy není automatický marketingový souhlas jen díky WP registraci či odeslání formuláře.
