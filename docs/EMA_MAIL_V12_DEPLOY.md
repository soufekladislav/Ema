# EMA MAIL V1.2 – jeden sjednocený release
**Revize:** 18. 11. 2026 · **Zdroj:** [PR #81](https://github.com/soufekladislav/Ema/pull/81) na `release/ema-mail-mobile-20261117`.

## Rozhodnutí (výslovné zadání provozovatele)
EMA je **rozhraní skutečného poštovního serveru**, nikoliv samostatný lokální mailbox. Změny přečtení / příznaku / přesunu se zapisují na IMAP a po potvrzení z něj ověřují. **Žádný obsah e-mailů ani příloh se nepersistuje do MariaDB**, v DB zůstává jen index hlaviček, UID, odkazy na klienta/projekt, konfigurace a audit. Příloha se na požádání načte v RAM serveru a prohlížeč ji stáhne do zařízení.

## Realizace
- `ema/mail_service.py`: jeden bounded `fetch_message_mime` pro otevření HTML/textu i příloh (UIDVALIDITY + kontrola UID; 512KiB partial FETCH; limit RFC822 celkem 30 MiB). Obsah ani přílohy se neukládají do DB ani souborového systému. `download_message_attachment` vybírá konkrétní položku přílohy.
- `ema/mail_render.py`: společný MIME parser pro náhledy a stažení, bezduplikovaný seznam názvů/typů/velikostí. Bezpečné HTML sandbox iframe s CSP, izolovanými styly, základní podporou `@media` a tabulek; default **Poppins**, ale e-mailový font jej přebije. Interní CID obrázky se zobrazí bez externího requestu; obrázky z HTTPS až po schválení.
- `ema/web.py`: `GET /mail/<id>/attachment/<part_index>` se server-side mailbox ACL, přesným folder/UIDVALIDITY, `Content-Disposition: attachment` a `Cache-Control: no-store`. Není automatické zobrazení podezřelého PDF v prohlížeči; stažení je explicitní.
- `ema/mail_folders.py`: IMAP `UID STORE +FLAGS/-FLAGS` pro `\Seen` a `\Flagged` včetně kontrolního `UID FETCH FLAGS`. `MailUserState.read_override` a `starred` již nerozhodují o seznamu ani o počtech. Změna se neoznačí za úspěšnou, pokud UID/FLAGS server nepotvrdí. Hromadně maximálně 50 UID v jedné složce.
- `ema/mail_folders.py`: `MOVE` na libovolnou cílovou složku **stejné schránky**; pro starší IMAP bez MOVE konzervativní COPY+STORE/omezený EXPUNGE s varováním při `\Deleted`. Nikdy nepřesouvat zprávy mezi různými mailboxy, pokud není navržena separátní vědomá funkce COPY napříč účty.
- `static/mail-actions-v12.js/.css`, šablony: jednotná nabídka přes `⋯`, pravý klik, klávesnici a dlouhé podržení, pod ní akce přečteno/nepřečteno, hvězdička, archiv, koš, přesun do složky. Tentýž serverový API tok pro drag & drop do stromu složek (pouze stejná schránka) a hromadný výběr.
- Webový favicon: původní **Fresh Crackers**. PWA manifest / iOS apple-touch-icon: skutečné lokální `static/icons/ema-192.png` a `ema-512.png` vygenerované z obrázku Emy, bez požadavku na vzdálený server při instalaci; startovní obrázek Emy zůstává v PWA.
- Staré PR #79/#80/#82 a staré JS/CSS buildy **nenasazovat samostatně**. Použít pouze jeden kompletní release.

## Bezpečnost, limity a vědomé hranice
- Standardní příloha se stáhne do počítače či telefonu, do lokálně zvolené složky podle nastavení prohlížeče; Ema cestu k souboru neurčuje a nemá k ní přístup.
- Limit jednoho zpracovávaného MIME e-mailu **30 MiB** (přenos po 512 KiB), jednotlivé dekódované přílohy **25 MiB**, aby Passenger worker neměl neomezenou paměť. U větších zpráv se zobrazí srozumitelná chyba a klient použije původní webmail; pro větší soubory později zavést samostatný part/stream transport, ne nekontrolované navyšování limitu.
- HTML sandbox: žádné JavaScript, formuláře, aktivní obsah, remote tracker obrázky defaultně blokované. Úplná pixel-perfect shoda s Roundcube není garantovaná; je důležitější bezpečnost. CSS `background-image: url(...)` není povoleno bez zvláštní revize kvůli trackingu.
- Každý serverový IMAP zásah je trvalý a objeví se v Roundcube. U cizí pošty při oprávnění pouze číst se stav `\Seen` automaticky nemění.
- Odmítnutí `UIDVALIDITY`, změna UID, cross-tenant schránka, špatné heslo nebo nejistý STORE/MOVE nepovede ke falešné hlášce o úspěchu. **Žádné automatické opakování nejasné remote operace**.
- Po automatických testech zbývá reálná IMAP/SMTP přejímka – testy nepoužívají skutečnou produkční schránku.

## Postup nasazení na Exon (bez ztráty dat)
1. Záloha aplikace a databáze; zapsat aktuální běžící commit/zip pro rollback. **Nedělat import DB ani změnu šifrovacího klíče.**
2. Nasadit kompletní commit z jediného PR #81 / výsledný sloučený `main`; společně server `ema/`, šablony `templates/`, `static/` a manifest/ikony. Nemíchat soubory z různých větví.
3. Na serveru ověřit `pip install -r requirements.txt` ve správném Python prostředí, restartovat Passenger. Neodstraňovat existující DB tabulky ani hesla.
4. V Chrome obnovit stránku (případně ukončit a znovu spustit již instalovanou PWA). Ověřit, že se načte `mail-actions-v12.js`; neodinstalovávat PWA, pokud to není potřeba.
5. **Na jedné testovací zprávě**: otevřít HTML bez externích obrázků, povolit obrázky, zkontrolovat Poppins fallback; otevřít detail, stáhnout malý PDF a porovnat velikost/soubor s Roundcube; prohlédnout, že v DB nevznikly BLOBy.
6. **Na testovací poště**: kliknout Přečtené/Nepřečtené + hvězdička a ověřit stav v Roundcube. Potom přesunout jednu zprávu do vlastní složky, zkontrolovat zdroj a cíl. Teprve potom drag/drop a hromadný přesun nejvýše 2–3 testovacích zpráv.
7. Ověřit UI na mobilu: PWA, longpress, nabídku `⋯`, přílohu do zařízení, žádný překryv složek.
8. Až po bodech 1–7 uvažovat o ostrém hromadném Koši. **Nevysypávat produkční Koš bez explicitního potvrzení a kontroly reálného počtu**.

## Rollback
Vrátit předchozí kompletní kód/commit + restart aplikace. DB schema v této změně nepřidáváme; metadata zůstávají čitelná. **Rollback kódu nevrací IMAP změny provedené na serveru**, zejména přesuny, změny příznaků nebo mazání. Před ostrým testem proto vytvořit zprávy určené k testování a nepoužívat produkční složky.
