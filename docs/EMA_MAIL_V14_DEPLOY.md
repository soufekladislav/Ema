# EMA Mail V1.4 – HTML náhled, složky IMAP, mobilní navigace

**20. 11. 2026 | návrh PR #89 | před produkční přejímkou**

## Co se mění
- V náhledu newsletteru se zachovají bezpečné CSS vlastnosti \`padding\`, \`background-color\`, \`color\`, tabulkové šířky apod., i když jsou v témže pravidle nebezpečné odkazy na \`url(...)\`. Tyto URL se nedostanou do \`srcdoc\`. E-mail zůstává v izolovaném iframe, obrázky z internetu se načítají až po kliknutí. Bez přesného HTML originální zprávy není možné prohlásit pixelovou shodu se všemi e-mailovými klienty.
- **Vytvořit složku** používá zabezpečený IMAPS \`CREATE\` a následné \`LIST\` k aktualizaci názvů složek v MariaDB. Obsah pošty ani přílohy se nesynchronizují kvůli vytváření složky.
- **Pořadí složek** je čistě prezentace: \`mail_folder_views\` ukládá uživatele, mailbox, ID složky a pozici. Přetažení nebo dotykové šipky nemění hierarchii/složky v Roundcube ani jiném IMAP klientovi. Změnu rodiče (IMAP \`RENAME\`) implementace neprovádí.
- Na mobilu a v PWA je spodní navigace **Chat, E-maily, Projekty, Úkoly, Více**. Více používá stejné hlavní menu. CRM, administrace a účet zůstávají v menu Více.

## Nasazení na Exon
1. Zálohovat běžící aplikaci, MariaDB a prostředí \`.env\`. Nic z toho nevkládat do GitHubu nebo chatu.
2. Sloučit PR až po zeleném CI a lidské revizi. Nasadit **všechny soubory stejné revize**, nikoli jednotlivé soubory přes stávající produkci.
3. Před restartem v aktivním virtualenv nové aplikace a se správnou \`DATABASE_URL\`:
   \`\`\`bash
   python -m flask --app 'ema.web:create_app' upgrade-db
   \`\`\`
   Migrace pouze vytvoří tabulku \`mail_folder_views\`, staré schránky, zprávy a přístupy nemění.
4. Restartovat Passenger a otevřít \`/health\`, \`/superadmin\`, \`/mail\`.
5. V prohlížeči potvrdit načtení nových unikátních assetů \`mail-folder-order-v1.js\`, \`ema-mail-folder-v1.css\`, \`ema-mobile-bottom-v1.js\`, \`ema-mobile-bottom-v1.css\`. PWA se musí aktualizovat online; po nasazení případně aplikaci zavřít a znovu otevřít.
6. Na **testovací IMAP schránce**: založit složku, ověřit existenci v Roundcube, aktualizovat složky, seřadit sourozenecké složky, obnovit stránku, znovu se přihlásit. Neměnit ani nevysypávat ostrý Koš.
7. Porovnat konkrétní newsletter v Emě a Roundcube. V Emě před povolením obrázků nesmí odejít žádný požadavek na externí obrazový tracker. Po kliknutí „Načíst obrázky“ očekávat rozložení bližší originálu a případně označit zbývající CSS odchylku.
8. Android Chrome/PWA (360–430 px), případně iPhone Safari: ověřit lištu na všech hlavních stránkách, Více → drawer, správné scrollování dlouhého e-mailu, klávesnici a odsadit chatové tlačítko od lišty.
9. Zapsat ověřenou revizi v provozní evidenci; **merge není nasazení**.

## Bezpečnostní hranice
- V MariaDB zůstávají pouze hlavičky a odkazy na reálné IMAP složky, plus preference jejich zobrazení. Žádné trvalé kopie MIME, obrázků ani příloh.
- Každé vytvoření složky vyžaduje oprávnění \`mailbox manage\`, firemní přístup a CSRF. Po nejasném timeoutu nepokoušet automaticky znovu o \`CREATE\`; nejprve ručně obnovit seznam.
- Třídění složek vyžaduje přístup k mailboxu a přesnou permutaci jeho vlastních folder ID.
- IMAP metadata zdrojem pravdy. Pokud druhý klient přejmenuje složku na serveru, aktualizovat ji přes \`LIST\`.
- PR záměrně **neřeší** Outlook-like offline uložení ani jakékoli automatické hromadné IMAP operace.

## Další etapa (mimo tento PR)
Po produkční přejímce V1.4 navázat projekty, úkoly, termíny, kalendář a první schvalovaný obchodní scénář Emy.