# EMA Mail V1.4 → UX dopracování a přejímka

**20. 11. 2026 | PR #89 sloučený v `main`, navazující UX oprava | před produkční přejímkou**

## Co se mění
- V náhledu newsletteru se zachovají bezpečné CSS vlastnosti `padding`, `background-color`, `color`, tabulkové šířky apod., i když jsou v témže pravidle nebezpečné odkazy na `url(...)`. Tyto URL se nedostanou do `srcdoc`. E-mail zůstává v izolovaném iframe, obrázky z internetu se načítají až po kliknutí. Bez přesného HTML originální zprávy není možné prohlásit pixelovou shodu se všemi e-mailovými klienty.
- **Vytvořit složku** používá zabezpečený IMAPS `CREATE` a následné `LIST` k aktualizaci názvů složek v MariaDB. Obsah pošty ani přílohy se nesynchronizují kvůli vytváření složky.
- **Pořadí složek** je čistě prezentace: `mail_folder_views` ukládá uživatele, mailbox, ID složky a pozici. Přetažení myší nebo dlouhým dotykem a výběr přes kontextovou nabídku nemění hierarchii/složky v Roundcube ani jiném IMAP klientovi. Změnu rodiče (IMAP `RENAME`) implementace neprovádí.
- Na mobilu a v PWA je spodní navigace **Chat, E-maily, Projekty, Úkoly, Více**. Více používá stejné hlavní menu. CRM, administrace a účet zůstávají v menu Více.

## Nasazení na Exon
1. Zálohovat běžící aplikaci, MariaDB a prostředí `.env`. Nic z toho nevkládat do GitHubu nebo chatu.
2. Novou UX opravu sloučit až po zeleném CI. Nasadit **všechny soubory stejné revize**, nikoli jednotlivé soubory přes stávající produkci.
3. Před restartem v aktivním virtualenv nové aplikace a se správnou `DATABASE_URL`:
   ```bash
   python -m flask --app 'ema.web:create_app' upgrade-db
   ```
   Migrace z V1.4 přidává pouze tabulku `mail_folder_views`. Navazující UX oprava nepřidává nové tabulky ani nemění existující obsah.
4. Restartovat Passenger a otevřít `/health`, `/superadmin`, `/mail`.
5. V prohlížeči potvrdit načtení nových unikátních assetů `mail-folder-order-v1.js`, `ema-mail-folder-v1.css`, `ema-mobile-bottom-v1.js`, `ema-mobile-bottom-v1.css`. PWA se musí aktualizovat online; po nasazení případně aplikaci zavřít a znovu otevřít.
6. Na **testovací IMAP schránce**: pravým kliknutím na název složky nebo dlouhým podržením otevřít kontextovou nabídku, zvolit Nová složka, zadat jediný název, ověřit existenci v Roundcube, aktualizovat složky, seřadit sourozenecké složky tažením, obnovit stránku, znovu se přihlásit. Neměnit ani nevysypávat ostrý Koš.
7. Porovnat konkrétní newsletter v Emě a Roundcube. V Emě před povolením obrázků nesmí odejít žádný požadavek na externí obrazový tracker. Po kliknutí „Načíst obrázky“ očekávat rozložení bližší originálu a případně označit zbývající CSS odchylku.
8. Android Chrome/PWA (360–430 px), případně iPhone Safari: ověřit lištu na všech hlavních stránkách, Více → drawer, správné scrollování dlouhého e-mailu, klávesnici a odsadit chatové tlačítko od lišty.
9. Zapsat ověřenou revizi v provozní evidenci; **merge není nasazení**.

