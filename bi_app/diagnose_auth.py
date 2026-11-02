"""Check the BI -> account service route without credentials or business queries.

Run inside bi-backend: python -m bi_app.diagnose_auth
"""
import asyncio

import httpx

from .auth import auth_me_url


async def diagnose() -> int:
    try:
        endpoint = auth_me_url()
    except ValueError:
        print('FAILED: invalid AUTH_SERVICE_URL; configure http://backend:8000 for Compose')
        return 1
    print('Account validation endpoint:', endpoint, flush=True)
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get(endpoint)
        print('HTTP status:', response.status_code, flush=True)
        body = response.json()
        if response.status_code == 401 and isinstance(body, dict) and body.get('success') is False:
            print('OK: account route is reachable and rejects unauthenticated requests as expected.')
            print('No login token supplied; authenticated NG requests still require a valid session.')
            return 0
        print('FAILED: unexpected account response; check endpoint and deployed backend version.')
    except (httpx.HTTPError, ValueError) as exc:
        print('FAILED: exception_type=' + type(exc).__name__)
        print('Check AUTH_SERVICE_URL, backend health and shared Docker network.')
    return 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(diagnose()))
