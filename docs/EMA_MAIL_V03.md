# EMA Mail V0.3 — složky, 50 zpráv, nezávislý scroll a bezpečné přesuny

Datum: 17. listopadu 2026. Rozhodnutí vlastníka: **retenci celé historie e-mailů řídí samotný poštovní server**. Ema je pohled/triáž nad IMAP, nemá mazat serverové zprávy kvůli limitu indexace.

## Co Ema reálně dělá
- Po otevření konkrétní schránky načte přes IMAP posledních **50 hlaviček**, v databázi ukládá pouze metadata. HTML a přílohy se dále při čtení načítají na vyžádání; v DB se neukládají.
- Při dosažení dolního okraje **samostatně rolovaného seznamu** se načte dalších až 50 starších hlaviček z vybrané IMAP složky. Počty a prvky na zbytku stránky se nescrollují.
- Volitelný výběr IMAP složek: INBOX / odeslané / Archiv / Koš / další složky ze serverového LIST. Obnovení složek tlačítkem, první načtení zjišťuje složky automaticky. U názvů v IMAP modified UTF-7 se pro UI používá dekódování.
- Souhrnný inbox zobrazuje jen zahrnuté schránky a zprávy z jejich INBOX. Pro něj se z lokálně indexovaných hlaviček stránkuje po 50; další zprávy se z ostatních schránek samy netahají. To je v souladu se správcovským filtrem a nepřetěžuje síť.
- Přečtení/hvězdičky nadále patří pouze uživateli v Emě; neposílají IMAP STORE.
- Archiv a Smazat jsou dvě oddělené **potvrzované** akce. Smazat znamená výhradně přesun do složky serverem označené `\\Trash` (případně známá složka Trash), **nikdy EXPUNGE**. Archivovat používá `\\Archive`, u Gmail `\\All`; pokud chybí cílová složka nebo UID MOVE, systém bezpečně odmítne akci a nic nemaže.
- Po úspěšném přesunu zůstává původní metadatový záznam interně zachovaný (`mail_messages.moved=true`), pouze zmizí z výpisu. Při synchronizaci cílové složky se při jedinečném Message-ID pokusí propojit novou UID s existujícími vazbami na projekt/klienta.
- Všechna čtení a operace jsou chráněna přístupem ke konkrétní schránce, firmě a CSRF. Smazat / archivovat smí pouze osoba s právy spravovat schránku.

## Co není dokončené
- OAuth 2.0 „Připojit Gmail účet“ zatím chybí. Pro osobní Gmail v aktuálním IMAP klientovi použít aplikační heslo účtu se zapnutým dvoufázovým ověřením. Oficiální postup: https://support.google.com/accounts/answer/185833 .
- Aktuální JSON/HTML loader zůstává synchronní během jedné dávky IMAP. Pro desítky tisíc zpráv bude vhodné přidat frontu, timeouty a cache; zatím maximálně 50 hlaviček na HTTP požadavek.
- Archivace funguje pouze u IMAP serverů s příkazem UID MOVE a zjištěnou cílovou složkou. Kód nepoužívá COPY/STORE/EXPUNGE fallback. Neprobíhá trvalé mazání ze serveru.
- Čištění interních metadat, mazání po 12 měsících, záznamy auditů a propojení AI triáže zatím neimplementováno. Nesmí se zapnout bez dohody o GDPR, vazbách na objednávky a legislativní retenci.

## Upgrade Exon (po úspěšných CI a merge do main)
1. Zálohovat aktuální MariaDB a bezpečně zachovat `.env` se stávajícím `MAIL_ENCRYPTION_KEY`.
2. Přenést pouze kód z GitHub `main`. Nahradit `.env` ani přenášet SQLite z lokálu na Exon se nesmí.
3. V aktivním Python venv `pip install -r requirements.txt` (pokud nebylo provedeno po V0.2).
4. Jednorázově `python -m flask --app ema.web:create_app upgrade-db`. Přibudou pouze pole `mail_folders.special_use`, `mail_folders.delimiter` a `mail_messages.moved` bez smazání současných zpráv.
5. Restart Python aplikace v cPanelu.
6. V Emě vybrat IMAP schránku, ověřit načtení 50, přirozený scroll dalších 50, výběr složek, archive/delete pouze testovací zprávou s potvrzením. Gmail nejdřív spojit aplikacím heslem a vyzkoušet jednu schránku.

**Nedělat**: spouštět původní SQL import přes novou databázi; vyměňovat Fernet klíč; expunge či přímé mazání zpráv.
