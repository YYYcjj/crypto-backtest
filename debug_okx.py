#!/usr/bin/env python3
import json, requests, os, hmac, hashlib, base64, datetime as dt

k=os.environ['OKX_API_KEY']; s=os.environ['OKX_API_SECRET']; p=os.environ['OKX_API_PASSPHRASE']
now=dt.datetime.now(dt.timezone.utc)
ts=now.strftime('%Y-%m-%dT%H:%M:%S.')+f'{now.microsecond//1000:03d}Z'
print(f"Using key: {k[:10]}...")

for m in range(1,8):
    start = int(dt.datetime(2026,m,1,tzinfo=dt.timezone.utc).timestamp()*1000)
    if m==12: end = int(dt.datetime(2027,1,1,tzinfo=dt.timezone.utc).timestamp()*1000)-1
    else: end = int(dt.datetime(2026,m+1,1,tzinfo=dt.timezone.utc).timestamp()*1000)-1
    path=f'/api/v5/trade/orders-history?instType=SWAP&state=filled&begin={start}&end={end}&limit=100'
    sig=hmac.new(s.encode(),(ts+'GET'+path).encode(),hashlib.sha256).digest()
    r=requests.get('https://www.okx.com'+path,
        headers={'OK-ACCESS-KEY':k,'OK-ACCESS-SIGN':base64.b64encode(sig).decode(),
                 'OK-ACCESS-TIMESTAMP':ts,'OK-ACCESS-PASSPHRASE':p},timeout=30)
    d=r.json()
    print(f'{m}月: {len(d.get("data",[]))}条, code={d.get("code")}, msg={d.get("msg","")[:50]}')
