"""Stream SEC files to audit shortlisted companies; no database changes.

Coverage checks use consolidated, USD, standard US-GAAP facts at each filing's
reporting date. They do not normalize company extensions or derive quarters.
"""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'data_quality'
COMPANIES = [
    (320193,'Apple'),(789019,'Microsoft'),(1652044,'Alphabet'),(1326801,'Meta Platforms'),
    (1341439,'Oracle'),(796343,'Adobe'),(1108524,'Salesforce'),(896878,'Intuit'),
    (1373715,'ServiceNow'),(858877,'Cisco Systems'),(51143,'IBM'),(8670,'Automatic Data Processing'),
    (50863,'Intel'),(2488,'Advanced Micro Devices'),(1045810,'NVIDIA'),(804328,'Qualcomm'),
    (97476,'Texas Instruments'),(6281,'Analog Devices'),(6951,'Applied Materials'),(707549,'Lam Research'),
    (21344,'Coca-Cola'),(77476,'PepsiCo'),(80424,'Procter & Gamble'),(21665,'Colgate-Palmolive'),
    (55785,'Kimberly-Clark'),(40704,'General Mills'),(1103982,'Mondelez International'),
    (47111,'Hershey'),(16732,'Campbell'),(23217,'Conagra Brands'),(1637459,'Kraft Heinz'),
    (313927,'Church & Dwight'),(21076,'Clorox'),(63754,'McCormick'),(1128928,'Flowers Foods'),
    (104169,'Walmart'),(27419,'Target'),(354950,'Home Depot'),(60667,"Lowe's"),
    (909832,'Costco'),(109198,'TJX Companies'),(745732,'Ross Stores'),(29534,'Dollar General'),
    (935703,'Dollar Tree'),(764478,'Best Buy'),(56873,'Kroger'),(866787,'AutoZone'),
    (898173,"O'Reilly Automotive"),(916365,'Tractor Supply'),(1403568,'Ulta Beauty'),
]
NAMES = dict(COMPANIES)
TAGS = {
    'assets': ['Assets'],
    'current_assets': ['AssetsCurrent'],
    'current_liabilities': ['LiabilitiesCurrent'],
    'revenue': ['RevenueFromContractWithCustomerExcludingAssessedTax',
                'RevenueFromContractWithCustomerIncludingAssessedTax','Revenues','SalesRevenueNet'],
    'operating_income': ['OperatingIncomeLoss'],
    'interest_expense': ['InterestExpenseNonOperating','InterestAndDebtExpense','InterestExpense'],
}
# Debt alternatives are audited separately, rather than silently mixing definitions.
DEBT_TAGS = {'LongTermDebtCurrent','LongTermDebtNoncurrent','LongTermDebt',
             'ShortTermBorrowings','ShortTermDebtCurrent','LongTermDebtAndCapitalLeaseObligationsCurrent',
             'LongTermDebtAndCapitalLeaseObligations','LongTermDebtAndFinanceLeaseObligationsCurrent',
             'LongTermDebtAndFinanceLeaseObligationsNoncurrent','DebtCurrent'}
INTEREST = set().union(*TAGS.values(), DEBT_TAGS)

def rows(path):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        yield from csv.DictReader(stream, delimiter='\t')

