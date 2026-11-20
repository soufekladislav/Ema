# Fresh Development Standard 1.0 — tři brány každé změny

**Vlastník produktových pravidel:** Fresh Crackers. **Platnost:** pro vývoj nových funkcí, opravy a UX úpravy Emy; určen jako sdílený vzor pro Karla/Bobana a další aplikace. Tento repozitář uchovává verzi užitou v Emě.

## G0: Před implementací
| Brána | Povinná otázka | Doklad |
|---|---|---|
| 1 — Reuse | Máme to už v kódu, testech, knihovně, dokumentaci nebo jiné schválené komponentě? | Konkrétní soubor/funkce/Issue, rozhodnutí znovu použít / rozšířit / vytvořit |
| 2 — UX | Udělá to člověk bez návodu přirozeně na PC i dotykem? | Uživatelská cesta o max. pár krocích; stavy, kontextová nabídka, klávesnice a přístupnost |
| 3 — Stabilita | Co se může rozbít, jak se to otestuje a vrátí zpět? | Integrační/regresní/negativní testy, desktop/tablet/mobil/PWA, migrace a návrat |

Kontroly musí předcházet každému novému endpointu, tabulce, toolbaru či formuláři. Pokud existuje jednodušší rozšíření současné funkce, přidávání paralelní komponenty se odmítne. Nepřidávat komponenty jen proto, že jejich implementace je snadná.

## G1: Implementace
- Měň co nejméně existujících komponent. Nezasahuj do jiných funkčních modulů.
- Spoléháš-li na serverovou operaci, server je zdrojem pravdy; žádné předstírání potvrzeného výsledku.
- Přidávej automatické testy pro chování a kontraindikace, nejen přítomnost elementu na stránce.
- Bezpečnost, soukromí, ACL/CSRF, rozsah oprávnění a idempotence jsou součástí produktu.
- U AI nepřevádět uživatelovy vágní požadavky rovnou na sérii UI prvků; nejdřív vyjasni scénář z kontextu projektu.

## G2: Předání testerovi a přijetí
| Stav | Důkaz | Kdo potvrzuje |
|---|---|---|
| V kódu | commit + diff | vývoj |
| CI OK | automatické integrační + negativní testy | GitHub Actions |
| Připraveno k přejímce | konkrétní přihlášený test a popis očekávání, včetně mobilu/tabletu/desktopu | vývoj |
| Produkčně přijato | provedený reálný scénář na nasazené verzi, bez regressí | vlastník/tester |

**Nikdy nehlásit hotovo pouze na základě PR nebo zeleného CI.** V PR zaznamenat poslední doložený stav a volné body.

## Praktická testovací karta (povinně)
- Cíl: „Jako uživatel chci ... abych ...“
- Předpoklady: účty, oprávnění, prohlížeč, testovací data, anonymizace.
- Kroky: otevřít → běžná akce → potvrzení → znovu otevřít/obnovit.
- Očekáváno: viditelný výsledek, skutečná změna zdroje pravdy, funguje i na telefonu.
- Negativní scénář: bez oprávnění, duplicitní akce, chyba sítě, prázdné data, návrat.
- Stav: neověřeno / CI OK / staging OK / produkce OK; screenshot + odkazy při vizuálních úpravách.

## EMA: mailová akceptace
1. **HTML:** stejný newsletter zobrazit v Emě a v Roundcube; porovnat layout tabulek, barvy, odkazy, text, vnější obrázky pouze po kliknutí. Neprohlašovat shodu bez tohoto srovnání.
2. **Složky:** pravé tlačítko na desktopu, dlouhý dotyk na mobilu → nabídka „Nová složka“ → jediný název → ověřit vytvoření na IMAP i v Roundcube. Přesun pořadí bez nové „formulářové stěny“; musí fungovat i obnovení stránky.
3. **Mobil/PWA:** 360–430 px telefon, cca 768 px tablet, desktop > 1024 px; vizuální kontrola čtení, scrollu, kontextového menu, klávesnice a spodní lišty.
4. **Regrese:** přihlášení, všechny schránky, přesun zprávy, SMTP send, Superadmin, chat. Neprovádět destruktivní testy na ostré poště.
