# EMA CRM – import osob a firem z CSV (20. 11. 2026)

## Proč tento milník vznikl
Na skutečném souboru `Fresh_Crackers_akvizice_100_firem_2026-11-16 (1).xlsx - Kandidáti.csv` (100 datových řádků, 21 sloupců) hlásila Ema na řádku 2 „nelze rozpoznat jméno, e-mail ani telefon“. Soubor ale **není seznam osob**: je to firemní akviziční rešerše s poli **Firma, Kraj, Město, Obor, Obrat, Rok obratu, Růst tržeb, Web, Hypotéza nabídky (neověřeno), Priorita, Zdroj, Stav ověření, E-commerce / online objednávky, Pozorování z webu (ověřeno vs hypotéza), Možná slabina – k prověření, Doporučená služba Fresh Crackers, Úhel prvního oslovení, Stav e-commerce ověření, Facebook profil – ověřený odkaz, LinkedIn profil – ověřený odkaz, Obchodní připravenost**.

**Diagnóza:** selhával datový typ importu, nikoli oprávnění uživatele. Nevypínat CSRF, firmovou izolaci ani zabezpečení přístupu. Změnit parser a mapování podle typu záznamu.

## 3 kontrolní brány standardu
1. **Reuse:** Původní `Company` a `Contact`, jeden `analyze_contacts` parser, `/database/import`, `/org/<org_id>/clients` a CRM ACL. Žádná druhá databáze firem. Jedna malá `company_origins` tabulka navazuje na dosavadní `contact_origins`, protože firma musí mít vlastní historii zdrojů.
2. **UX:** CSV bez kontaktní osoby vytvoří **firmu**, ne falešný kontakt. Soubor osob vytvoří kontakty, smíšený soubor oba typy. Statistiky oddělují osoby a klientské firmy. Preview uvádí oba typy a shody. Při zobrazení firem lze rozbalit zdrojová data a ručně upravit název, IČO, telefon, e-mail, poznámky; kontakty lze opravovat obdobně. Původní zdroj zůstává zachován.
3. **Stabilita:** Původní 100 firem importovat do jedné vybrané vlastní firmy Emy, další import téhož souboru beze změny počtu firem; opakovaný import z jiného zdroje propojí nový původ. Metadata zachovávají původní české názvy sloupců a doslovné hodnoty včetně `neověřeno`. Oprávnění nelze obejít; marketingový souhlas se neodvozuje. Nově po opravě z 21. 11. 2026: nejvýše 5 000 datových řádků a 5 MB na jeden CSV import; není třeba soubor s cca 2 500 kontakty dělit.

## Schéma a nasazení
Po záloze MariaDB a nasazení Emy z `main` spustit jednou ve skutečném venv a pracovním adresáři:

```bash
python -m flask --app 'ema.web:create_app' upgrade-db
```

Migrace pouze **přidá** `company_origins` s jedinečným zdrojem `(organization_id, source_site, source_kind, external_id)`. Stávající Companies, Contacts, e-maily, objednávky ani CustomerOrigins se neodstraňují. Poté restart Passenger.

## Přijímací scénář (skutečný soubor)
1. CRM → Importy a propojení → CSV; vybrat `Fresh Online s.r.o.` (nebo jinou skutečnou firmu, jejíž data to jsou), zdroj např. `Akvizice 100 firem 16.11.2026`.
2. **Zkontrolovat:** očekávat 100 firem bez kontaktní osoby, 0 neplatných e-mailů; žádný zápis. Pokud firma v Ema už existuje, preview rozliší shody.
3. **Importovat:** počet klientských firem v CRM vzroste podle nových firem, počet osobních kontaktů se nemusí změnit.
4. Otevřít **Klientské firmy** v rozbalené sekci → u některé firmy rozbalit **obchodní podklady**: původní Web, Zdroj, Priorita, Hypotéza nabídky (neověřeno) a další pole.
5. Upravit např. telefon nebo obchodní poznámku firmy; znovu importovat stejné CSV; ruční úprava nesmí zmizet a žádná firma ani zdroj nesmí vzniknout duplicitně.
6. Stejnou firmu naimportovat z druhého označeného souboru; má mít jeden Company záznam a dvě CompanyOrigin vazby.
7. Smíšené CSV `Firma,Jméno,E-mail,Telefon` → firma bez osoby se uloží do Companies, řádek s osobou do Contacts; soubor není celý odmítnut.
8. Prohlédnout rozhraní na desktopu/tabletu/mobilu, ověřit že kontakt druhé vlastní organizace nelze upravit.

