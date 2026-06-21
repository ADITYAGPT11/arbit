# Test Credentials

## ARBIT Angel One — Personal Auto-Login (DEV mode)

These credentials enable the `_system` user auto-login at backend startup.
They are stored in `/app/backend/.env` and NEVER committed to git anywhere except auto-snapshots.

```
ANGEL_API_KEY=rbFr048b
ANGEL_CLIENT_ID=A884453
ANGEL_MPIN=1110
ANGEL_TOTP_SECRET=PIRTOGAEJU6TAJT254UDQN6HTY
```

## ARBIT Angel One — Platform (Publisher-Login flow, multi-user future)

Same API key (`rbFr048b`) but used as the platform identifier in the multi-user
publisher-login redirect flow.

```
ARBIT_ANGEL_API_KEY=rbFr048b
ARBIT_ANGEL_REDIRECT_URL=https://broker-integrator.preview.emergentagent.com/api/brokers/angel_one/callback
```

> Note: The current SmartAPI app is type "Trading" (retail accounts don't get
> "Publisher" type by default). Publisher-login URL works with `redirect_url`
> query param fix, but the actual login completion still requires a working
> publisher-grade app. For personal use, the auto-login above is the active path.
