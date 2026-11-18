# EMA Mail V1.3 – šest závěrečných provozních oprav
**Datum:** 18. 11. 2026 · **PR:** [#84](https://github.com/soufekladislav/Ema/pull/84)

## Vydání a bezpečnost
Toto vydání napravuje šest konkrétních připomínek bez přepisování poštovní architektury. **IMAP zůstává zdrojem pravdy**, zprávy/přílohy se neukládají do MariaDB. **Nikdo neprovedl ostré vyprázdnění Koše ani neodesílal reálné testovací zprávy** během vývoje.

### 1. HTML jako bezpečná samostatná stránka
- Odesílatelův HTML obsah se zobrazuje v izolovaném iframe s blokovanými skripty/formuláři.
- Poppins je fallback, pokud jej nedefinuje samotný e-mail.
- Zůstávají tabulkové atributy width/height, styly buněk a bezpečné CSS včetně media pravidel; už se nevynucuje padding 4px a border-collapse na každou tabulku.
- Převádí se bezpečné inline body CSS, HTML/CID obrázky. Vzdálené obrázky jen po souhlasu.
- **Omezení:** u některých newsletterů s externí CSS nebo vzdálenými CSS background obrázky nelze slíbit pixel-perfect shodu s Roundcube. Bezpečnost a ochrana před trackingem má přednost.

### 2. „Vysypat Koš“ se týká pouze přesně vybrané složky
- Operace nepřijímá INBOX, \All, \Sent, \Drafts, kořen mailboxu ani složku jiného uživatele.
- Před kontrolou i smazáním znovu čte IMAP LIST a porovná přesný název fyzické složky se serverem. Před potvrzením zobrazuje e-mailovou schránku, plnou serverovou cestu a přesné počty.
- Při potvrzení ověří UIDVALIDITY, počet, maximální UID a SHA256 fingerprint **celé množiny UID**. Přidání/změna zprávy mezi kontrolou a potvrzením = odmítnutí.
- Nutný CSRF, jednorázový nonce, checkbox a přesný text **SMAZAT KOŠ**. Serverová operace je jednorázová a bez automatického retry.
- **Provozně zásadní:** nezkoušet nevratný výmaz na reálném Koši s tisíci zprávami. Použít nejprve testovací mailbox a uměle vytvořený Koš.

### 3. Pořadí schránek
- Serverové \`mailbox_views.position\` podle uživatelského účtu je autoritativní. Klient ověří, že server potvrdil stejné pořadí.
- Pokud uživatel přesune více schránek rychle za sebou, požadavky se serializují a poslední pořadí se nesmí ztratit.
- Nefunkční uložení se zobrazí jako chyba – ne falešné „uloženo“.

### 4. Nastavitelná šířka
- Desktop: svislé táhlo mezi stromem schránek a seznamem e-mailů; šipky ±20 px, Home/dvojklik obnoví 255 px.
- Šířka je uložená pouze jako uživatelská předvolba na tomto zařízení (localStorage, žádná pošta/hesla). Na mobilu dál funguje výsuvné menu bez přetahování.
- Minimum 205 px, maximum 600 px a do 48 % dostupného prostoru; seznam má vždy vlastní flexibilní oblast.

### 5. Odpověď = nový text + podpis + **kompletní původní obsah**
- Při přípravě odpovědi se z IMAP načítá text původní zprávy a zobrazí se jeho náhled v odděleném panelu.
- Při samotném odeslání se citace **načte znovu na serveru**; nelze ji omylem odstranit z editoru. Do odpovědi se připojí nakonec. Původní přílohy se automaticky znovu neposílají.
- Pokud je původní MIME nedostupné či přesahuje konzervativní limit citace, Ema **neodešle** neúplnou odpověď.
- Odesílací MIME obsahuje prostý text a HTML alternativu, skutečné SMTP příjemce/hlavičky zůstávají pod stávajícími kontrolami a idempotencí.

### 6. Podpis a skutečný IMAP/SMTP stav
- Každý účet má vlastní uložený e-mailový podpis v existujícím \`mailboxes.signature_html\` (prostý text nebo bezpečně očištěné HTML). Ochrana proti skriptům a nebezpečným odkazům.
- V nastavení schránky je vizuální náhled podpisu.
- V pravém panelu **Otestovat IMAP + SMTP**: autentizace IMAP + read-only INBOX, autentizace SMTP + NOOP (bez odeslání e-mailu). Výsledky a čas jsou oddělené.
- Stav testu není trvalá garance dostupnosti: zobrazuje **poslední ověřený test**. Po změně hesla/hostitele/SMTP uživatele se starý výsledek odstraní.

## Nasazení – jeden celek, žádné míchání větví
1. **Předem** zazálohovat aplikační soubory, .env a MariaDB; identifikovat běžící git commit. Ověřit pracovní cestu a aktivní Python virtuální prostředí.
2. Nasadit nejnovější **sloučený \`main\` až po zeleném CI v PR #84**. Nepřepisovat .env, MAIL_ENCRYPTION_KEY, soukromé storage, databázi ani uživatelská data.
3. V aktivním prostředí aplikace, se stejnou DATABASE_URL jako web:
   \`\`\`bash
   python -m flask --app 'ema.web:create_app' upgrade-db
   \`\`\`
   Jde o **aditivní migraci**: přidává pouze tabulku \`mailbox_connection_checks\` pro oddělené statusy; původní zprávy a tabulky nepřestavuje. Při neúspěchu migrace **nenasazovat nový web**; zkontrolovat přístupy a práva.
4. Restartovat Passenger, otevřít \`/health\`, \`/mail\`, jednu schránku a \`/org/<org_id>/mail/<box_id>/edit\`. Prohlížeč obnovit a ověřit načtení \`mail-layout-v13.js\` a \`mail-final-v13.css\`.
5. Na desktopu přesunout dvě schránky a rychle jejich pořadí změnit; obnovit stránku. Ověřit tahání levého panelu, klávesnici a uloženou šířku. Na mobilu ověřit že zůstalo původní výsuvné menu.
6. Srovnat newsletter Vodafone/Poptávky s Roundcube – zejména rozměry tabulek, font, dělení sloupců a volitelné obrázky. Pokud se některé originální vlastnosti neshodují, zaznamenat konkrétní blok, **nepovolovat automaticky aktivní HTML**.
7. V nastavení testovací schránky uložit podpis, samostatně stisknout **Otestovat IMAP + SMTP**. Ověřit skutečný stav a čas kontroly, pak odešleme **jednu výslovně schválenou** testovací zprávu do vlastní schránky (kontrola podpisu, Odeslané a příjemce).
8. Odpovědět na testovací příchozí zprávu: odesílaný MIME musí obsahovat vlastní odpověď, podpis a na konci skutečnou původní zprávu. Přílohy se automaticky nepřipojí.
9. **Koš – bez reálného ostrého smazání:** otevřít Koš jedné testovací schránky a zkontrolovat, že potvrzovací obrazovka uvádí přesnou složku (např. \`INBOX.Trash\`), nikoliv kořen \`INBOX\`. Na testovací sadě potom lze teprve smazání výslovně schválit, zkontrolovat ostatní složky v Roundcube.
10. Při jakémkoli nesouladu nepokračovat v nevratných operacích, zaznamenat screenshot a běžící SHA, vrátit poslední nasazení.

**Rollback:** vrátit předchozí aplikaci jako celek a restartovat Passenger. Novou prázdnou tabulku výsledků spojení lze ponechat, předchozí verze ji ignoruje. Rollback kódu **nevrací** žádné už provedené IMAP přesuny, přečtení, odeslání nebo mazání.

## Další etapa
Po přejímce posledních šesti bodů uzavřít stabilizaci Mail v GitHub Issues. Dále pokračovat na **Projekty → akviziční kampaně → Fresh AI Engine**. Další nesouvisející funkce poštovního klienta nyní neotvírat.