## Bezpečnostní hranice
- V MariaDB zůstávají pouze hlavičky a odkazy na reálné IMAP složky, plus preference jejich zobrazení. Žádné trvalé kopie MIME, obrázků ani příloh.
- Každé vytvoření složky vyžaduje oprávnění `mailbox manage`, firemní přístup a CSRF. Po nejasném timeoutu nepokoušet automaticky znovu o `CREATE`; nejprve ručně obnovit seznam.
- Třídění složek vyžaduje přístup k mailboxu a přesnou permutaci jeho vlastních folder ID.
- IMAP metadata zdrojem pravdy. Pokud druhý klient přejmenuje složku na serveru, aktualizovat ji přes `LIST`.
- PR záměrně **neřeší** Outlook-like offline uložení ani jakékoli automatické hromadné IMAP operace.


## Aktualizace ergonomie po uživatelské revizi 20. 11.
- Dřívější formulář **Nová složka na serveru** na konci dlouhého stromu a trvale viditelné šipky na každém řádku byly odstraněny. Nyní pouze **pravé tlačítko / dlouhý dotyk / Shift+F10 → Nová složka → jeden název**. Podřazená složka se vytvoří pod vybranou složkou; na titulku stromu na hlavní úrovni. Používá se **stejný již existující serverový endpoint**, žádný druhý systém složek.
- **Přetažení myší nebo dlouhé podržení a tažení prstem** mění pozici sourozeneckých složek pouze v uživatelském pohledu. Na mobilu lze v kontextové nabídce také zvolit Posunout výše/níže. Skutečné přemístění podsložky na serveru není implementováno a není vydáváno za hotové.
- E-mailový náhled nově **nevnucuje Poppins** obsahu cizí zprávy. Zachovává bezpečné HTML tabulky, orientaci, pozadí řádků, rozšířenou whitelist CSS a původní fonty. Obrázky i **externí CSS background-image** jsou povoleny až po kliknutí. Remote fonty/stylesheet zůstávají blokovány.
- **Důležité omezení**: zdrojový MIME obsah ukázkového newsletteru „Barvy na dřevo“ nebyl připojen. Automatické testy nyní mají podobný realistický test, ale **bez reálného srovnání dvou klientů nelze potvrdit pixelovou shodu**. Další práce na parseru se bude řídit reprodukovatelným rozdílem v konkrétním HTML, nikoli přidáváním dalších náhodných CSS výjimek.

### Testovací scénář pro přejímku
| Zařízení | Uživatelský úkon | Očekávaný výsledek |
|---|---|---|
| Desktop Chrome/Firefox | Pravé tlačítko na složku → Nová podsložka → název → Vytvořit | Vznikne skutečně na IMAP serveru a v Roundcube; žádné duplicitní UI |
| Desktop | Táhnout složku před/za jinou **na stejné úrovni**, obnovit | Pořadí zachováno v Emě pro uživatele; struktura na serveru se nemění |
| Mobil Android/PWA | Dlouhý dotyk na složku bez pohybu | Otevře se nabídka; bez náhodného otevření zpráv/složky |
| Mobil Android/PWA | Dlouhý dotyk a táhnutí mezi sourozenci; běžné tažení prstem | Reorder uložen; běžný scroll funguje a zůstává na stejné pozici |
| Tablet cca 768 px | Otevřít složky, číst mail, klávesnicí Shift+F10 | Správná hierarchie, žádné překryvy kontextové nabídky |
| Desktop, mobil | Otevřít stejný HTML newsletter v Emě a Roundcube | Shodné hlavní rozložení a čitelnost; žádné automatické externí obrázky či fonty |
| Desktop, mobil | Povolit obrázky u jedné zprávy | Externí obrázky se načtou po souhlasu; před kliknutím nesmějí být odeslány požadavky |
| Všechny | Odpovědět, přeposlat, přesunout do archivu/koše, otevřít Superadmin, chat | Funkce zůstávají bez regrese |

Nesmazávat ostré složky ani zprávy pro účely testování. Test vytváření provést na neprodukční schránce.

## Další etapa (mimo tento PR)
Po produkční přejímce V1.4 navázat projekty, úkoly, termíny, kalendář a první schvalovaný obchodní scénář Emy.