# AGENTS.md — závazný standard práce na aplikaci EMA

Toto je pracovní kontrakt pro AI coding agenty a vývojáře; nevytváří nová oprávnění ani nepotvrzuje provozní stav. Před každým zadáním pročti [Fresh Development Standard 1.0](docs/FRESH_DEVELOPMENT_STANDARD.md) a příslušnou relevantní část [projektové mapy](docs/EMA_PROJECT_MAP.md). Aktuální GitHub kód, Issues a PR jsou zdrojem pravdy, nikoli historické release poznámky.

## STOP: povinné 3 brány PŘED změnou kódu
1. **Existuje už řešení?** Nejprve konkrétní Issue, související repozitář, komponenty, existující endpointy/DB/migrace a testy. Uveď, co se znovupoužije a proč nová komponenta nevytváří duplicitu. Pokud už existuje řešení, uprav jej, nezakládej paralelní implementaci.
2. **Je to přirozené pro uživatele?** Definuj krátký scénář běžného člověka, standardní ovládání (klik, kontextové menu, dlouhý dotyk, přesunutí, Esc, klávesnice), minimum kroků a tlačítek. Zachovej Poppins/firemní styl rozhraní, nikoli vnucování stylu do cizích dokumentů/e-mailů. Využívej schválené vzory a komponenty.
3. **Je to stabilní a ověřitelné?** Zmapuj regresní dopady, přístupová práva, desktop/tablet/mobil/PWA, prázdné a chybové stavy, migrace a rollback; napiš testovací scénář pro člověka včetně očekávání.

Výstup tohoto předběžného auditu musí být krátký a doložený konkrétními odkazy na soubory. Pokud některá brána neprojde, nejdříve ji vyřeš, nikoli přílepkem dalšího formuláře.

## EMA specifika
- EMA je jednoduchý **e-mailový klient nad IMAP/SMTP**, nikoliv Outlook/offline úložiště. Nezrcadli MIME těla, obrázky, přílohy ani hesla do MariaDB, cache nebo browser storage. Ukládej jen malá metadata a preference, pokud mají doložený účel.
- Server IMAP je zdrojem složek, zpráv a příznaků. Složky vytvořené přes IMAP musí být vidět i v Roundcube. Změna uživatelského pořadí zobrazení **není** serverový přesun složky. IMAP RENAME, DELETE a hromadné akce nepřidávej bez samostatného schválení, bezpečnostních testů a jasného potvrzení uživatelem.
- HTML e-mail: maximální zachování jeho vlastních layoutových tabulek, barev a typografie; nikdy nespouštět skripty, formuláře, vzdálené styly, automatické externí obrázky ani trackery. E-mail vykresluj izolovaně v sandboxovaném iframe; externí obrázky teprve po výslovném kliknutí. Netvrď pixelovou shodu bez srovnání konkrétní zprávy v Roundcube.
- Dodrž oddělení firem, mailbox ACL a CSRF; mail/AI nesmějí bez schválení odesílat či mazat data.
- Na mobilu/PWA používej **existující** spodní lištu Chat / E-maily / Projekty / Úkoly / Více; nesmí překrývat čtení ani chat. Doplňky pouze tam, kde zjednodušují průchod úkolem.

## Průchod úkolem a definice hotovo
Analýza (3 brány) → malá změna existujícího řešení → unit/integration/bezpečnostní testy → CI → praktický scénář na mobilu, tabletu, desktopu → uživatelské potvrzení v nasazené verzi.

- V Issue/PR uveď: obchodní záměr, audit opakovaného použití, UX scénář, změněné soubory, automatické výsledky, rizika, migrace, rollback a konkrétní scénář pro testera.
- **Zelené CI ≠ schválený produkt; merge do main ≠ deploy; screenshot ≠ funkční důkaz.** Označ pravdivě stav kódu/CI/staging/produkční akceptace.
- Je-li výslovně schválen zápis do `main`, dokonči i sloučení po zeleném CI; nenechávej uživateli správu větví. Produkční deploy, smazání/změna existujících dat či secrets jsou samostatná autorizace.
- Chybí-li podklad nebo běh na Exonu, sděl přesnou mez ověření místo vymyšleného úspěchu. Vytvoř testovatelný výsledek, ne další sadu viditelných ovládacích formulářů.
