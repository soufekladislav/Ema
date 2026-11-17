# EMA Mail — pracovní klient V0.2 (17.11.2026)

## Datové rozhodnutí

**Ema není archiv celých e-mailových schránek.** Zdroj pravdy zůstává IMAP server. MariaDB ukládá pouze identitu šifrovaně připojených schránek, indexované hlavičky (předmět, od/komu, UID, UIDVALIDITY, datum, velikost, IMAP příznaky), vazby na klienty/projekty a uživatelská nastavení.

- Tělo text/HTML: FETCH z IMAP až při otevření; v jednom HTTP požadavku maximálně 192 KiB raw RFC822/MIME. Nezapisuje se do databáze ani do dočasného souboru. Přílohy se neukládají.
- CID obrázky: jen po kliknutí na „Načíst obrázky“; do dané odpovědi lze vložit nejvýše 8 inline obrázků do 64 kB každý z dostupné MIME části.
- Vzdálené obrázky: při otevření automaticky **blokované**. Až po výslovném opt-in se vykreslují v sandboxovaném iframe. Web prohlížeč může načtením obrázků informovat odesílatele o otevření zprávy; žádná server-side proxy ani datový archiv není zapnutý. Ostatní zdroje a skripty v HTML jsou blokované.
- HTML e-mail je zpracován MIME dekodérem a sanitizován knihovnou bleach; HTML/CSS e-mail nemusí být vizuálně přesně stejné jako v Gmail/Outlook. Náhled může být zkrácený, jde o pilotní čtečku.
- Hvězdička a přečtení jsou **osobní údaje uživatele Emy** v `mail_user_states`. Serverový IMAP `\\Seen` se používá jako počáteční stav; otevření detailu změní pouze osobní stav, nikoli příznak na IMAP serveru. Aktualizace IMAP příznaků již indexovaných zpráv při běhu na pozadí zatím není implementována.
- `mailbox_views`: pořadí a účast v souhrnném inboxu pro každého uživatele zvlášť. Vyloučená schránka zůstává dostupná kliknutím přímo na její název; nedochází k odpojení ani vymazání.
- `mailboxes.server_message_count`: počet zpráv v INBOX v době posledního úspěšného sync (snapshot), nikoliv online počet. Badge „nepřečtené / načtené“ zahrnuje pouze zprávy indexované Emou s platným UIDVALIDITY. Čísla nemusí odpovídat celkové nepřečtené poště na serveru.

## Reálné limity a navazující úkoly

Souhrnný inbox nyní ukazuje posledních 120 indexovaných hlaviček. Synchronizace `sync_inbox` průběžně načítá nové zprávy a v první dávce nanejvýš 10–100 nejnovějších. **Historický backfill zatím neexistuje**; položku „načíst starší“ je nutné dodat před full-history režimem. Nyní nejsou nasazeny žádné automatické mazací/retention joby.

Doporučená budoucí politika, **nikoli již zapnutá funkce**: výchozí retention metadata 12 měsíců od poslední aktualizace, strop cca 100 000 indexovaných zpráv/schránka jako výchozí rozpočtové pravidlo, výjimky pro otevřené objednávky, obchodní případy, úkoly a zákonné lhůty. Retence se nesmí nasadit bez schválení a auditovatelného pravidla, nesmí mazat zprávy na poštovním serveru.

Odesílání mailů zůstává výslovně schvalované; pro AI triáž budou nejprve oprávnění + čtení hlaviček, potom návrhy kategorizace a až potom přiřazování k projektu/objednávce.

## Nasazení na existující Exon MariaDB

1. Zálohovat aktuální Python EMA MariaDB (zachovat `.env`, Fernet `MAIL_ENCRYPTION_KEY` a stávající poštovní účty).
2. Aktualizovat z hlavní GitHub větve `main`, žádný otevřený PR neřešit.
3. V aktivním Python virtualenv dané aplikace: `pip install -r requirements.txt` — nově bleach 6.2.0.
4. Jednorázově: `python -m flask --app ema.web:create_app upgrade-db` — aditivně vytvoří `mailbox_views`, `mail_user_states` a sloupec `mailboxes.server_message_count`. Existující přihlašovací údaje, indexy ani zprávy nemaže.
5. Restart přes Exon **Setup Python App**.
6. Ověřit `/mail` (pořadí, skrytí z agregace, počty), otevření zprávy, hvězdičku, HTML a opt-in obrázků, `/account` a editaci schránky. Žádná operace nesmí automaticky odeslat e-mail.

**Pozor:** Na existující databázi nepoužívat `init-db` místo `upgrade-db` a nespouštět žádný SQL import ze staré PHP verze.
