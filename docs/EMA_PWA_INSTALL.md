# EMA – PWA instalace a startovací obrazovka
Datum: 17. listopadu 2026

Tato změna je součástí jediného vydání [PR #81](https://github.com/soufekladislav/Ema/pull/81), aby instalace nepřepsala dřívější opravy mobilu, HTML a e-mailů.

## Co uživatel uvidí
- Aplikace v instalaci se jmenuje **EMA** (`name`, `short_name`, iOS titul i výchozí titulek).
- Start je na `/` (chat/nástěnka), nikoli pouze v `/mail`; identita manifestu `id: /mail` je **záměrně zachována** kvůli kompatibilitě s už nainstalovanou PWA.
- V tmavém menu **Správa**, hned pod **Nastavení účtu**, je **Nainstalovat EMA**. Funguje napříč webem a na desktopu; v nainstalované samostatné PWA se skryje.
- Na Androidu/Chromu, pokud je `beforeinstallprompt` dostupný, kliknutí nabídne systémový instalační dialog. Pokud ne, zobrazí se přesný návod, jak instalovat z menu Chrome.
- Safari na iPhonu/iPadu neumožňuje spolehlivě spouštět nativní instalační dialog přes JS. Ovládání zobrazí instrukci **Sdílet → Přidat na plochu**; pro Chrome na iOS doporučí Safari.
- Při prvním otevření *samostatné aplikace* se ukáže krátká úvodní obrazovka **EMA** s dosavadní grafikou Emy z `fresh-hub.png`. Nepoužívá logo Fresh Crackers. Při běžném přepínání stránek neběží znovu.
- iOS `apple-touch-icon` používá obrázek Emy; PWA manifest jej upřednostňuje tam, kde je podporován, ale zachovává lokální 192/512px PNG pro instalovatelnost při chybě vzdáleného obrázku.

### Rozdíl: systémová vs. aplikační startovací obrazovka
Při spuštění instalované PWA systém nejprve může ukázat vlastní splash vytvořený **prohlížečem/OS z ikony manifestu**. Ten nelze přes HTML/JS přepsat identicky na všech modelech. **Až po načtení stránky** se ukáže naše vlastnoručně řízená obrazovka s obrázkem Emy. Na iOS může systémové splash vytvořit Safari ze snapshotu posledního spuštění nebo ikony. Proto je nutné testovat zvlášť Android a iOS a netvrdit, že HTML splash nahrazuje systémový splash na 100 % zařízení.

## PWA bezpečnost a aktualizace
- `/manifest.webmanifest` vrací `Cache-Control: no-cache, must-revalidate`, aby se po nasazení rychle aktualizoval název a instalované ikony, pokud prohlížeč aktualizaci podporuje.
- Service Worker cache `ema-shell-20261117-3` uchovává **jen offline stránku a lokální grafické ikony**, nikoli session, osobní údaje, e-maily, přílohy nebo HTML obsahy.
- Staré cache-first kopie JS/CSS byly odstraněny v PR #81. Nová install logika je z `pwa-install-v1.js`, nezávislá na staré cache.
- SessionStorage uchovává pouze bezcitlivý příznak `ema.pwa.launch.v1=shown` pro jednorázové zobrazení splash. Žádný obsah zpráv nebo přihlášení.
- Samotné e-maily a firemní data fungují **online**; při ztrátě internetu PWA nabídne jen bezpečnou offline stránku.

## Provozní přejímka po nasazení
1. Na desktopu po přihlášení ověřit menu **Nastavení účtu → Nainstalovat EMA** (správa firem zůstává přístupná) a kliknout.
2. Na Android Chrome otevřít `https://hub.freshcrackers.cz`, kliknout Nainstalovat EMA, potvrdit systémový dialog nebo projít návod `⋮ → Nainstalovat aplikaci`. Zkontrolovat ikonu na ploše, název **EMA**, spuštění bez adresního řádku, krátkou obrazovku s obrázkem Emy a otevření nástěnky.
3. Na iPhone Safari kliknout Nainstalovat EMA, zobrazení instrukce `Sdílet → Přidat na plochu`, instalovat, spustit z plochy, zkontrolovat název, obrázek Emy a navigaci.
4. Opakovat po obnovení stránky, přepínání mezi projekty/poštou/CRM a restartu PWA. Splash nesmí vyskakovat při každém kliknutí.
5. Na již instalované starší aplikaci ověřit aktualizaci manifestu bez vzniku duplicity. Změna systémové ikony může vyžadovat odinstalování/přidání znovu kvůli cache OS.
6. Otestovat aktualizaci CSS/JS (žádný starý sidebar), offline stránku a přihlášení po expiraci session.
7. Nezaměňovat úspěšné pytest/JS syntax checks s ověřenou instalací v konkrétních prohlížečích.

**Nasazení ani fyzická instalace na zařízení nebyly provedeny přes GitHub.** PR #81 vyžaduje běžný release a kontrolu na skutečném Android/iOS zařízení.

## Diagnostika instalačního tlačítka (18. 11. 2026)

Uživatelský test odhalil, že v Chrome při kliknutí na `Nainstalovat EMA` místo systémového dialogu vyskočilo `Otevři EMU v Chrome`, následně `Rozumím` jen zavřelo okno. **Tlačítko nebylo rozbité v části kliknutí; prohlížeč dosud nevydal `beforeinstallprompt`.** To může znamenat různé důvody: neschválená instalovatelnost, manifest/ikony chybně publikované na serveru, PWA již nainstalovaná, potlačená nabídka, nebo prohlížeč který tuto událost nevydává. Ze samotné hlášky nelze určit skutečnou příčinu.

- `static/pwa-install-v2.js` nahradil slepé `Rozumím` diagnostickým oknem: ukáže bezpečný kontext, platformu, standalone, obdržení instalační události, načtení manifestu, nalezení lokálních ikon 192/512px a stav Service Workeru; lze **Zkopírovat diagnostiku** (bez poštovního obsahu/tokenu/user-agent stringu). Když Chrome později vydá `beforeinstallprompt`, objeví se `Spustit instalaci`.
- Manifest nyní používá **jen stejnodoménové PNG ikony**. Vzdálený obrázek Emy zůstává na ilustrativní úvodní obrazovce, ne jako instalačně kritická ikona. Tím je odstraněna jedna z možných příčin nekompatibility Chrome.
- **Superadmin → EMA PWA – instalace a manifest**: tlačítko Otestovat PWA, Zobrazit manifest a Service Worker. Samotný manifest je veřejný: `https://hub.freshcrackers.cz/manifest.webmanifest` a není exportním souborem Superadminu.
- Na Androidu se vždy nejprve doporučuje vyzkoušet menu skutečného Chrome **⋮ → Přidat na plochu / Nainstalovat aplikaci**. Chrome není možné přímo přinutit k instalačnímu dialogu, pokud neposkytne `beforeinstallprompt`. Pokud se nabídne pouze zástupce, nepovažovat to za ověřenou instalaci PWA.
- Po úspěšném CI nasadit **pouze sjednocenou PR #81 větev**, obnovit stránku a v Superadminu zkopírovat diagnostiku přímo z problémového telefonu. Při `Manifest: CHYBA` nebo `SW registrace: NENÍ` opravit hosting; při zelených kontrolách a bez události ověřit Chrome verzi/již instalovanou aplikaci/manuální instalaci.

Pozor: Nelze zaručit, že samotná diagnostická změna vyvolá nativní instalační nabídku na konkrétním zařízení. Rozhodnutí je na Chrome.
