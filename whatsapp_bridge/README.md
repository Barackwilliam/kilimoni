# Kilimoni AI WhatsApp Bridge

> Nakala ya bridge ya JamiiTek (Baileys 6.7.18), iliyorekebishwa kwa Kilimoni:
> njia za Django, `DOWNLOAD_AUDIO` (voice notes zimezimwa kwa sasa), na
> `DJANGO_RETRIES` (kujaribu tena Django ikishindwa).

Mchakato wa Node unaoshikilia socket za WhatsApp kwa niaba ya bot zote.

Bridge ni **injini tu**. Haina akili ya biashara, haina database ya
mazungumzo, haiamui chochote. Udhibiti wote uko Django ya Kilimoni.

```
WhatsApp  <--->  Bridge (Node)  <--->  Django (Kilimoni)
                     |
                     +--> Supabase: jedwali `baileys_auth` (sessions pekee)
```

## Kwa nini sessions ziko Supabase

Render ina filesystem ya muda. Session ikihifadhiwa kwenye folda
(`auth_info_baileys`), inafutwa kila deploy na kila mteja analazimika
kuscan QR upya. Kwenye Postgres, bridge inaweza kurestart mara ngapi —
sessions zinarudi zilipoishia.

Funguo ya jedwali ni `(session_name, key_id)`, kwa hiyo sessions za
wateja wengi zinakaa kwenye jedwali moja bila kugongana.

---

## Kusanidi

### 1. Env

```bash
cp .env.example .env
```

`BRIDGE_API_KEY` **lazima ilingane** na ile ya Django. Ni ufunguo mmoja
unaotumika pande zote mbili:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`DATABASE_URL` ni ile ile ya Django — bridge inatumia jedwali lake moja
tu (`baileys_auth`) na haigusi jedwali zingine.

### 2. Kukimbia

```bash
npm install
npm start
```

Bridge ikianza, inauliza Django: *"ni sessions zipi ninazopaswa
kuziinua?"* (`GET /webhook/bridge/sessions/`). Django ya Kilimoni inarudisha
session moja: `BAILEYS_SESSION` (chaguo-msingi `kilimoni`).

### 3. Render

Service ya pili, aina **Web Service**, root directory `bridge/`:

| | |
|---|---|
| Build command | `npm install` |
| Start command | `node server.js` |
| Health check path | `/health` |

Env: `DJANGO_URL`, `BRIDGE_API_KEY`, `DATABASE_URL`, `PG_POOL_MAX`.

Weka `BRIDGE_URL` na `BRIDGE_API_KEY` ile ile kwenye service ya Django.

---

## Njia

Zote zinahitaji header `X-Bridge-Key` isipokuwa `/health`.

| Njia | Kazi |
|---|---|
| `GET /health` | hali ya jumla (haina ulinzi — kwa Render health check) |
| `GET /sessions` | orodha ya sessions zote na hali yao |
| `GET /sessions/:name` | hali ya session moja |
| `GET /sessions/:name/qr` | QR kama data URL |
| `POST /sessions/:name/start` | anzisha |
| `POST /sessions/:name/restart` | anzisha upya (session inabaki) |
| `POST /sessions/:name/stop` | simamisha (session inabaki) |
| `POST /sessions/:name/logout` | **futa auth** — QR upya inahitajika |
| `POST /send` | `{session, to, text}` |
| `POST /read` | `{session, jid, message_id}` |
| `POST /prune` | `{days}` — futa app-state-sync-key za zamani |

---

## Mtiririko wa ujumbe

Bridge **haisubiri** jibu la Django.

```
1. WhatsApp -> bridge
2. bridge   -> POST /webhook/bridge/incoming/   {session, phone, text, ...}
3. Django   -> inahifadhi ujumbe kwenye foleni (whatsapp_incomingmessage), 200 mara moja
4. Django   -> wafanyakazi wa nyuma: injini ya Kilimoni, kwa mpangilio kwa kila mkulima
5. Django   -> POST /send  (mara ngapi inavyohitaji)
6. bridge   -> WhatsApp
```

