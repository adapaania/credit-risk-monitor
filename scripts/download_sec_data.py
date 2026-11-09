"""Download and validate the 2023–2025 SEC Financial Statement Data Sets."""
import hashlib
import argparse
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "raw"
BASE = "https://www.sec.gov/files/dera/data/financial-statement-data-sets"
parser = argparse.ArgumentParser()
parser.add_argument('--quarters', nargs='+', default=[f'{y}q{q}' for y in range(2023,2026) for q in range(1,5)])
args = parser.parse_args()
if any(len(p)!=6 or not p[:4].isdigit() or p[4]!='q' or p[5] not in '1234' for p in args.quarters):
    parser.error('Quarters must use YYYYqN format')
manifest = ROOT / 'download_manifest.json'
records = {r['quarter']:r for r in json.loads(manifest.read_text())} if manifest.exists() else {}
for period in args.quarters:
        folder = ROOT / period
        folder.mkdir(parents=True, exist_ok=True)
        archive = folder / f"{period}.zip"
        url = f"{BASE}/{period}.zip"
        if not archive.exists():
            partial = archive.with_suffix(".zip.part")
            subprocess.run([
                "curl", "--fail", "--location", "--silent", "--show-error",
                "--retry", "3", "--max-time", "600",
                "--user-agent", "CreditRiskMonitor adapaania aaniadap@gmail.com",
                "--output", str(partial), url,
            ], check=True)
            partial.rename(archive)
        with zipfile.ZipFile(archive) as z:
            bad = z.testzip()
            if bad:
                raise RuntimeError(f"Corrupt archive member: {period}/{bad}")
            required = {"sub.txt", "num.txt", "tag.txt", "pre.txt"}
            if not required.issubset(z.namelist()):
                raise RuntimeError(f"Missing required tables in {period}")
            for member in z.infolist():
                target = (folder / member.filename).resolve()
                if not target.is_relative_to(folder.resolve()):
                    raise RuntimeError("Unsafe archive path")
            z.extractall(folder)
        digest = hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()
        records[period] = {"quarter": period, "url": url, "bytes": archive.stat().st_size, "sha256": digest}
        manifest.write_text(json.dumps([records[k] for k in sorted(records)], indent=2) + "\n")
        print(f"{period}: downloaded, CRC verified, extracted", flush=True)
print(f"All {len(args.quarters)} requested quarters ready.", flush=True)
