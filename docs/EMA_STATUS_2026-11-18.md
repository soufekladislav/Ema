> **Aktualizace vydání 18. 11. 2026:** Jediný [PR #81](https://github.com/soufekladislav/Ema/pull/81) je **sloučený do main** v jednom squash commitu `1531f7e`. Obsahuje EMA Mail V1.2, HTML/Poppins, stažení MIME příloh, IMAP synchronizované příznaky a přesuny, kontextovou nabídku, mobilní PWA a skutečné ikony Emy. **95 automatických testů úspěšných**. Uživatelské nasazení a ostrá IMAP/SMTP přejímka ještě nebyly potvrzeny. [Nasazovací kontrolní postup](EMA_MAIL_V12_DEPLOY.md). Zbývající text níže je původní revize *před* sloučením, ponechaná pro historii.

# EMA – aktuální stav realizace a přejímky
**Revize:** 18. 11. 2026 · **Základ:** skutečný obsah repozitáře `soufekladislav/Ema`, GitHub Issues/PR, Actions a uživatelské provozní testy z 17. 11.

> **Zásada:** „existuje v kódu“, „prošlo CI“ a „uživatel ověřil v provozu“ jsou tři samostatné skutečnosti. Uvádět je odděleně. Tento dokument je aktuální stavový přehled; produktové zadání zůstává v [EMA_PROJECT_MAP.md](EMA_PROJECT_MAP.md). Dřívější revize [17. 11.](EMA_DELIVERY_STATUS_2026-11-17.md) je historický snímek, nikoliv návod pro dnešní nasazení.

## 1. Fakta o vydání a GitHubu

| Položka | Zjištění |
|---|---|
| Repozitář a produkt | [soufekladislav/Ema](https://github.com/soufekladislav/Ema); cíl: chat-first obchodní a projektová asistentka s CRM a komunikátorem |
| Běžící doména | [hub.freshcrackers.cz](https://hub.freshcrackers.cz); uživatel poslal screenshoty skutečné aplikace |
| **PWA** | **Instalace potvrzena uživatelem 17. 11. ve 23:22 UTC** po opravě instalačního dialogu; přesný běžící git SHA, systémová ikona/splash a offline aktualizace nebyly nezávisle ověřeny |
| `main` | Poslední sloučený funkční mail klient: [PR #77](https://github.com/soufekladislav/Ema/pull/77); manifest v `main` se stále jmenuje **EMA HUB** |
| **Jediná aktivní release větev** | [PR #81](https://github.com/soufekladislav/Ema/pull/81), `release/ema-mail-mobile-20261117`; obsahuje nejnovější poštovní, mobilní a PWA změny; **není merged do main** |
| PR úklid | #79 a #80 byly nahrazeny #81; **#82** (duplicitní mobilní PR) uzavřen 18. 11. po porovnání stejných mobilních zdrojů |
| CI | [GitHub Actions run 44196227731](https://github.com/soufekladislav/Ema/actions/runs/44196227731): **86 passed**, Python compileall a JS syntax checks zelené na release větvi |
| Issues | **47 open / 20 closed**, z 47 otevřených **10 dlouhodobých roadmap/epiků** #1–#10. Nejde o 47 dnešních P0 prací |
| Původní backlog | **18 budoucích dílčích Issues** uzavřeno jako `not_planned` pro aktuální etapu (ne „hotovo“); #11 uzavřeno jako hotový základ hostingu, #63 jako nahrazený milestone |
| GitHub Project | [Board #10](https://github.com/users/soufekladislav/projects/10): stav jednotlivých položek boardu **z dostupných konektorových nástrojů nelze potvrdit ani přímo upravit**. Issues a tento dokument jsou aktuální zdroj statusu |

**Provozní riziko:** protože `main` a release #81 nejsou sjednocené, samotný GitHub `main` momentálně nedává pravdivou informaci o skutečné produkční verzi. V Superadminu chybí doložený release SHA a čas nasazení. Před dalším vývojem přidat evidenci verze a po přejímce sloučit PR #81.

## 2. Co skutečně máme

| Oblast | Stav | Podklad a zbývající přejímka |
|---|---|---|
| **Hosting + Flask/Passenger** | **Funkční v provozu** | `hub.freshcrackers.cz` běží a uživatel jej používá; app factory, health, MariaDB model a migrátor v repo. F0 #11 uzavřeno. Zálohy a opakovatelný restore jsou otevřený #59 |
| **Login, firmy, projekty** | **Funkční základ / další ACL QA** | Přihlášení, výběr firmy, projekty a projektové role v backendu a UI. Testy multi-tenant negativních scénářů existují. Kompletní revokace/pozvánky/ACL stále #13–#17, #21–#22, #58 |
| **Navigace desktop + mobil** | **Kód a CI; mobilní přejímka částečná** | Sidbar, chat-first, přepínač firmy, drawer se zachovaným obrázkem Emy a CSS/PWA cache fixy v PR #81. Reálné šířky 320–430 px a všechny stránky zatím nemají potvrzenou celkovou vizuální přejímku #18/#76 |
| **PWA instalace** | **Uživatelsky potvrzena** | Uživatel instalaci na mobilu výslovně potvrdil. V PR #81 název EMA, `beforeinstallprompt`, fallback Safari/Chrome, diagnostika v superadminu, lokální manifestové ikony 192/512 a vlastní obrázková úvodní obrazovka. Neověřené: native splash/ikona OS, iOS test, bezpečný logout, aktualizace po nové verzi a offline bez pošty #76 |
| **Více IMAP schránek a inbox** | **Použitelný základ, ostré nedostatky** | Zobrazuje souhrn více mailboxů, podstrom složek, hlavičky, načítání po dávkách a náhled; potvrzeno screenshoty. Na části účtů (Gmail) byla chyba IMAP. Migrace původních 6 mailboxů není doložena #32–#34/#64 |
| **SMTP/Odeslané** | **Implementováno a otestováno jen automaticky** | Sestavení zprávy, To/Cc/Bcc a idempotentní odesílací pokus; PR #81 odděluje SMTP od IMAP APPEND do Sent. Živé skutečné doručení, SMTP login a kopie v Odeslané musí projít testem #35/#78 |
| **Mazání/přesuny/Koš** | **Pořád provozní P0** | PR #81 řeší UID MOVE nebo COPY/STORE fallback a potvrzované vysypání celého Koše. Roundcube dříve zobrazoval šedé `\\Deleted` originály, počty Koše se lišily (Roundcube badge vs `SEARCH ALL`). Před nevratným výmazem či hromadnými akcemi nutný malý test na testovací schránce #78 |
| **HTML e-maily** | **Kód hotový, reálná věrnost otevřená** | MIME render v iframe, čištění CSS a blokace vzdálených trackerů; PR #81 zachovává povolené tabulkové a třídní styly. Ostrý newsletter na reálném mailboxu ještě neprošel přejímkou #34/#78 |
| **Průběžný IMAP sync** | **Částečně** | Aktualizace při otevřené stránce, agregace hlaviček, UIDVALIDITY a stránkování; **není** tím nahrazen nezávislý serverový worker/fronta a bezpečná rekonsiliace #33/#56 |
| **CRM** | **Základ v kódu** | Firma/klient a kontakt, import **CSV** s náhledem a kontrolou duplicity některých identit, negativní tenant testy. Není doložen kompletní **XLSX**, plná deduplikace/merge, historie vztahů a právní titul #28/#29 (pokročilé #30/#31 archivováno pro tuto etapu) |
| **Obchodní projekty a úkoly** | **Základ v kódu a UI** | Projekty, stavy a jednoduchý plánovač úkolů / datum. **Nejde o dokončené** milníky, obchodní závazky z komunikace, kalendář, automatické follow-upy #48/#49 |
| **Základ pipeline** | **Pilotní databázový model / CRUD** | `Opportunity` model a firemní pipeline/stage routy existují. **Plná sales pipeline a nabídky/verze/KPI nejsou hotové**; dílčí #44–#47 archivovány mimo současný release, souhrn drží epik #7 |
| **AI Ema** | **Read-only pilotní klient v kódu, nikoliv hotová asistentka** | `assistant_service.run_assistant` sestavuje omezený dostupný projektový kontext a jeden volitelný HTTPS požadavek na Fresh AI Engine. Záleží na klíči/aktivaci. Plnohodnotný chat s důkazy, CRM/e-mail kontextem, schvalováním akcí a bezpečnostním auditem stále #38–#43 |
| **Superadmin** | **Základ dostupný** | Správa účtů a firem, počty, PWA diagnostika v PR #81. Není kompletní worker health, release info, trvalý audit, metriky/kvóty ani plošná bezpečnostní přejímka #20–#23/#57–#59 |
| **Google OAuth** | **Nedokončeno / neověřeno** | #74 požaduje přihlášení ke Gmailu a správu účtů/schránek/hesel. Z aktuálního kódu není doložena hotová OAuth integrace; běžný IMAP přístup není důkazem Google OAuth |
| **Integrace Fresh ekosystému** | **Plán** | Fresh Key, Karel, Eda, Boban, Linda, Viki a Woo podle epiku #9; dílčí integrační Issues #51–#55 jsou odložené pro další fázi |
| **Provoz / security / backup** | **Nedokončené release brány** | Health a testy existují, ale není doložen restore DB, cílené provozní sledování front a rozšířený audit rolí/dat. Aktivní #23/#56–#59. Neprohlašovat za produkčně bezpečný SaaS |

## 3. Stav fází podle původního zadání

- **F0 – základ aplikace:** hlavní části implementované a viditelné, ale chybí úplné bezpečnostní a provozní release gate.
- **F1 – e-maily a CRM:** použitelný základ; **aktuální kritická práce je stabilizovat mail** a dokázat bezpečnost operací na skutečném serveru.
- **F2 – AI Ema:** jen read-only pilotní klient a chat-first UX, nikoliv plný asistent rozhodující nad komunikací a úkoly.
- **F3 – obchodní workflow:** projekty, úkoly a pipeline mají základní UI/modely; nabídky, závazky, verzování a follow-up zatím ne.
- **F4 – integrace dalších agentů:** nyní backlog; nejdřív smlouvy identity a oprávnění.
- **F5 – SaaS provoz a automatizace:** budoucí etapa; nespěchat s marketingovým slibem nehotových funkcí.

## 4. Co zůstává otevřené a na čem skutečně pracovat

### P0-A: vydání a přejímka existující Emy
1. **#81 PR**: kód ze sjednocené release větve projít, ověřit na testovacím serveru (pošta + mobil + PWA) a potom sloučit do `main`. Žádné paralelní vývojové PR stejného UI.
2. **#76**: **instalace PWA ověřena uživatelem**. Stále ověřit standalone a rebrand obrázku/ikony, všechny mobilní obrazovky, návrat z offline, přihlášení a aktualizaci cache.
3. **#78**: skutečný send → Sent, refresh/sync, HTML, single/bulk MOVE a koš na testovacích zprávách. Neprovádět nevratné masové mazání bez přejímky a zálohy.
4. **#64**: porovnat seznam původních 6 e-mailových konfigurací s nynějšími zapojenými schránkami, bez zveřejňování hesel a identit v issues.
5. **#19/#23**: zavést viditelnou verzi aplikace a nasazený Git SHA v superadminu, poslední úspěšný/nejnovější sync + důvod chyby.

### P0-B: spolehlivý provoz pošty
6. **#56/#33**: nezávislý DB worker a cron fronta, inkrementální synchronizace i bez otevřeného browseru, retry/lease, jména úloh a diagnostika.
7. **#58/#59/#57**: tenant/HTML/SMTP bezpečnostní revize, backup a **ověřený restore**.
8. **#74**: Google OAuth, bezpečné přidání a odebrání Google mailboxu, změna hesla Emy. Hesla nedešifrovat a nevykreslovat plošně.

### P1: AI a obchodní funkce až po stabilizaci
9. **#38/#39**: prokázat Fresh AI Engine kontrakt a vyřešit použitelný dialog s kontextem projektů/klientů, zdroji a historií.
10. **#40–#43**: řízené návrhy (nikoliv samovolné akce), vytěžení závazků a bezpečnostní politika.
11. **#28/#29 a #48/#49**: pošta → CRM → klient/projekt → úkol/follow-up; před tím skutečný pilot importu CRM.
12. **#7/#9** epiky obchodní pipeline a integrací ponechat pro další plánování, neotvírat 18 archivovaných subtasků v jednom sprintu.

## 5. Pravidla pro GitHub do dalšího vývoje

- **Jediný aktivní implementační PR:** nyní #81. Každá další změna má malý, samostatně testovatelný rozsah. Starší duplicitní PR #82 je zavřený jako superseded.
- **Dvě oddělené evidenční osy:** *kód/CI* (branch/PR/testy), *produkční přejímka* (konkrétní telefon/mailbox/scénář). Teprve druhá opravňuje označit feature jako „hotovo v provozu“.
- **U každé P0 Issue** uvedeme: vlastník, vazbu PR, kritéria přejímky, chybové scénáře, ověřené testy, verzi nasazení a poslední prokazatelný výsledek.
- **Epiky #1–#10** ponechat jako mapu. `not_planned` u odložených Issues znamená **nepracujeme teď**, ne „funkce je implementována“.
- **GitHub Project #10** sladit ručně nebo nástrojem, který umí Projects V2 status. Nelze považovat jeho současné hodnoty za ověřené z obsahu repozitáře.
- **Dokumentace:** `README.md` směruje sem; `EMA_PROJECT_MAP.md` drží cílový produkt; starší implementační a deploy dokumenty jsou historické verze, nikoliv aktuální provozní stav.

## 6. Rozhodnutí pro následující iteraci

**Nezačínat rozsáhlý nový modul.** Nejprve jeden sjednocený release s funkční poštou, responzivním UI a PWA; důsledná přejímka pošty a bezpečnostních operací; OAuth/worker. Jakmile je to prokazatelně provozní, navázat AI Emou s použitelným obchodním kontextem. V0.1 má význam jako funkční základ, **ne jako hotový komerční produkt**.
