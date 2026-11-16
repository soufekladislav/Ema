# EMA / Fresh HUB — realizační backlog a GitHub Issues

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

- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Potvrdit doménu, hosting Python/Passenger a provozní limity (F0, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Zabezpečit repozitář a auditovat historické balíky (F0, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Založit modulární Flask app factory, migrace a Passenger vstup (F0, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Model users/organizations a firemní členství (F0, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Model členství pouze v projektu a pozvánky (F0, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Centrální autorizační vrstva org/project/mailbox ACL (F0, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Oddělit firemní a projektové chaty a AI kontext (F0–F2, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Základní UX/UI podle Bobana — sidebar, chat, pravé karty (F0, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Testovací fixtures, verze release a základní CI pravidla (F0, P0)

### [E-09 — Superadmin, metriky a správa účtů](https://github.com/soufekladislav/Ema/issues/3) — 8 úkolů

- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Platform_superadmin: oddělená role a přístup bez obsahu (F0, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Konzole: správa firem a uživatelských účtů (F0, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Konzole: role, firemní a projektové členství (F0–F1, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Konzole: health, verze, worker a stav poštovních konektorů (F0, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Metriky velikosti MariaDB a úložiště včetně trendů (F5, P1)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Kvóty, alerty, retence a bezpečné pozastavení firmy (F5, P1)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — AI náklady a kredity po firmách z Fresh AI Engine (F5, P1)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Auditovaný a dočasný support access; export a řízená likvidace (F5, P1)

### [E-02 — CRM a import firem](https://github.com/soufekladislav/Ema/issues/4) — 4 úkolů

- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — CRM: firmy, osoby, vztahy a kontaktní historie (F1, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Import firem z CSV/XLSX s dry-run a reportem (F1, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Deduplikace firem a kontaktů se schváleným sloučením (F1, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Klientská časová osa, právní titul a blokace oslovení (F1, P0)

### [E-03 — Mail IMAP/SMTP](https://github.com/soufekladislav/Ema/issues/5) — 6 úkolů

- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Více IMAP/SMTP schránek, bezpečné přihlašování a ACL (F1, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Metadata-first IMAP sync s kurzory a UIDVALIDITY (F1, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Poštovní UI: inbox, složky, vlákna a detail on-demand (F1, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — SMTP koncepty, schválené odesílání a serverové přesuny (F1, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Přílohy on-demand a řízené projektové připnutí (F1, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Přiřazení vlákna klientovi a projektu; diagnostika konektoru (F1, P0)

### [E-04 — AI Chat / Copilot](https://github.com/soufekladislav/Ema/issues/6) — 6 úkolů

- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Integrace Fresh AI Engine: schéma, ceny, limity a chyby (F2, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Chat-first s historií a chytrými kontextovými kartami (F2, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — AI třídění e-mailů a vytěžení závazků se zdrojem (F2, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Návrhy a editace odpovědí s auditovatelným kontextem (F2, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Typované AI akce: návrh → schválení → výkon → ověření (F2, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Bezpečnost proti prompt injection a exfiltraci přes AI (F2, P0)

### [E-05 — Pipeline / Nabídky](https://github.com/soufekladislav/Ema/issues/7) — 4 úkolů

- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Obchodní pipeline a životní cyklus příležitosti (F3, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Cenové nabídky: položky, kalkulace a neměnné verze (F3, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Follow-up, připomínky a důvody prohry (F3, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Obchodní KPI: nabídky, konverze, aktivita a marže (F3–F5, P1)

### [E-06 — Obchodní projekty / Plánovač](https://github.com/soufekladislav/Ema/issues/8) — 3 úkolů

- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Obchodní projekty, milníky, dohody a změny rozsahu (F3, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Úkoly, závazky, kalendář a firemní plánovač (F3, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Projektové dokumenty pouze při vědomém připnutí (F3, P0)

### [E-07 — Integrace Fresh ekosystému](https://github.com/soufekladislav/Ema/issues/9) — 5 úkolů

- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Fresh Key: ověřit identity, vault a scopes; integrační kontrakt (F0–F4, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Karel: předání zakázky a read-only stav realizace (F4, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Eda: fakturační podklady a ověřený platební stav (F4, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Boban: příjem leadů s původem a deduplikací (F4, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Další platformy Linda, Viki a WooCommerce dle ověřených API (F5, P2)

### [E-08 — Provoz / Security / QA](https://github.com/soufekladislav/Ema/issues/10) — 6 úkolů

- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — DB job queue a krátký cron worker pro Passenger (F0–F1, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Audit událostí, korelace jobů a obnova po chybě (F0–F5, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Bezpečnostní testy tenantů, rolí, HTML/MIME a API (F0–F5, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Zálohování a test obnovy DB a připnutých dokumentů (F1–F5, P0)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Výkonový pilot a release gate pro interní provoz/SaaS (F5, P1)
- [ ] [#undefined](https://github.com/soufekladislav/Ema/issues/undefined) — Automatizační politiky a kalendářové konektory (F5, P1)

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
