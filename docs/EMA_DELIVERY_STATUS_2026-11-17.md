# EMA – aktuální stav vývoje, ověření a třídění GitHub Issues
**Datum:** 17. 11. 2026 · **Zdroj:** kód a PR na GitHubu, CI a uživatelské screenshoty z ostrého `hub.freshcrackers.cz`.

> **Neplést stav kódu se stavem produkce.** `main` obsahuje sloučené základní PR do #77. PR #79 (poštovní stabilizace) a PR #80 (mobil napříč Emou) jsou samostatně otevřené a nelze je označit za ověřené na produkčním serveru. V screenshotu může být nasazená i pracovní větev; nelze ověřit commit běžícího Passengeru bez release údaje.

## Aktuální zásada řízení Issues

- **HOTOVO:** jen splněná přejímka nebo historický issue výslovně nahrazený novou konkrétní prací. Uzavírat se zdůvodněním a odkazem na nástupce.
- **KÓD / KONTROLA:** implementováno a testováno v CI, ale čeká ostrý IMAP/SMTP/PWA nebo vizuální mobile test. **Neuzavírat.**
- **ROZPRACOVÁNO:** existuje funkční kostra, ale podstatná část akceptace chybí. **Neoznačovat za hotové jen kvůli UI.**
- **BACKLOG:** relevantní budoucí požadavek, momentálně bez realizace. Nemíchat s P0; řešit až po dokončení pošty. Historické epiky zachovat pro produktovou mapu.
- **NAHRAZENO:** archivované issue místo duplicit. Původní kontext zůstává dohledatelný.

## Právě aktivní (P0, 17. 11.)

| Oblast / issue | Co existuje | Co zbývá / rozhodnutí |
| --- | --- | --- |
| **Mobil celá aplikace** #18, #76 / **PR #80** | Sdílené mobilní vysouvací menu, Ema obrázek uvnitř, kompaktní lišta, ovládání ×/mimo/Esc; testy HTML pro /, /mail, /projects, /database, /tasks, /account, /superadmin; CI **55 passed** | **Ostrý mobil 320/375/390/430/760 + tablet**, kontrola PWA a vizuálních přetečení; PR není sloučen ani nasazen |
| **EMA Mail V1** #75 + #32–#36 | Základ více schránek, souhrn, lazy stránkování hlaviček, serverové složky, MIME náhled, compose, PWA shell z PR #77; screenshoty prokazují živý seznam a počet schránek | Funkčnost některých operací není stabilní, v reálu chyby IMAP/SMTP/Koše; přejímku neuzavírat |
| **Stabilizace pošty** #78 / **PR #79** | Fallback IMAP COPY/STORE pro servery bez MOVE, oddělení SMTP od IMAP Sent, preflight CC/BCC, souhrnný sync, bezpečné HTML, paměť stromu, dvoukrokové vysypání celého Koše; CI **66 passed** | Otestovat reálný IMAP/SMTP, zvláště Koš 3301 položek **pouze na testovacích datech** před nevratným produkčním krokem. PR není sloučen; neprovádět automatické retry SMTP |
| **Gmail/Google OAuth** #74 | Existuje issue/zadání, ale z aktuálního průchodu není prokázána funkční OAuth cesta | Rozpracovat a samostatně ověřit Google login, účty, odpojení a nastavení hesel |
| **Worker/sync a provoz** #23, #33, #56–#59 | Základ přímého načítání IMAP a GitHub CI, informace o některých konektorech v UI | Časové synchronizace mimo otevřenou stránku, fronta s názvy, diagnostika, bezpečnostní a restore testy; prodražené nebo neověřené běhy označit, neuzavírat |

## Funkční základ v `main`, ale akceptace zpravidla rozpracovaná

