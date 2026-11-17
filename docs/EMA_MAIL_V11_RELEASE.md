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
7. Koš: jedním e-mailem ověřit `MOVE`, pak malou hromadnou dávku z více schránek. **Vysypat Koš** testovat jen na testovacích zprávách – je trvalé a vyžaduje UIDPLUS. Každé potvrzení odstraní nejvýše 100 IMAP UID.
8. Ověřit strom podsložek s `/` i `.`, otevření/sbalení a stav po reloadu. Nastavení zůstává v lokální paměti konkrétního prohlížeče (neukládá e-maily).

## Technické hranice

- Jeden průchod souhrnným inboxem synchronizuje postupně maximálně 50 *hlaviček* na zapojený mailbox, nikoli celou historii ani MIME přílohy.
- Synchronizace v browseru běží pouze při otevřené stránce a každé 2 minuty. **Trvalý background worker na serveru tím není nahrazen** (#33/#56).
- Hromadný přesun seskupí výběr max. 50 zpráv podle mailboxu a zdrojové složky, přes `UID MOVE`. Bez podpory MOVE je akce odmítnuta bez náhradního nebezpečného EXPUNGE.
- Trvalý výmaz používá pouze `UIDPLUS / UID EXPUNGE` vybrané složky Koš, explicitně požadovaný uživatelem. Nepoužívá obecné EXPUNGE celé schránky.
- Na produkčním serveru bez přístupu k reálným credentials a IMAP stavu nelze konec-konec potvrdit jen testy CI. Před ostrým používáním nutná přejímka.
