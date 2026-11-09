"""Download and validate the 2023–2025 SEC Financial Statement Data Sets."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "raw"
BASE = "https://www.sec.gov/files/dera/data/financial-statement-data-sets"
records = []
for year in range(2023, 2026):
    for quarter in range(1, 5):
        period = f"{year}q{quarter}"
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
        records.append({"quarter": period, "url": url, "bytes": archive.stat().st_size, "sha256": digest})
        (ROOT / "download_manifest.json").write_text(json.dumps(records, indent=2) + "\n")
        print(f"{period}: downloaded, CRC verified, extracted", flush=True)
print("All 12 quarters ready.", flush=True)