def write_csv(name, records, fields):
    with (OUT / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    batches = sorted((ROOT / 'data/raw').glob('20*/sub.txt'))
    filings = {}
    by_period = defaultdict(list)
    log = []
    for path in batches:
        for r in rows(path):
            if not r['cik'].isdigit() or int(r['cik']) not in NAMES:
                continue
            if r['form'] not in ('10-Q','10-K') or not ('20230101' <= r['period'] <= '20251231'):
                continue
            r['cik'] = int(r['cik'])
            r['source_quarter'] = path.parent.name
            filings[r['adsh']] = r
    for adsh, r in filings.items():
        by_period[(r['cik'],r['period'])].append(adsh)
    # One latest original filing per reporting date; amendments deliberately excluded.
    selected = {max(ids, key=lambda a:(filings[a]['filed'],a)) for ids in by_period.values()}
    facts = defaultdict(lambda: defaultdict(set))
    exclusions = Counter()
    candidates = Counter()
    for path in batches:
        scanned = matched = 0
        for r in rows(path.parent / 'num.txt'):
            scanned += 1
            a = r['adsh']
            if a not in selected:
                continue
            f = filings[a]
            if r['ddate'] != f['period']:
                continue
            if r['uom'] != 'USD' or r['segments'] or r['coreg']:
                exclusions['non_USD_or_dimensional'] += 1
                continue
            if any(x in r['tag'].lower() for x in ('interest','debt','revenue')):
                candidates[(f['cik'],r['tag'],r['version'])] += 1
            if r['tag'] not in INTEREST or not r['version'].startswith('us-gaap/'):
                continue
            try:
                value = Decimal(r['value'])
                if not value.is_finite():
                    continue
            except InvalidOperation:
                continue
            instant = r['tag'] in DEBT_TAGS or r['tag'] in {'Assets','AssetsCurrent','LiabilitiesCurrent'}
            allowed = {'0'} if instant else ({'4'} if f['fp']=='FY' else {'1',str({'Q1':1,'Q2':2,'Q3':3,'Q4':4}.get(f['fp'],0))})
            if r['qtrs'] not in allowed:
                continue
            facts[a][(r['tag'],r['qtrs'])].add(str(value))
            matched += 1
        message = f'{path.parent.name}: scanned {scanned:,} numeric rows; retained {matched:,} candidate facts'
        print(message, flush=True)
        log.append(message)
    detail = []
    for a in sorted(selected, key=lambda a:(filings[a]['cik'],filings[a]['period'])):
        f = filings[a]
        row = {k:f[k] for k in ('cik','period','fy','fp','form','filed','source_quarter')}
        row.update(company=NAMES[f['cik']], adsh=a)
        source = facts[a]
        for metric, tags in TAGS.items():
            matches = [(t,q,vs) for (t,q),vs in source.items() if t in tags]
            if any(len(vs)>1 for _,_,vs in matches):
                status = 'ambiguous'
            else:
                status = 'present' if matches else 'missing_standard_tag'
            row[metric] = status
            row[metric+'_tags'] = ';'.join(sorted({t for t,_,_ in matches}))
            row[metric+'_qtrs'] = ';'.join(sorted({q for _,q,_ in matches}))
        debt = sorted({t for t,q in source if t in DEBT_TAGS})
        row['debt_components'] = 'available_needs_definition' if debt else 'missing_standard_tag'
        row['debt_tags'] = ';'.join(debt)
        row['ratio_inputs_present'] = all(row[m]=='present' for m in TAGS)
        detail.append(row)
    summary = []
    for cik,name in COMPANIES:
        subset = [r for r in detail if r['cik']==cik]
        periods = {(r['fy'],r['fp']) for r in subset}
        expected = {(str(y),p) for y in range(2023,2026) for p in ('Q1','Q2','Q3','FY')}
        r = dict(cik=cik,company=name,reporting_dates=len(subset),
                 missing_fiscal_periods=';'.join(y+p for y,p in sorted(expected-periods)),
                 complete_metric_dates=sum(x['ratio_inputs_present'] for x in subset))
        for metric in TAGS:
            r[metric+'_present'] = sum(x[metric]=='present' for x in subset)
        r['debt_component_dates'] = sum(x['debt_components']=='available_needs_definition' for x in subset)
        summary.append(r)
    write_csv('company_completeness.csv',summary,list(summary[0]))
    write_csv('filing_completeness.csv',detail,list(detail[0]))
    inventory = [dict(cik=cik,company=NAMES[cik],tag=tag,version=version,fact_count=n)
                 for (cik,tag,version),n in sorted(candidates.items())]
    write_csv('candidate_tag_inventory.csv',inventory,['cik','company','tag','version','fact_count'])
    meta = dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),companies=len(COMPANIES),
                selected_filings=len(selected),input_batches=[p.parent.name for p in batches],
                exclusions=dict(exclusions),log=log)
    (OUT/'check_log.json').write_text(json.dumps(meta,indent=2)+'\n')
    report = [
        '# SEC shortlist completeness audit', '',
        f'Checked {len(COMPANIES)} companies and {len(selected)} selected reporting dates across {len(batches)} filing batches.',
        '', '## Method and limits', '',
        '- Source: downloaded 2023 Q1–2025 Q4 SEC Financial Statement Data Sets. No raw files were changed.',
        '- Includes original 10-K/10-Q filings with reporting dates in calendar 2023–2025; chooses the latest original filing for each company/reporting date. Amendments are excluded.',
        '- Uses USD, non-dimensional, non-co-registrant US-GAAP facts at the filing reporting date. Company extensions and net-interest concepts are not automatically mapped.',
        '- Missing standard tags mean mapping or source review is needed; they do not prove the underlying financial information is unavailable.',
        '- Instant metrics require qtrs=0; duration metrics accept standalone quarters or matching year-to-date periods, and annual values for FY. Presence does not establish comparable standalone-quarter ratios.',
        '- Conflicting values for the same tag/duration are flagged ambiguous.',
        '- Debt component availability is reported separately. Total debt and lease treatment still need an agreed definition; no total debt completeness claim is made.',
        '- Fiscal coverage expects Q1/Q2/Q3/FY for fiscal 2023–2025. Fiscal-year labels can differ from calendar years. FY2025 filings made in 2026 are outside the downloaded batches.',
        '', '## Metric summary', '',
        '| Metric | Present | Missing standard mapping | Ambiguous |',
        '| --- | ---: | ---: | ---: |',
    ]
    for metric in TAGS:
        counts = Counter(r[metric] for r in detail)
        report.append(f"| {metric} | {counts['present']} | {counts['missing_standard_tag']} | {counts['ambiguous']} |")
    report += [
        '', f"All six mapped metrics occur together on {sum(r['complete_metric_dates'] for r in summary)} of {len(detail)} reporting dates. This excludes total-debt readiness and duration normalization.",
        '', '## Results', '',
        '| Company | Reporting dates | Dates with all six mapped metrics | Missing fiscal periods |',
        '| --- | ---: | ---: | --- |',
    ]
    for r in summary:
        report.append(f"| {r['company']} | {r['reporting_dates']} | {r['complete_metric_dates']} | {r['missing_fiscal_periods'] or 'None'} |")
    report += ['', '## Follow-up', '',
        'Review missing/ambiguous metrics in filing_completeness.csv and candidate_tag_inventory.csv before selecting the final sample. Resolve interest expense and debt mappings, normalize duration values, and obtain 2026 filing batches where FY2025 coverage is needed. Keep missing values distinct from zero.',
        '', 'Rerun: `python3 scripts/check_completeness.py`.', '']
    (OUT/'REPORT.md').write_text('\n'.join(report))
    print(json.dumps({'companies':len(summary),'filings':len(detail),'fully_mapped_dates':sum(r['complete_metric_dates'] for r in summary)}),flush=True)

if __name__ == '__main__':
    main()