Sababu ni ya vitendo, si ya nadharia: `_process_message` ya Django
inatuma jumbe **mbili** mteja anapoanza (salamu, kisha "niambie jina
lako"). Mkataba wa `{reply: "..."}` moja hauwezi kufanya hivyo.

---

## Yaliyorekebishwa kutoka toleo la Kilimoni

**Pool ilikuwa inavuja.** `connectToWhatsApp()` ilijiita yenyewe kila
reconnect na kila mwito uliunda `new Pool({max: 3})` mpya bila kufunga
ya zamani. Mtandao ukikatika mara 20 usiku mmoja, ulikuwa na
connections 60 zinazoelekea Supabase — na Django inashiriki database
ile ile. Sasa pool ni moja kwa mchakato mzima.

**`/qr` ilikuwa wazi.** `/logout` ilikagua `X-Bridge-Key`; `/qr`
haikukagua chochote. Mtu yeyote aliyejua URL angeweza kuiscan, na namba
yake ingekuwa ndiyo bot — akisoma mazungumzo yote ya wateja na
kuandika kwa niaba yako. Sasa kila njia ina ulinzi isipokuwa
`/health`.

**Jumbe zilishughulikiwa mmoja baada ya mwingine.** `await` ilikuwa
ndani ya `for` loop yenye timeout ya sekunde 120. Wateja watano
wakiandika pamoja, wa tano alisubiri wote wanne wamalize. Sasa kila
ujumbe una handler yake.

**Socket ya zamani haikufungwa.** Reconnect iliacha socket na listeners
zake hai. Sasa `teardown()` inaita `removeAllListeners()` na `end()`
kabla ya kuunganisha upya.

**Backoff ilikuwa sekunde 3 milele.** WhatsApp ikikataa, bot iliipiga
kila sekunde 3 bila kikomo. Sasa inapanda 3s → 6s → 12s hadi dakika 5,
na inasimama baada ya majaribio 20.

---

## Usafi

`app-state-sync-key` zinaongezeka zenyewe na hazifutwi. Django
inazisafisha kila siku 7 kupitia `DailyTasksMiddleware`:

```bash
python manage.py prune_baileys_keys --days 30
```

Creds na funguo zinazotumika hazifutwi — LIKE inachuja
`app-state-sync-key-%` pekee.

---

## Kujua tatizo liko wapi

**QR hairudi.** Angalia logs za bridge. Session ikiwa
`waiting_qr` lakini QR haionekani kwenye dashboard, bridge inaweza
kuwa haiwezi kufikia Supabase — angalia `DATABASE_URL`.

**Ujumbe unafika lakini hakuna jibu.** Angalia logs za Django, si za
bridge. Bridge inatuma na kusahau; kosa lolote la state machine au AI
liko upande wa Django.

**Bridge inaanza lakini haina session.** Django haikujibu
`/webhook/bridge/sessions/`. Angalia `DJANGO_URL` na `BRIDGE_API_KEY`
zinalingana pande zote mbili.

**Session inakatika kila mara.** WhatsApp inakataa vifaa vingi vya
namba moja. Hakikisha namba ile ile haijaunganishwa kwenye WhatsApp Web
sehemu nyingine.


---

## Kilimoni: kusanidi Render

**Service ya bridge** (root `whatsapp_bridge/`, `npm install`, `node server.js`, health `/health`):
`DJANGO_URL` (URL ya Django ya Kilimoni), `BRIDGE_API_KEY`, `DATABASE_URL` (Supabase ya Kilimoni),
`PG_POOL_MAX=5`, `BRIDGE_NAME=Kilimoni AI`.

**Service ya Django**: `BRIDGE_URL` (URL ya service ya bridge) na `BRIDGE_API_KEY` ileile.
Hiari: `BAILEYS_SESSION` (chaguo-msingi `kilimoni` — ileile ya bridge ya zamani, hivyo session
inaendelea), `BRIDGE_WORKERS` (chaguo-msingi 4 kwa kila worker wa gunicorn).

Hali ya namba, QR, kuanzisha upya na kutoa namba: **Dashboard → WhatsApp**.