| Issue | Prokázané v kódu / screenshotu | Nedokončeno |
| --- | --- | --- |
| #13–#17 | Flask app factory, MariaDB model, firmy/projekty/ACL, základ chatů a uživatelů | Kompletní acceptance včetně revokací, širšího autorizačního auditu a provozních migrací |
| #18–#19 | Poppins, design systém, sidebar, chat, CI testy/fixtures | Responzivita všech obrazovek řešena PR #80; release gate, reálné zařízení |
| #20–#23 | Základ superadminu, účtů, oprávnění, health a mailbox status | Opravdová platformní izolace superadmina od obsahu, granularita práv, diagnostika workeru |
| #28–#29 | Základ CRUD firem/kontaktů v CRM; základ importu CSV v kódu | Úplná historie, deduplikace, dry-run a akceptace konkrétních reálných importů |
| #32–#37 | Více schránek a metadata-first UI, čtení/výpis/kompozice a části přenosů | Google OAuth, reálné chyby, přílohy/projektové připnutí, vlákna, automatický worker |
| #39 | Chat-first vstupní stránka a vybraný projektový kontext | Plný agentní chat s kontextovými kartami, historií a schvalováním akcí |
| #48–#49 | V UI existují projekty a úkoly, model a CRUD | Obchodní milníky, dohody, záznam závazků z komunikace, skutečný kalendář/follow-up |
| #64 | V dřívější specifikaci 6 legacy schránek; screenshot nyní ukazuje 5 | Ověřit počet a mapování všech schránek; neprohlašovat migraci za plně dokončenou |

## Odloženo do backlogu (dílčí issue archivované, epiky ponechány otevřené)

- **CRM hloubka:** #30–#31 (deduplikace a právní titul/časová osa).
- **AI Ema:** #38, #40–#43 (Engine kontrakt, analýzy, návrhy, schvalování, injection/exfiltrace).
- **Obchodní pipeline:** #44–#47 (pipeline, nabídky, follow-up, KPI).
- **Dokumenty a projektový delivery kontrakt:** #50, #52.
- **Integrace jiných agentů/platforem:** #51, #53–#55.
- **Rozšířený provoz/SaaS:** #24–#27, #60–#61 (kvóty, náklady, support access, performance).
- **Zbylé F0/F1 provozní brány:** #12, #21–#22, #57–#59 je nutné zachovat jako bezpečnostní/provozní dluh, nikoliv tvrdit že jsou hotové.

## Epiky a archiv

- #1 = dlouhodobá roadmapa; #2–#10 jsou produktové epiky/obsahové kontejnery, **ne všechno aktuální práce**. Nemají být považované za jednotlivé současné P0 úkoly.
- **#11** – uzavřeno jako splněná volba domény/hostingu (ostatní provozní podmínky mají samostatné Issues).
- **#63** – uzavřeno jako historický milestone V0.1 **nahrazený #75/#78**, nikoliv jako plně odzkoušená produkční verze.
- **#24–#27, #30–#31, #44–#47, #50–#55, #60–#61** – **18 dílčích future backlog Issues archivováno** jako `closed/not_planned` pro aktuální etapu. Rozsah a historické akceptační požadavky zůstávají v jednotlivých issue a epikách #3/#4/#7/#8/#9/#10. **Nejde o hotové funkce ani o jejich trvalé zrušení; při návratu k dané fázi issue znovu otevřít.**
- Výsledek revize: z **67 původně otevřených Issues je 20 uzavřených** (1 potvrzeně hotové, 1 nahrazený milestone, 18 odložený backlog) a **47 otevřených** (epiky + rozpracovaná/nejbližší práce). Otevřená čísla obsahují i 10 dlouhodobých epiků, takže nejde o 47 současných implementačních P0 úkolů.

## Pořadí realizace

1. **PR #79:** přijmout poštu na testovacím IMAP/SMTP a bezpečně ověřit Koš/Sent/HTML + novou zprávu.
2. **PR #80:** na reálných mobilech projít všechny hlavní stránky; zachovat ilustraci a ověřit menu, formuláře, scroll a navigaci. Merge až po testu.
3. **#74:** Google OAuth + nastavení schránek a přihlášení.
4. **#56/#23:** provozní worker/monitoring a pravidelné bezduplicitní sync všech schránek.
5. Teprve potom pokračovat v **AI Emě (#38–#43)** a obchodním workflow.

**Pozn.:** GitHub API nedává prostřednictvím aktuálního konektoru možnost přímo měnit stav položek GitHub Project #10. Stav na boardu proto musí být synchronizován zvlášť; tento dokument a komentáře v Issues rozlišují skutečné doručení od plánů.
