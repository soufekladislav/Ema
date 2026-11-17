# EMA / Fresh HUB — UX rozhodnutí: projekt jako pracovní prostor

**Stav:** návrh a první implementace UX • 17. 11. 2026  
**Navazuje na:** [EMA Project Map](EMA_PROJECT_MAP.md) • Python EMA V0.1  
**Zdroj inspirace přihlášení:** uživatelem dodaný archiv původní PHP Emy (`public/index.php`, `public/assets/app.css`)

## 1. Zásadní rozhodnutí

**Projekt je hlavní pracovní kontext. Firma je datová, přístupová a účetní hranice.**

- Uživatel se přihlásí **jednou** a hned vidí všechny projekty, ke kterým má právo.
- Není nucen vybrat firmu, aby si mohl zobrazit projekt.
- Firma je vlastníkem dat, databáze klientů, schránek, fakturační identity a oprávnění.
- Firma může být **volitelným filtrem** projektů, nikoli první úrovní každodenní navigace.
- Host projektu nesmí automaticky vidět firemní CRM, všechny schránky ani jiné projekty.
- Superadmin není implicitní člen firmy a nesmí mít automatické oprávnění číst klientskou komunikaci.

## 2. Přihlašovací obrazovka

Přejímáme strukturu původní PHP stránky:

1. **Vlevo:** logo Fresh Crackers, původní ilustrační obrázek `fresh-hub.png`, vysvětlení programu a tři srozumitelné přínosy.
2. **Vpravo:** přihlášení e-mail/heslo, chybové hlášení, informace o správě účtů.
3. **Responzivita:** mobilní zobrazení pod sebou.
4. **Pravdivý stav:** v pilotu neuvádět AI třídění nebo autonomní odpovědi jako dostupné funkce.
5. **Bezpečnost:** formulář používá stávající CSRF, žádná veřejná registrace nebyla do Python V0.1 doplněna.

**Upřesnění z komentáře PR #66:** úvodní obrázek `https://www.freshcrackers.cz/wp-content/uploads/2026/10/fresh-hub.png`; logo a favicon `https://www.freshcrackers.cz/wp-content/uploads/2023/10/Fresh-Crackers-Logo.png`. Původní ilustrace je nyní také v hlavičce chatu, prázdném stavu chatu a levém menu. Zdroje se načítají přímo z webu Fresh Crackers (nejsou součástí Git repozitáře). Dostupnost URL se nepodařilo z tohoto prostředí nezávisle ověřit; vizuální kontrola v prohlížeči je součástí akceptace. Před produkcí lze pro spolehlivost zvážit lokální kopie v `static/`.

## 3. Výchozí pracovní obrazovka a menu

```text
EMA HUB
├── Přehled projektů                 ← výchozí obrazovka po přihlášení
├── Moje projekty                     ← dostupné projekty, nezávisle na firmě
│   ├── Projekt A
│   ├── Projekt B
│   └── Projekt C
├── Aktuální projekt                  ← po otevření vybraného projektu
│   ├── Přehled projektu
│   └── Chat projektu
├── Firemní zdroje                    ← pouze při firemním členství
│   ├── E-maily firmy
│   ├── Klienti / CRM
│   ├── Obchodní pipeline
│   ├── Úkoly firmy
│   └── Nastavení firmy
└── Správa
    ├── Firmy a pracovní účty
    └── Superadmin                    ← jen platformní oprávnění
```

**Přehled projektů:** projekty jsou primární kartou; lze filtrovat podle přidělené firmy a založit nový projekt přímo z úvodní stránky.

**Projektový detail:** ukazuje projekt, stav, úkoly a projektový chat; nezaměňuje je s firemním chatem.

**Návazné UX:** v dalších verzích v projektu zobrazovat pouze relevantní e-mailová vlákna, klientské kontakty a nabídky. Firemní sekce do té doby jednoznačně označovat **„firmy“** – nepředstírat projektový filtr, dokud jej API nevynucuje.

## 4. Datová architektura: žádné bourání izolace

```text
Uživatel (jedno přihlášení)
   ↕ členství / projektová pozvánka
Firma / Organization (tenant, účetnictví, databáze, schránky)
   ├── Klientské firmy a kontakty
   ├── Poštovní schránky
   └── Projekty (primární práce)
         ├── projektový chat
         ├── projektové úkoly
         ├── přiřazené e-mailové zprávy
         ├── nabídky a obchodní milníky (další etapa)
         └── dokumentace (další etapa)
```

V první UX změně **neměníme tabulky ani schéma DB**. Pouze měníme prezentaci, bezpečný výběr viditelných projektů a přidáváme vytvoření projektu z úvodní stránky. Nové vazby klient–projekt a projektové poštovní filtry musí dostat vlastní Issue, migraci a testy.

## 5. Akceptace první UX úpravy

- [ ] Přihlášení zobrazuje dvousloupcový layout, správný obrázek (2026/10) a logo (2023/10).
- [ ] Favicon používá dodané logo; ilustrace se zobrazuje v levém menu a v chatu.
- [ ] Po přihlášení se zobrazí seznam přístupných projektů, **ne firemní rozcestník**.
- [ ] Uživatel s více firmami může otevřít každý přístupný projekt bez předchozího výběru firmy.
- [ ] Projekt lze založit přímo z přehledu s přiřazením k firmě.
- [ ] Pozvaný uživatel uvidí pouze explicitně povolený projekt a jeho chat.
- [ ] Pozvaný uživatel **nevidí** firemní CRM a schránky.
- [ ] Firemní CRM, sdílené schránky a fakturační identita zůstávají na úrovni organizace.
- [ ] Mobilní přihlášení a menu jsou ovladatelné, bez překrývání a horizontálního přetečení.
- [ ] Úprava zachová funkční Python V0.1 a projdou dosavadní regresní testy.

## 6. Otevřené rozšíření

- **Projektový dashboard:** klienti, e-mailové konverzace, verze nabídek, termíny a dokumenty přiřazené projektu.
- **Výchozí kontext chatu:** vybraný projekt; firemní chat pouze pro oprávněné uživatele a správu mimo projekt.
- **Navigační škálování:** vyhledávání a připnutí projektů, stránkování pro stovky projektů.
- **Primární firmní filtr:** volitelný, v úvodním přehledu; v nastavení rovněž správa více firem.
- **Datové změny:** vyřešit vazbu klient–projekt, oprávnění sdílených poštovních zpráv a fakturační společnosti před přidáním AI akcí.

Tato změna je **UX základ**, nikoli hotová migrace CRM/e-mailů ani plný projektový inbox.