## Důležité hranice
- Firemní názvy z neověřené akviziční rešerše **nejsou automaticky potvrzené** a nemusí být kontaktním oprávněním. `review_status=unverified` zůstává v provenance, včetně výslovného původního `Zdroj`.
- Data se nedoplňují domyšleným jménem, telefonem či e-mailem; zůstávají prázdná do ověření.
- Automatické vyhledávání telefonů, enrichment, čištění spamu a hromadné oslovení jsou samostatné kroky. Tato verze není nástroj na hromadnou rozesílku.
- Produkční test neprováděl GitHub CI nad skutečným zákaznickým CSV; testuje syntetické 21sloupcové ekvivalenty, reálnou přejímku je nutné doložit odděleně.


## Stabilizace 21. 11. 2026 — import cca 2 500 osob a chybějící tabulka

**Výchozí stav produkčního manifestu 20. 11. 23:09 UTC:** `migration_required=true`; chybí pouze `company_origins`, počet uložených kontaktů 292. Nasazený commit v manifestu není identifikován. GitHub main sice obsahuje aditivní migraci, ale samotné nahrání Python souborů migraci neprovede.

### Bezpečné nasazení a migrace
1. V cPanelu/Exonu zálohovat **stávající MariaDB** (před migrací), zkontrolovat adresář aplikace a aktivní virtuální prostředí.
2. Nasadit revizi až po schváleném PR a zelených CI testech. Příkaz spustit **v aktivním virtualenv aplikace ze složky s `ema/`**:
   ```bash
   python -m flask --app 'ema.web:create_app' upgrade-db
   ```
3. Příkaz je aditivní: `company_origins` je pomocná tabulka vazeb firem a zdrojů. Nikdy nespouštět `init-db` místo migrace ani nesmazat `contacts`, `companies` nebo `contact_origins`. Ověřit, že CLI vypíše `table company_origins` (pokud právě vznikla). Druhý běh nesmí vytvářet duplicity.
4. Restartovat Passenger; na nové stránce Superadmin/Ops ověřit `database.status=ok`, `migration_required=false`, `missing_tables=[]`; původní kontakty stále přítomné.
5. Ověřit nahrání 2 500 řádků v CRM přes **Zkontrolovat** (bez zápisu), potom **Importovat**. Očekávat počty nových a shodných řádků, ne přesný přírůstek +2 500 (mohou existovat duplikáty). Opakování téhož souboru se stejným názvem zdroje nesmí založit další kontakty.

### Technické hranice nové implementace
- `ema/contact_import.py`: limit 5 000 CSV řádků a 5 MiB; zachováno rozlišení firem/osob a varování pro neplatné e-maily.
- `ema/web.py`: zvýšení Flask upload stropu pro multipart; nové kontakty se v rámci jediného požadavku flushují dávkově po nejvýše 200, ale **commit nastává až po kompletním importu**. Žádná samostatná druhá databáze, žádné vypnutí ACL/CSRF.
- `ema/schema_upgrade.py`: nyní výslovně vypíše a ověří vytvořené tabulky. Na Exonu tento kód příkaz pouze **umožňuje**, sám ho nespouští.
- Pokud HTTP import na Exonu přes nový limit přesto vyprší, nelze to vyřešit jen zvyšováním timeoutu: další etapa je resumovatelný serverový job ve stávající frontě, bez částečné či duplicitní evidence.

**Stav ověření:** GitHub PR/CI a produkční příjem oddělené. Bez běhu na skutečném Exonu není nasazení ani migrace potvrzena.
