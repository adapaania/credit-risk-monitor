"""Cache official SEC company facts for the 50-company shortlist locally."""
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from check_completeness import COMPANIES, ROOT

folder = ROOT / 'data/raw/companyfacts'
folder.mkdir(parents=True, exist_ok=True)
records = []
for cik, name in COMPANIES:
    url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'
    target = folder / f'CIK{cik:010d}.json'
    if not target.exists():
        partial = target.with_suffix('.json.part')
        subprocess.run(['curl','--fail','--location','--silent','--show-error',
                        '--retry','3','--max-time','180','--user-agent',
                        'CreditRiskMonitor adapaania aaniadap@gmail.com',
                        '--output',str(partial),url],check=True)
        data = json.loads(partial.read_text())
        if int(data['cik']) != cik:
            raise ValueError('Company identity mismatch')
        partial.rename(target)
        time.sleep(0.2)
    with target.open('rb') as stream:
        digest = hashlib.file_digest(stream,'sha256').hexdigest()
    records.append(dict(cik=cik,company=name,url=url,bytes=target.stat().st_size,
                        sha256=digest,cache_modified_utc=datetime.fromtimestamp(target.stat().st_mtime, timezone.utc).isoformat()))
    print(f'{name}: company facts cached',flush=True)
(folder / 'manifest.json').write_text(json.dumps(records,indent=2)+'\n')
