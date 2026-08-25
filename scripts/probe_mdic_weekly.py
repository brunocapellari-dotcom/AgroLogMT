from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('--informativo', default='https://www.gov.br/mdic/pt-br/assuntos/comercio-exterior/estatisticas/informativos/informativo-2026-040')
    return p.parse_args()


def main() -> int:
    args=parse_args()
    headers={'User-Agent':'AgroLogMT/0.1'}
    r=requests.get(args.informativo,headers=headers,timeout=30)
    r.raise_for_status()
    html=r.text
    hrefs=re.findall(r'href=["\']([^"\']+)["\']',html,flags=re.I)
    candidates=[]
    for href in hrefs:
        u=urljoin(r.url,href)
        low=u.lower()
        if 'balanca.mdic.gov.br' in low or 'balanca.economia.gov.br' in low:
            candidates.append(u)
    candidates=list(dict.fromkeys(candidates))
    result={
      'informativo_url':r.url,
      'checked_at':datetime.now(timezone.utc).isoformat(),
      'informativo_sha256':hashlib.sha256(r.content).hexdigest(),
      'primary_candidates':[],
      'status':'NUMBERS_BLOCKED_SOURCE_ACCESS',
      'materialized':False,
    }
    for url in candidates:
        try:
            d=requests.get(url,headers=headers,timeout=30)
            item={'url':url,'http_status':d.status_code,'bytes':len(d.content),'content_type':d.headers.get('Content-Type')}
            result['primary_candidates'].append(item)
            if d.status_code==200 and len(d.content)>200:
                # Retrieval is evidence that the primary detail path recovered. Numeric parsing remains a separate schema gate.
                item['sha256']=hashlib.sha256(d.content).hexdigest()
                result['status']='PRIMARY_DETAIL_RETRIEVED_SCHEMA_PARSE_REQUIRED'
                result['materialized']=True
                break
        except Exception as exc:
            result['primary_candidates'].append({'url':url,'error':f'{type(exc).__name__}:{exc}'})
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0 if result['materialized'] else 2


if __name__=='__main__':
    raise SystemExit(main())
