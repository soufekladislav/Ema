# EMA Mail V1.1 – provozní opravy a test na Exon (17. 11. 2026)

Větev navazuje na merged PR #77 a řeší P0 #78. **Oprava v repozitáři není nasazení na Exon.**

## Kritická závada z přiloženého `stderr(10).log`

- Starší `passenger_wsgi.py` načítal opakovaně sám sebe → RecursionError. Aktuální main už používá správný `from ema import create_app; application = create_app()`. Při nasazení zkontrolovat, že stejný soubor opravdu běží na serveru.
- Závěrečné trace ukazují **ModuleNotFoundError: No module named 'tinycss2'**, vyvolaný importem `bleach.css_sanitizer`. Současné `requirements.txt` tuto závislost obsahuje, ale instalace v *aktivním venv Passenger* zřejmě nebyla kompletní. V1.1 navíc umožňuje bezpečný HTML fallback bez inline CSS, kdyby `tinycss2` chybělo.
- Historické `users` table missing a `projects.kind` column missing: po záloze ověřit aktuální schéma a použít existující `init-db` / `upgrade-db`.
- `BuildError: mail_aggregate_page` zachycen před merge #77; endpoint v současném main existuje.

## Bezpečný postup po sloučení do main

1. Zálohovat databázi i aktuální aplikační soubory. Nesmazat `.env`, neotáčet `MAIL_ENCRYPTION_KEY`.
2. V cPanel **Setup Python App** aktivovat přesné Python 3.11 virtuální prostředí k aplikaci a aktualizovat soubory z main. Nepoužívat jiné `pip` než v tomtéž venv.
3. V adresáři aplikace (s aktivním venv) provést:

   ```bash
   python -m pip install -r requirements.txt
   python -m pip show tinycss2 bleach
   python -m compileall -q ema
   flask --app 'ema.web:create_app' upgrade-db
   ```

   Pokud tabulky nebyly vytvořeny při první instalaci, postup `init-db` ověřit samostatně (po záloze).
4. Restartovat Python aplikaci přes cPanel/Passenger. Ověřit `/health`, `/login`, `/mail`.
5. **Testovat na vlastní testovací schránce:** otevřít HTML zprávu, jedna testovací odpověď, potvrdit *SMTP přijato*, ověřit kopii ve skutečné IMAP složce Odeslané a doručení u příjemce. Při stavu `sent_no_copy` zprávu **neodesílat znovu**.
6. Příchozí (všechny zahrnuté schránky): při otevření souhrnu pozorovat aktualizaci každé schránky; zkontrolovat novou zprávu bez reloadu a průběžné stránkování.
7. Koš: jedním e-mailem ověřit `MOVE`, pak malou hromadnou dávku z více schránek. **Vysypat Koš** testovat jen na testovací schránce. Otevře se samostatná potvrzovací stránka se skutečným počtem položek načteným přímo z IMAP. Po zaškrtnutí nevratného souhlasu Ema znovu ověří počet, UIDVALIDITY a nejvyšší UID; až pak odstraní **celý** Koš. Podporovány jsou i servery bez UIDPLUS.
8. Ověřit strom podsložek s `/` i `.`, otevření/sbalení a stav po reloadu. Nastavení zůstává v lokální paměti konkrétního prohlížeče (neukládá e-maily).

## Technické hranice

- Jeden průchod souhrnným inboxem synchronizuje postupně maximálně 50 *hlaviček* na zapojený mailbox, nikoli celou historii ani MIME přílohy.
- Synchronizace v browseru běží pouze při otevřené stránce a každé 2 minuty. **Trvalý background worker na serveru tím není nahrazen** (#33/#56).
- Hromadný přesun seskupí výběr max. 50 zpráv podle mailboxu a zdrojové složky. Pokud má server `UID MOVE`, používá jej. Na starším IMAP použije `UID COPY` do cíle a pak `UID STORE +FLAGS.SILENT (\\Deleted)` pro vybrané původní UID. **Nespouští EXPUNGE zdrojové složky**; zdrojové zprávy mohou fyzicky zůstat označené jako `\\Deleted` do serverového úklidu. Při selhání STORE po COPY se nesmí automaticky opakovat (možná duplicitní kopie).
- Trvalý výmaz přes nové dvoufázové tlačítko `Vysypat Koš` odstraní **celý ověřený Koš bez limitu 100 zpráv**. Předem zjistí přesný počet a nejvyšší UID ze serveru (`EXAMINE` + UID SEARCH ALL). Po potvrzení (5min platnost, jednorázový token, checkbox) zkontroluje stejný stav a provede jediné `UID STORE 1:<max_UID> +FLAGS.SILENT (\\Deleted)`, pak při UIDPLUS cílené `UID EXPUNGE 1:<max_UID>`, jinak standardní `EXPUNGE` **pouze v ověřené složce Trash**. Všechny SQL indexované hlavičky Koše označí jedním UPDATE. Žádný EXPUNGE nepoužívá v INBOX ani jiné zdrojové složce. Pokud počet nebo UID neodpovídá potvrzení, nic se nemaže.
- Na produkčním serveru bez přístupu k reálným credentials a IMAP stavu nelze konec-konec potvrdit jen testy CI. Před ostrým používáním nutná přejímka.

## Reakce na ostré screenshoty 17. 11. 2026, 18:09

- Schránka bez IMAP MOVE → nově bezpečný COPY+STORE bez EXPUNGE zdroje. Testovat jednou vlastní zprávou a ověřit cíl i zdroj u skutečného poskytovatele.
- Schránka bez UIDPLUS → po 18:21 doplněna nová **dvoufázová varianta celého Koše** pro 3 301 i více zpráv; ochrana max 100 zůstává pouze ve staré interní pomocné metodě pro dávkové mazání, nikoliv v uživatelském tlačítku. Trvalý výmaz dělat na testovacích zprávách.
- SMTP formát adresy: především **preflight validace před vytvořením outbound pokusu**; odmítnutý vstup znamená neodesláno, rozepsaná zpráva zůstane v editoru, není nutné „ověřovat doručení“. Zjištěna i konkrétní chyba parseru: prázdné **nepovinné** pole CC/BCC dříve vyvolalo `Zkontrolujte formát adres příjemců`, i když samotný příjemce byl správně. V1.1 vrací pro prázdnou CC/BCC seznam `[]` a pokračuje.
- Chyba IMAP načítání: neznáme příčinu z obrázku. Nová diagnostická hláška obsahuje bezpečně jen fázi LIST/SELECT/SEARCH/FETCH/DATABASE a typ chyby bez citlivého obsahu. Podle výsledku z testu pokračovat cíleně.

## Testovací brána pro screenshot s 3 301 zprávami (18:21)

1. Na **testovací schránce** přesuň do Koše více testovacích zpráv.
2. Klikni Vysypat Koš. Musí se otevřít stránka s názvem a adresou **jediné schránky**, správným názvem Koše, aktuálním celkovým počtem a varováním o nevratnosti.
3. Změní-li se počet mezi náhledem a potvrzením, server musí odmítnout mazání **před IMAP STORE**.
4. Zkontroluj, že po potvrzení je Koš prázdný a ostatní složky zůstaly beze změn. Bez UIDPLUS musí proběhnout pouze jeden standardní `EXPUNGE` ve složce Koš.
5. V případě timeoutu nebo jiné nejistoty **neopakovat potvrzení naslepo**; nejprve znovu načíst serverový Koš. Nepředpokládat, že HTTP timeout znamená neprovedené mazání.
6. Až po úspěšném testu zvaž skutečné vyprázdnění Koše se 3 301 zprávami – je to nevratné.
