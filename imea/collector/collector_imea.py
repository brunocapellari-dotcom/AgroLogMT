#!/usr/bin/env python3
"""AgroLog MT - IMEA collector v1.0.

Safe primitives for IMEA collection:
- inventory/register locally downloaded official files;
- download PUBLIC direct URLs with conditional HTTP headers and immutable RAW;
- never accepts/stores username/password;
- authenticated collection is delegated to an interactive local browser session or
  to a documented API/token explicitly authorized by IMEA.

No BigQuery mutation is performed by this collector.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, pathlib, shutil, urllib.request, urllib.error, re, os, sys
from urllib.parse import urlparse

ALLOWED_EXT={'.xls','.xlsx','.pdf','.zip','.csv','.txt'}
UA='AgroLogMT-IMEA-Collector/1.2 (+private analytical use; contact owner)'
ALLOWED_HOSTS={'imea.com.br','www.imea.com.br','wap.imea.com.br','portal.imea.com.br'}

def utcnow(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def safe_name(s): return re.sub(r'[^A-Za-z0-9._-]+','_',s).strip('_.') or 'file'

def append_jsonl(path,obj):
    p=pathlib.Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a',encoding='utf-8') as f: f.write(json.dumps(obj,ensure_ascii=False)+'\n')

def immutable_raw_path(raw_root,source_id,filename,sha,when=None):
    when=when or dt.datetime.now(dt.timezone.utc)
    return pathlib.Path(raw_root)/safe_name(source_id)/f'{when:%Y}'/f'{when:%m}'/f'{when:%d}'/(sha[:12]+'__'+safe_name(filename))

def register_file(file,source_id,raw_root,manifest,source_url=None,publication_date=None):
    p=pathlib.Path(file)
    if not p.is_file(): raise FileNotFoundError(p)
    if p.suffix.lower() not in ALLOWED_EXT: raise ValueError(f'Extensão não autorizada: {p.suffix}')
    sha=sha256_file(p); dst=immutable_raw_path(raw_root,source_id,p.name,sha)
    dst.parent.mkdir(parents=True,exist_ok=True)
    status='JA_EXISTIA' if dst.exists() else 'NOVO_RAW'
    if not dst.exists(): shutil.copy2(p,dst)
    rec={'source_id':source_id,'source_url':source_url,'source_file':p.name,'raw_path':str(dst),'bytes':p.stat().st_size,
         'sha256':sha,'data_publicacao':publication_date,'data_coleta':utcnow(),'status':status}
    append_jsonl(manifest,rec); return rec

def inventory(folder):
    rows=[]
    for p in sorted(pathlib.Path(folder).rglob('*')):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXT:
            rows.append({'file':str(p),'bytes':p.stat().st_size,'sha256':sha256_file(p),'data_coleta':utcnow()})
    return rows

def download_public(url,source_id,raw_root,manifest,state_file=None,timeout=60):
    """Download a PUBLIC direct URL. No cookies, login, auth headers or credentials."""
    u=urlparse(url)
    if u.scheme!='https' or (u.hostname or '').lower() not in ALLOWED_HOSTS:
        raise ValueError(f'URL fora da allowlist oficial IMEA/HTTPS: {url}')
    state={}
    sp=pathlib.Path(state_file) if state_file else None
    if sp and sp.exists():
        try: state=json.loads(sp.read_text(encoding='utf-8'))
        except: state={}
    hdr={'User-Agent':UA}
    prev=state.get(url,{})
    if prev.get('etag'): hdr['If-None-Match']=prev['etag']
    if prev.get('last_modified'): hdr['If-Modified-Since']=prev['last_modified']
    req=urllib.request.Request(url,headers=hdr)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as resp:
            data=resp.read(); final=resp.geturl();
            fu=urlparse(final)
            if fu.scheme!='https' or (fu.hostname or '').lower() not in ALLOWED_HOSTS:
                raise ValueError(f'Redirecionamento para host não autorizado: {final}')
            cd=resp.headers.get('Content-Disposition','')
            m=re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)',cd,re.I)
            filename=(m.group(1) if m else pathlib.PurePosixPath(urlparse(final).path).name) or 'download.bin'
            tmp=pathlib.Path(raw_root)/'_incoming'/safe_name(filename); tmp.parent.mkdir(parents=True,exist_ok=True); tmp.write_bytes(data)
            rec=register_file(tmp,source_id,raw_root,manifest,source_url=url)
            tmp.unlink(missing_ok=True)
            state[url]={'etag':resp.headers.get('ETag'),'last_modified':resp.headers.get('Last-Modified'),'last_sha256':rec['sha256'],'checked_at':utcnow()}
            if sp: sp.parent.mkdir(parents=True,exist_ok=True); sp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
            return rec
    except urllib.error.HTTPError as e:
        if e.code==304:
            rec={'source_id':source_id,'source_url':url,'data_coleta':utcnow(),'status':'SEM_ALTERACAO_HTTP_304'}; append_jsonl(manifest,rec); return rec
        raise

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('inventory'); a.add_argument('--input-folder',required=True); a.add_argument('--out',default='imea_inventory.json')
    a=sub.add_parser('register'); a.add_argument('--file',required=True); a.add_argument('--source-id',required=True); a.add_argument('--raw-root',required=True); a.add_argument('--manifest',required=True); a.add_argument('--source-url'); a.add_argument('--publication-date')
    a=sub.add_parser('download-public'); a.add_argument('--url',required=True); a.add_argument('--source-id',required=True); a.add_argument('--raw-root',required=True); a.add_argument('--manifest',required=True); a.add_argument('--state-file')
    args=ap.parse_args()
    if args.cmd=='inventory':
        rows=inventory(args.input_folder); pathlib.Path(args.out).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8'); out={'status':'OK','files':len(rows),'out':args.out}
    elif args.cmd=='register': out=register_file(args.file,args.source_id,args.raw_root,args.manifest,args.source_url,args.publication_date)
    else: out=download_public(args.url,args.source_id,args.raw_root,args.manifest,args.state_file)
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
