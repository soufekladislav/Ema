# EMA / Fresh HUB — realizační backlog a GitHub Issues

> **Historické zadání / stav k původnímu datu.** Tento soubor není aktuální seznam hotových funkcí ani nasazovací instrukce. Aktuální revize: [EMA_STATUS_2026-11-18.md](EMA_STATUS_2026-11-18.md).


> Datum: 16. 11. 2026. Stav: zadání a Issues založené, vývoj neověřen.

**Master specifikace:** [Projektová mapa v1.1](EMA_PROJECT_MAP.md) · **Řídicí Issue:** [#1](https://github.com/soufekladislav/Ema/issues/1) · **GitHub Project:** [#10](https://github.com/users/soufekladislav/projects/10)

## Fáze a akceptační brány

| Fáze | Obsah | Gate |
|---|---|---|
| F0 | Python/Passenger, MariaDB, účty, tenant/project ACL, superadmin minimum, UX | Test izolace firem a hosta, healthcheck a opakovatelné migrace |
| F1 | CRM, import, více IMAP/SMTP a metadata-first index | Dvě schránky, žádné duplicity, přílohy se automaticky neukládají |
| F2 | AI Engine, firma/projekt chat, návrhy a schvalování | AI najde zdroj, odpověď připraví, bez schválení nic neodešle |
| F3 | Pipeline, nabídky a verze, projekty a úkoly | Nabídka V2 přijata a neměnná, založená obchodní zakázka |
| F4 | Karel, Eda, Boban a konektory | Bezduplicitní předání, řízené retry, vlastnictví polí |
| F5 | Automatizace, kalendář, metriky, kvóty, SaaS pilot | Bezpečnost, restore, výkon a ekonomika ověřeny |

Priority: **P0** = funkční bezpečné jádro, **P1** = důležité rozšíření, **P2** = volitelná další integrace. Průřezové epiky se týkají více fází.

## Epiky a navázané Issues

### [E-01 — Foundation, role, tenant ACL a Boban UX](https://github.com/soufekladislav/Ema/issues/2) — 9 úkolů

- [ ] [#11](https://github.com/soufekladislav/Ema/issues/11) — Potvrdit doménu, hosting Python/Passenger a provozní limity (F0, P0)
- [ ] [#12](https://github.com/soufekladislav/Ema/issues/12) — Zabezpečit repozitář a auditovat historické balíky (F0, P0)
- [ ] [#13](https://github.com/soufekladislav/Ema/issues/13) — Založit modulární Flask app factory, migrace a Passenger vstup (F0, P0)
- [ ] [#14](https://github.com/soufekladislav/Ema/issues/14) — Model users/organizations a firemní členství (F0, P0)
- [ ] [#15](https://github.com/soufekladislav/Ema/issues/15) — Model členství pouze v projektu a pozvánky (F0, P0)
- [ ] [#16](https://github.com/soufekladislav/Ema/issues/16) — Centrální autorizační vrstva org/project/mailbox ACL (F0, P0)
- [ ] [#17](https://github.com/soufekladislav/Ema/issues/17) — Oddělit firemní a projektové chaty a AI kontext (F0–F2, P0)
- [ ] [#18](https://github.com/soufekladislav/Ema/issues/18) — Základní UX/UI podle Bobana — sidebar, chat, pravé karty (F0, P0)
- [ ] [#19](https://github.com/soufekladislav/Ema/issues/19) — Testovací fixtures, verze release a základní CI pravidla (F0, P0)

### [E-09 — Superadmin, metriky a správa účtů](https://github.com/soufekladislav/Ema/issues/3) — 8 úkolů

- [ ] [#20](https://github.com/soufekladislav/Ema/issues/20) — Platform_superadmin: oddělená role a přístup bez obsahu (F0, P0)
- [ ] [#21](https://github.com/soufekladislav/Ema/issues/21) — Konzole: správa firem a uživatelských účtů (F0, P0)
- [ ] [#22](https://github.com/soufekladislav/Ema/issues/22) — Konzole: role, firemní a projektové členství (F0–F1, P0)
- [ ] [#23](https://github.com/soufekladislav/Ema/issues/23) — Konzole: health, verze, worker a stav poštovních konektorů (F0, P0)
- [ ] [#24](https://github.com/soufekladislav/Ema/issues/24) — Metriky velikosti MariaDB a úložiště včetně trendů (F5, P1)
- [ ] [#25](https://github.com/soufekladislav/Ema/issues/25) — Kvóty, alerty, retence a bezpečné pozastavení firmy (F5, P1)
- [ ] [#26](https://github.com/soufekladislav/Ema/issues/26) — AI náklady a kredity po firmách z Fresh AI Engine (F5, P1)
- [ ] [#27](https://github.com/soufekladislav/Ema/issues/27) — Auditovaný a dočasný support access; export a řízená likvidace (F5, P1)

### [E-02 — CRM a import firem](https://github.com/soufekladislav/Ema/issues/4) — 4 úkolů

- [ ] [#28](https://github.com/soufekladislav/Ema/issues/28) — CRM: firmy, osoby, vztahy a kontaktní historie (F1, P0)
- [ ] [#29](https://github.com/soufekladislav/Ema/issues/29) — Import firem z CSV/XLSX s dry-run a reportem (F1, P0)
- [ ] [#30](https://github.com/soufekladislav/Ema/issues/30) — Deduplikace firem a kontaktů se schváleným sloučením (F1, P0)
- [ ] [#31](https://github.com/soufekladislav/Ema/issues/31) — Klientská časová osa, právní titul a blokace oslovení (F1, P0)

### [E-03 — Mail IMAP/SMTP](https://github.com/soufekladislav/Ema/issues/5) — 6 úkolů

- [ ] [#32](https://github.com/soufekladislav/Ema/issues/32) — Více IMAP/SMTP schránek, bezpečné přihlašování a ACL (F1, P0)
- [ ] [#33](https://github.com/soufekladislav/Ema/issues/33) — Metadata-first IMAP sync s kurzory a UIDVALIDITY (F1, P0)
- [ ] [#34](https://github.com/soufekladislav/Ema/issues/34) — Poštovní UI: inbox, složky, vlákna a detail on-demand (F1, P0)
- [ ] [#35](https://github.com/soufekladislav/Ema/issues/35) — SMTP koncepty, schválené odesílání a serverové přesuny (F1, P0)
- [ ] [#36](https://github.com/soufekladislav/Ema/issues/36) — Přílohy on-demand a řízené projektové připnutí (F1, P0)
- [ ] [#37](https://github.com/soufekladislav/Ema/issues/37) — Přiřazení vlákna klientovi a projektu; diagnostika konektoru (F1, P0)

### [E-04 — AI Chat / Copilot](https://github.com/soufekladislav/Ema/issues/6) — 6 úkolů

- [ ] [#38](https://github.com/soufekladislav/Ema/issues/38) — Integrace Fresh AI Engine: schéma, ceny, limity a chyby (F2, P0)
- [ ] [#39](https://github.com/soufekladislav/Ema/issues/39) — Chat-first s historií a chytrými kontextovými kartami (F2, P0)
- [ ] [#40](https://github.com/soufekladislav/Ema/issues/40) — AI třídění e-mailů a vytěžení závazků se zdrojem (F2, P0)
- [ ] [#41](https://github.com/soufekladislav/Ema/issues/41) — Návrhy a editace odpovědí s auditovatelným kontextem (F2, P0)
- [ ] [#42](https://github.com/soufekladislav/Ema/issues/42) — Typované AI akce: návrh → schválení → výkon → ověření (F2, P0)
- [ ] [#43](https://github.com/soufekladislav/Ema/issues/43) — Bezpečnost proti prompt injection a exfiltraci přes AI (F2, P0)

### [E-05 — Pipeline / Nabídky](https://github.com/soufekladislav/Ema/issues/7) — 4 úkolů

- [ ] [#44](https://github.com/soufekladislav/Ema/issues/44) — Obchodní pipeline a životní cyklus příležitosti (F3, P0)
- [ ] [#45](https://github.com/soufekladislav/Ema/issues/45) — Cenové nabídky: položky, kalkulace a neměnné verze (F3, P0)
- [ ] [#46](https://github.com/soufekladislav/Ema/issues/46) — Follow-up, připomínky a důvody prohry (F3, P0)
- [ ] [#47](https://github.com/soufekladislav/Ema/issues/47) — Obchodní KPI: nabídky, konverze, aktivita a marže (F3–F5, P1)

### [E-06 — Obchodní projekty / Plánovač](https://github.com/soufekladislav/Ema/issues/8) — 3 úkolů

- [ ] [#48](https://github.com/soufekladislav/Ema/issues/48) — Obchodní projekty, milníky, dohody a změny rozsahu (F3, P0)
- [ ] [#49](https://github.com/soufekladislav/Ema/issues/49) — Úkoly, závazky, kalendář a firemní plánovač (F3, P0)
- [ ] [#50](https://github.com/soufekladislav/Ema/issues/50) — Projektové dokumenty pouze při vědomém připnutí (F3, P0)

### [E-07 — Integrace Fresh ekosystému](https://github.com/soufekladislav/Ema/issues/9) — 5 úkolů

- [ ] [#51](https://github.com/soufekladislav/Ema/issues/51) — Fresh Key: ověřit identity, vault a scopes; integrační kontrakt (F0–F4, P0)
- [ ] [#52](https://github.com/soufekladislav/Ema/issues/52) — Karel: předání zakázky a read-only stav realizace (F4, P0)
- [ ] [#53](https://github.com/soufekladislav/Ema/issues/53) — Eda: fakturační podklady a ověřený platební stav (F4, P0)
- [ ] [#54](https://github.com/soufekladislav/Ema/issues/54) — Boban: příjem leadů s původem a deduplikací (F4, P0)
- [ ] [#55](https://github.com/soufekladislav/Ema/issues/55) — Další platformy Linda, Viki a WooCommerce dle ověřených API (F5, P2)

### [E-08 — Provoz / Security / QA](https://github.com/soufekladislav/Ema/issues/10) — 6 úkolů

- [ ] [#56](https://github.com/soufekladislav/Ema/issues/56) — DB job queue a krátký cron worker pro Passenger (F0–F1, P0)
- [ ] [#57](https://github.com/soufekladislav/Ema/issues/57) — Audit událostí, korelace jobů a obnova po chybě (F0–F5, P0)
- [ ] [#58](https://github.com/soufekladislav/Ema/issues/58) — Bezpečnostní testy tenantů, rolí, HTML/MIME a API (F0–F5, P0)
- [ ] [#59](https://github.com/soufekladislav/Ema/issues/59) — Zálohování a test obnovy DB a připnutých dokumentů (F1–F5, P0)
- [ ] [#60](https://github.com/soufekladislav/Ema/issues/60) — Výkonový pilot a release gate pro interní provoz/SaaS (F5, P1)
- [ ] [#61](https://github.com/soufekladislav/Ema/issues/61) — Automatizační politiky a kalendářové konektory (F5, P1)

## Pravidla dokončování

- Dílčí Issue obsahuje zadání, akceptační kritéria, závislosti, odkaz na epik a master dokument.
- Ověřit funkci v reálném UI, backendu a negativních scénářích; dokumentovat release a chybové stavy.
- Ema vlastní obchodní projekt, Karel řídí technickou/development realizaci.
- E-mail je primárně na serveru poskytovatele; přílohy nezrcadlíme.
- Nepotvrzovat neprovedené nasazení, test ani integraci.

## Propojení s GitHub Projects #10

GitHub Issues vznikly v repozitáři; jejich vložení jako položek Project #10 je **samostatná operace** a nebylo touto změnou provedeno.

V Project #10 na spodním řádku kliknout na **+** → **Add item from repository** → vybrat **soufekladislav/Ema** → hromadně označit všech **61 Issues** → **Add selected items**. Nastavit pohled podle Status (Todo/In progress/Review/Done), případně pole Phase/Priority.

Pro budoucí Issues zapnout **Workflows → Auto-add to project** s vybraným repozitářem a filtrem **is:issue is:open**. Auto-add nepřidává existující Issues zpětně.
