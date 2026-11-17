"""Generate reproducible educational loans, two covenants per loan and initial ratings."""
import argparse
import csv
import json
import random
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from pilot_common import POLICY_VERSION, ROOT, digest, number, read_pilot

DEFAULT_SEED = 5132026
CR_BANDS = tuple(map(Decimal, ('2', '1.75', '1.5', '1.25', '1', '.9', '.8', '.7', '.6')))
IC_BANDS = tuple(map(Decimal, ('20', '12', '8', '5', '3', '2', '1.5', '1', '0')))


def risk_rating(current_ratio, interest_coverage):
    """1 = lowest monitored risk; 10 = highest. Weaker of two explicit bands."""
    cr_grade = next((i for i, floor in enumerate(CR_BANDS, 1) if current_ratio >= floor), 10)
    ic_grade = next((i for i, floor in enumerate(IC_BANDS, 1) if interest_coverage >= floor), 10)
    return max(cr_grade, ic_grade)


def build_records(rows, seed=DEFAULT_SEED):
    loans, covenants, ratings = [], [], []
    baselines = {}
    for row in sorted(rows, key=lambda r: (r['filed'], r['period_end'], r['accession'])):
        baselines.setdefault(int(row['cik']), row)
    for cik, baseline in sorted(baselines.items()):
        rng = random.Random(f'{POLICY_VERSION}:{seed}:{cik}')
        key = f'{POLICY_VERSION}-{cik}'
        originated = datetime.strptime(baseline['filed'], '%Y%m%d').date() + timedelta(days=1)
        try:
            maturity = originated.replace(year=originated.year + 3)
        except ValueError:  # February 29 -> February 28 three years later.
            maturity = originated.replace(year=originated.year + 3, day=28)
        fraction = Decimal(rng.randint(5, 20)) / Decimal(10000)
        principal = min(Decimal('250000000'), number(baseline['assets'], 'assets') * fraction)
        principal = principal.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        rate = Decimal(rng.randint(450, 850)) / Decimal(10000)
        cr = number(baseline['current_assets'], 'CA') / number(baseline['current_liabilities'], 'CL')
        ic = number(baseline['operating_income_quarter'], 'OI') / number(baseline['interest_expense_quarter'], 'IE')
        loans.append(dict(synthetic_key=key, cik=cik, principal=str(principal), currency='USD',
                          annual_interest_rate=f'{rate:.6f}', originated_on=originated.isoformat(),
                          matures_on=maturity.isoformat(), is_synthetic='true',
                          baseline_accession=baseline['accession'],
                          baseline_period_end=baseline['period_end'],
                          principal_asset_fraction=str(fraction)))
        floors = {'current_ratio': max(Decimal('.1'), cr * Decimal('.8')),
                  'interest_coverage': min(Decimal('5'), max(Decimal('1'), ic * Decimal('.6')))}
        for metric, floor in floors.items():
            covenants.append(dict(synthetic_key=key, metric=metric, comparison='>=',
                                  threshold=str(floor.quantize(Decimal('.000001'), rounding=ROUND_FLOOR)),
                                  effective_from=originated.isoformat(), effective_to=maturity.isoformat()))
        ratings.append(dict(cik=cik, rating=risk_rating(cr, ic), effective_on=originated.isoformat(),
                            reason=f'{POLICY_VERSION}; initial synthetic rating from {baseline["accession"]}; '
                                   f'current_ratio={cr:.6f}; quarterly_interest_coverage={ic:.6f}; '
                                   'weaker of the two policy bands', is_synthetic='true'))
    return {'synthetic_loans.csv': loans, 'synthetic_covenants.csv': covenants,
            'synthetic_ratings.csv': ratings}


def generate(path, output_dir, seed=DEFAULT_SEED):
    if not -(2**63) <= seed < 2**63:
        raise ValueError('Seed must fit a PostgreSQL bigint')
    rows = read_pilot(path)
    records = build_records(rows, seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {'policy_version': POLICY_VERSION, 'seed': seed, 'input_sha256': digest(path),
                'input_file': Path(path).name, 'input_rows': len(rows), 'files': {},
                'assumptions': {'loans_per_borrower': 1, 'term_years': 3, 'currency': 'USD',
                                'annual_rate_min': '0.045', 'annual_rate_max': '0.085',
                                'principal_asset_fraction_min': '0.0005',
                                'principal_asset_fraction_max': '0.0020',
                                'principal_cap_usd': '250000000', 'debt_covenants': False,
                                'baseline': 'first available filing; originate the following day'}}
    for filename, data in records.items():
        target = output_dir / filename
        with target.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(data)
        manifest['files'][filename] = {'rows': len(data), 'sha256': digest(target)}
    (output_dir / 'generation_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', required=True, type=Path)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'data/processed')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    print(json.dumps(generate(args.csv, args.output_dir, args.seed), indent=2))
