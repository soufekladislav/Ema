# EMA: pracovní struktura, role firem, mailů a projektů — verze 1.4

**Uživatelské rozhodnutí: 17. 11. 2026.** Ema je obchodní a projektová asistentka, která má převzít první orientaci v komunikaci. Firma je primárně **právní, účetní a GDPR tenant**, ne prvek hlavního menu.

## Pevné menu (uživatelský pohled)

1. **Chat / Nástěnka** — jeden hlavní dialog s Emou + skutečné připomínky úkolů, navazující obchodní souvislosti.
2. **E-maily** — jedno zobrazení všech schránek, ke kterým má uživatel přístup, volitelný filtr schránky. Přístup není odvozen jen od přístupu k projektu. AI selekce a vazby na objednávky navazují.
3. **Projekty** — hlavní pracovní kontext a další vrstva kategorizace za e-mailem: e-shop, marketing/obchodní kampaň, vývoj, ostatní. Projekt může mít vlastní pipeline, úkoly, přiřazené klienty a později komunikaci a objednávky.
4. **Databáze / CRM** — souhrnný přehled klientů a kontaktů, s jednoznačným vlastníkem firmy. CSV import do zvolené firmy (náhled bez zápisu, nahrání, deduplikace e-mailu v rámci firmy a volitelná metadata). WooCommerce synchronizace přes Fresh Core další etapa.
5. **Úkoly / Plánovač** — deadline a stav napříč projekty a oprávněnými firmami; souhrn otevřených na hlavní nástěnce.
6. **Nastavení účtu** — přidání prvotní firmy, správa firemních členství, přístupů a e-mailových účtů. Superadmin provozu zůstává samostatný.

**Filtr vpravo nahoře:** `Všechny moje firmy` / konkrétní firma. Vybírá pouze z firem, kde má uživatel členství. Nejde o přístupové oprávnění, pouze o filtr dat, nad nimiž už má uživatel právo.

## První přihlášení

Na novém účtu se musí nabídnout založení první firmy, i když nejsou žádné firmy, projekty ani schránky. Původní rozhraní mělo chybu: formulář byl skrytý v bloku `if orgs`. Po vytvoření firmy vzniká členství `owner`; projekt může vzniknout následně. Admin platformy **není automaticky členem všech cizích firem**.

## Datové hranice

- `organizations` = oddělený právní/účetní kontext, důležitý pro Eda, GDPR a přístupy.
- `projects.organization_id` = povinné vlastnictví; `projects.kind` = `shop|campaign|development|other`.
- `opportunities.project_id` = přiřazená obchodní příležitost; pipeline může být filtr firmy nebo projektu.
- `contacts.organization_id` a `companies.organization_id` = klientská databáze oddělená od ostatních firem.
- `contacts.metadata_json` = doplňková pole z importu CSV, eviduje zdroj CSV a čas importu. Marketingový souhlas se **neodvozuje** z importu.
- `mailboxes.organization_id` = firma je vlastníkem mailboxu. Právo na projekt samo o sobě **nestačí** k přístupu k firemnímu mailu.
- `mail_messages.project_id` již existuje; UI nyní umí vazbu nastavit manuálně. Ema bude později klasifikovat a navrhovat přiřazení, ne automaticky přeřazovat bez kontroly.
- `tasks.project_id` = může být projektový nebo firemní; host projektu vidí jen své projektové úkoly.

## Stav etap

**Dodáno touto verzí:** pevné menu, přístupově filtrované souhrnné přehledy, funkční založení firmy z prázdného účtu, typy projektů a pipeline, CSV import kontaktů s metadaty, centrální deadline, připomínky na nástěnce. **Není hotové:** napojení Fresh Core, automatické třídění e-mailů a přiřazování k Woo objednávkám, import produktů/objednávek, schvalovací AI akce, fakturace a integrace s Edou.

## Instalace na Exon po aktualizaci GitHub `main`

1. Zálohovat současnou MariaDB `lauhannq_hub` z Exonu, včetně údajů uživatelských účtů a nově vytvořených firem.
2. Aktualizovat kód Python aplikace z GitHub `main`.
3. **Jednorázově** v aktivním virtualenv v kořeni Emy spustit `python -m flask --app ema.web:create_app upgrade-db`.
4. Příkaz přidá pouze chybějící sloupce `projects.kind` a `contacts.metadata_json`; zároveň zachová starší kompatibilní upgrade pošty. Nenahrává žádná cizí data, nemaže tabulky.
5. Restartovat aplikaci v cPanel `Setup Python App`, otevřít `/account`, `/projects`, `/mail`, `/database`, `/tasks`, `/`.

### Import nastavení původních schránek

Pro přechod z PHP Emy existuje **soukromý** instalační balíček `EMA_v01_SQL_instalacni_sada.zip` s `02_EMA_v01_IMPORT_6_SCHRANEK.sql` a odděleným privátním `EMA_PRIVATE_MAIL_KEY.txt`. SQL2 obsahuje šest již převedených Fernet ciphertextů a vytváří šest firemních prostorů včetně mailboxů, **nikoli historické e-maily**. **Nenahrávat do GitHubu.**

Bezpečné předpoklady importu: aktuální DB je **nová Python EMA** se založenými tabulkami, superadmin odpovídá účtu očekávanému v soukromém SQL importu, `MAIL_ENCRYPTION_KEY` v Exon `.env` je přesně klíč pro dané ciphertexty, není povolen neomezený synchronizační cron a existuje záloha před importem. SQL2 je navržen idempotentně pro nové mailboxy, ale musí být nejprve ověřeno proti skutečnému stavu databáze. **Nespouštět čistící SQL1 na již provozované Ema DB**. Pokud šifrovací klíč nesouhlasí, bude nutná řízená re-encryption nebo nové připojení schránek — pouhé vložení šifrovaných hodnot nestačí.

SQL dump původní PHP aplikace `lauhannq_hub.sql` je odlišné schéma a obsahuje citlivá uživatelská data. **Nesmí se obnovovat přes aktuální Python DB.** Převody původních kontaktů/projektů/pošty musí být oddělenou a ověřenou migrační úlohou.

## Další priority

1. AI třídění e-mailů (důležité, spam, follow-up, objednávky), návrhy přiřazení k projektu a klientovi, **schválení uživatelem**, bez automatického odesílání.
2. Fresh Core synchronizace zákazníků a Woo objednávek s deduplikací, mapováním na firmu + shop projekt a dohledatelným stavem sync.
3. Zpravování pipeline do celkového kanbanu s termíny a obchodními metrikami, poctivé oddělení obchodního úkolu Emy od vývojového řízení Karla.
4. Správa firemních účetních údajů, fakturace a předávání podkladů Edovi přes Fresh Key/Fresh Core.
5. Audit retenčních lhůt, právní titul kontaktu, export/smazání dat zákazníka, limity AI a provozu.
