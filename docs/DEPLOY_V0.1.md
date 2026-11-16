# EMA HUB V0.1 — nasazení na cPanel / Passenger

> **Předpoklad:** nová izolovaná aplikace, ne přepis staré PHP Emy. Pilotní rozsah pouze s testovacími daty do ověření práv a připojení mailů. Žádná konfigurace ani heslo nepatří do Gitu.

## 1. Na hostingu

1. Ověřit a potvrdit cílovou doménu: zadání obsahuje `hub.freshrackers.cz`, starší Ema používá `hub.freshcrackers.cz`. **D-01 vyžaduje rozhodnutí, žádnou doménu automaticky nepřepínáme.**
2. V cPanel **Setup Python App** založit samostatnou Python aplikaci (doporučení Python 3.11+), doménu nastavit na potvrzenou hodnotu, entrypoint `passenger_wsgi.py` a callable `application`. Nepřepisovat původní PHP adresář ani DB.
3. Vytvořit samostatnou MariaDB s uživatelem pouze pro danou databázi, vynutit `utf8mb4`. Před importem živých dat zálohovat DB.
4. Přenést soubory repozitáře, v izolovaném virtuálním prostředí spustit `pip install -r requirements.txt`.
5. Zkopírovat `.env.example` na `.env` **mimo Git** (práva 600). Vyplnit `SECRET_KEY`, `DATABASE_URL`, `MAIL_ENCRYPTION_KEY` a `EMA_HTTPS=1`. Nesdílet hesla v chatu ani issue. Heslo v `DATABASE_URL` URL-enkódovat.
6. V env dočasně nastavit `EMA_BOOTSTRAP_EMAIL` a `EMA_BOOTSTRAP_PASSWORD` (silné, min. 12 znaků). V aplikačním adresáři a aktivním venv spustit:
   ```bash
   flask --app 'ema.web:create_app' init-db
   flask --app 'ema.web:create_app' bootstrap-admin
   ```
   Následně bootstrap heslo z env odstranit. **Nikdy nepoužívat výchozí produkční účet.**
7. Restartovat Python aplikaci přes cPanel; otevřít `https://<potvrzená-doména>/health` a pak `/login`. Přihlásit se superadminem, založit firmu, klienta, projekt a firemní poznámku.
8. Nastavit cron ve frekvenci odpovídající zátěži, např. 5–15 minut (v cPanel ověřit přesnou cestu do venv):
   ```bash
   cd /home/ACCOUNT/ema && /home/ACCOUNT/virtualenv/ema/3.11/bin/flask --app 'ema.web:create_app' sync-mailboxes --limit 20
   ```
   **Příklad cest, skutečné se liší.** Neprovádět synchronizaci neomezeně v HTTP požadavku.

## 2. Povinná kontrola před reálnými maily

- Připojit **jednu testovací schránku** přes IMAP TLS 993 / SMTP SSL 465 nebo STARTTLS 587 (ověřený certifikát a veřejná IP).
- Kliknout na ruční synchronizaci 10 hlaviček; ověřit časy, předměty, duplicity po opakování a nulové přílohy v datovém adresáři.
- Obsah zprávy se načítá až kliknutím v limitu 32 KiB, bez ukládání do DB; složité MIME/HTML zatím může být zobrazeno pouze jako částečný surový náhled.
- U SMTP provést **jediný řízený test** na vlastní adresu a ověřit výsledek na serveru. V0.1 nepodporuje BCC, přílohy ani automatické odesílání.
- Dva uživatelé ve dvou firmách: ověřit nemožnost otevřít cizí URL firmu, její poštu a chat. Projektový host nesmí získat firemní přístup.
- Zkontrolovat zálohu a návrat k poslednímu funkčnímu release.

## 3. Co V0.1 skutečně obsahuje

Funkční ukládání: více firem na účet, uživatelé a projektové role, klienti/kontakty, projekty, základní pipeline, úkoly, firemní a projektový chat, poštovní schránky, IMAP metadata, ručně vyvolaný náhled, SMTP odeslání, superadmin účtů a základní počty. Superadmin **nečte** zákaznický obsah.

**Zatím neobsahuje:** AI Engine, schvalovací Copilot, přílohy, úplný MIME/HTML klient, produkční automatické archivace, nabídky PDF/verze, automatický import, kompletní audit čtení, zrušení přístupu přes UI, skutečné DB-size per tenant ani kompletní SaaS billing. Pro reálný provoz s více zákazníky je potřeba security review a další integrační testy.

## 4. Datový model / migrace

`flask init-db` vytvoří **počáteční schéma V0.1** (`CREATE TABLE IF NOT EXISTS` podle modelů), neprovádí změny existujících tabulek. Pozdější úpravy schématu vyžadují verzované migrace (doporučeno Alembic), před nimi vždy backup. Starou PHP databázi **nepřipojovat přímo** bez mapování a migračního testu.

## 5. Bezpečnost a provozní limity

- Hesla uložit jen jako Werkzeug hash, poštovní tajemství šifrovat Fernet, klíč mimo DB a Git.
- Pokud se ztratí `MAIL_ENCRYPTION_KEY`, poštovní účty bude nutné znovu připojit.
- Povinné HTTPS, HttpOnly/SameSite cookie, CSRF všech formulářů, server-side scope firmy/projektu, TLS konektory.
- Zapnout na hraně hostingu rate limit pro `/login`, WAF, denní zálohování a průběžnou kontrolu logů bez obsahu soukromých zpráv.
- Navržený limit indexace: 20–100 hlaviček/schránka/jedna cron dávka, 50 schránek/max běh. Později doplnit robustní scheduler, kurzory a více složek.