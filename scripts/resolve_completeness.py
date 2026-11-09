"""Resolve SEC shortlist facts using cached companyfacts with exact provenance.

Never replaces gross interest with net interest or cash paid; never imputes zero.
Outputs are data preparation artifacts, independent of the team's SQL schema.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from check_completeness import COMPANIES, ROOT, rows

OUT = ROOT / 'docs/data_quality/resolved'
DATA = ROOT / 'data/processed'
MAPPING = {
    'assets': ['Assets'],
    'current_assets': ['AssetsCurrent'],
    'current_liabilities': ['LiabilitiesCurrent'],
    'revenue': ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues',
                'SalesRevenueNet','RevenueFromContractWithCustomerIncludingAssessedTax'],
    'operating_income': ['OperatingIncomeLoss'],
    'interest_expense': ['InterestExpenseNonoperating','InterestExpense','InterestAndDebtExpense','InterestExpenseDebt'],
}
INSTANT = {'assets','current_assets','current_liabilities'}
DEBT = ['DebtLongtermAndShorttermCombinedAmount','LongTermDebt','ShortTermBorrowings','LongTermDebtCurrent','LongTermDebtNoncurrent']

def write(path, records):
    with path.open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(records[0]))
        w.writeheader(); w.writerows(records)

def select_value(facts, tags, accn, end, start=None):
    for tag in tags:
        matches=[r for r in facts.get(tag,{}).get('units',{}).get('USD',[])
                 if r.get('accn')==accn and r.get('end')==end
                 and r.get('start')==start]
        values={Decimal(str(r['val'])) for r in matches}
        if len(values)>1:
            return None,tag,'ambiguous'
        if values:
            return values.pop(),tag,'present'
    return None,'','unavailable'

def main():
    OUT.mkdir(parents=True,exist_ok=True); DATA.mkdir(parents=True,exist_ok=True)
    metadata={}
    for path in sorted((ROOT/'data/raw').glob('20*/sub.txt')):
        for r in rows(path):
            if r['cik'].isdigit() and int(r['cik']) in dict(COMPANIES) and r['form'] in ('10-K','10-Q'):
                metadata[r['adsh']]={**r,'source_quarter':path.parent.name}
    records=[]; provenance=[]; corrections=[]; definitions=[]; hashes=[]
    for cik,name in COMPANIES:
        path=ROOT/f'data/raw/companyfacts/CIK{cik:010d}.json'
        with path.open('rb') as stream: sha=hashlib.file_digest(stream,'sha256').hexdigest()
        hashes.append(dict(cik=cik,sha256=sha))
        payload=json.loads(path.read_text()); facts=payload['facts']['us-gaap']
        grouped=defaultdict(list)
        for r in facts.get('Assets',{}).get('units',{}).get('USD',[]):
            if r.get('accn') in metadata: grouped[r['accn']].append(r)
        chosen={}
        for a,fs in grouped.items():
            latest=max(fs,key=lambda r:r['end']); end=latest['end']; source=metadata[a]
            key=(source['filed'],a)
            if end not in chosen or key>chosen[end][0]: chosen[end]=(key,a,latest)
        company=[]
        for end,(_,a,asset) in sorted(chosen.items()):
            source=metadata[a]
            # Infer fiscal start from the longest current-period revenue/operating duration.
            starts=[r['start'] for tag in MAPPING['revenue']+MAPPING['operating_income']
                    for r in facts.get(tag,{}).get('units',{}).get('USD',[])
                    if r.get('accn')==a and r.get('end')==end and 'start' in r
                    and 60 <= (date.fromisoformat(end)-date.fromisoformat(r['start'])).days+1 <= 380]
            start=min(starts) if starts else None
            days=(date.fromisoformat(end)-date.fromisoformat(start)).days+1 if start else None
            q=4 if source['form']=='10-K' else min(3,max(1,round(days/91))) if days else None
            inferred='FY' if q==4 else f'Q{q}' if q else 'unknown'
            row=dict(cik=cik,company=name,period_end=end,reporting_year=int(end[:4]),
                     source_fy=asset.get('fy',''),source_fp=asset.get('fp',''),
                     inferred_period=inferred,fiscal_start=start or '',duration_days=days or '',
                     accession=a,filed=source['filed'],source_quarter=source['source_quarter'])
            if source['fy']!=str(asset.get('fy','')) or source['fp']!=str(asset.get('fp','')) or source['fp']!=inferred:
                corrections.append(dict(cik=cik,company=name,accession=a,sub_fy=source['fy'],sub_fp=source['fp'],
                                        api_fy=asset.get('fy',''),api_fp=asset.get('fp',''),inferred_period=inferred,
                                        actual_period_end=end,sub_period=source['period']))
            for metric,tags in MAPPING.items():
                value,tag,status=select_value(facts,tags,a,end,None if metric in INSTANT else start)
                if metric not in INSTANT and start is None: value,tag,status=None,'','no_duration'
                row[metric]=str(value) if value is not None else ''
                row[metric+'_status']=status
                row[metric+'_tag']=tag
                if tag:
                    definitions.append(dict(cik=cik,company=name,metric=metric,tag=tag,
                                            label=facts[tag].get('label',''),description=facts[tag].get('description') or ''))
                provenance.append(dict(cik=cik,company=name,period_end=end,accession=a,metric=metric,
                                       tag=tag,start='' if metric in INSTANT else start or '',end=end,
                                       value=str(value) if value is not None else '',status=status,
                                       url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'))
            # Candidate borrowing totals. Require explicit components and review
            # lease scope before comparing issuers; missing debt is never zero.
            debt={t:select_value(facts,[t],a,end) for t in DEBT}
            total=None; formula=''
            if debt['DebtLongtermAndShorttermCombinedAmount'][0] is not None:
                total=debt['DebtLongtermAndShorttermCombinedAmount'][0]
                formula='DebtLongtermAndShorttermCombinedAmount'
            elif debt['ShortTermBorrowings'][0] is not None:
                short=debt['ShortTermBorrowings'][0]
                if debt['LongTermDebt'][0] is not None:
                    total=short+debt['LongTermDebt'][0]; formula='ShortTermBorrowings + LongTermDebt'
                elif all(debt[t][0] is not None for t in ('LongTermDebtCurrent','LongTermDebtNoncurrent')):
                    total=short+debt['LongTermDebtCurrent'][0]+debt['LongTermDebtNoncurrent'][0]
                    formula='ShortTermBorrowings + LongTermDebtCurrent + LongTermDebtNoncurrent'
            row['total_debt_candidate']=str(total) if total is not None else ''
            row['debt_formula']=formula
            row['interest_scope']='gross_debt_interest' if row['interest_expense_tag']=='InterestExpenseDebt' else 'reported_interest_expense' if row['interest_expense'] else 'unavailable'
            for t,(value,tag,status) in debt.items():
                if value is not None:
                    provenance.append(dict(cik=cik,company=name,period_end=end,accession=a,metric='debt_component',
                                           tag=t,start='',end=end,value=str(value),status=status,
                                           url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'))
            company.append(row)
        # Normalize duration facts to individual fiscal quarters, including Q4=FY-Q3.
        # Only subtract equivalent tags with the identical fiscal-year start.
        for i,row in enumerate(company):
            q=4 if row['inferred_period']=='FY' else int(row['inferred_period'][1:]) if row['inferred_period']!='unknown' else None
            prevs=[r for r in company[:i] if r['fiscal_start']==row['fiscal_start']
                   and r['inferred_period']==f'Q{q-1}'] if q and q>1 else []
            previous=prevs[-1] if prevs else None
            for metric in set(MAPPING)-INSTANT:
                value=row[metric]; status='unavailable'; quarter=''; method=''
                if value and q==1:
                    quarter=value; status='reported'; method='current YTD equals Q1'
                elif value and q:
                    # Prefer an explicitly reported standalone period in this accession.
                    tag=row[metric+'_tag']
                    direct=[r for r in facts[tag].get('units',{}).get('USD',[])
                            if r.get('accn')==row['accession'] and r.get('end')==row['period_end']
                            and r.get('start') and 60 <= (date.fromisoformat(r['end'])-date.fromisoformat(r['start'])).days+1 <=125]
                    values={Decimal(str(r['val'])) for r in direct}
                    if len(values)==1:
                        quarter=str(values.pop());status='reported';method='standalone duration in current accession'
                    elif previous and previous[metric] and row[metric+'_tag']==previous[metric+'_tag']:
                        quarter=str(Decimal(value)-Decimal(previous[metric]));status='derived';method='current YTD minus prior YTD; same tag and fiscal start'
                row[metric+'_quarter']=quarter
                row[metric+'_quarter_status']=status
                row[metric+'_quarter_method']=method
                row[metric+'_previous_accession']=previous['accession'] if status=='derived' else ''
            row['six_metrics_ready']=all(row[m+'_status']=='present' for m in MAPPING)
            row['quarter_metrics_ready']=row['six_metrics_ready'] and all(row[m+'_quarter']!='' for m in set(MAPPING)-INSTANT)
            row['all_metrics_with_debt_ready']=row['quarter_metrics_ready'] and row['total_debt_candidate']!=''
            if '2023-01-01' <= row['period_end'] <= '2025-12-31': records.append(row)
        print(f'{name}: resolved',flush=True)
    write(DATA/'resolved_financials.csv',records)
    pilot_names=['Microsoft','Alphabet','Adobe','Intel','NVIDIA','PepsiCo','Kimberly-Clark','General Mills','Campbell','McCormick']
    pilot=[r for r in records if r['company'] in pilot_names]
    assert len(pilot)==120 and all(r['quarter_metrics_ready'] for r in pilot), 'Pilot core metrics must cover all 120 dates'
    write(DATA/'pilot_10_financials.csv',pilot)
    write(OUT/'filing_resolution.csv',[{k:v for k,v in r.items() if k not in MAPPING and not k.endswith('_quarter') and k!='total_debt_candidate'} for r in records])
    write(DATA/'metric_provenance.csv',provenance)
    unique={tuple(r.values()):r for r in definitions}
    write(OUT/'mapping_definitions.csv',list(unique.values()))
    write(OUT/'metadata_discrepancies.csv',corrections)
    summary=[]
    for cik,name in COMPANIES:
        rs=[r for r in records if r['cik']==cik]
        r=dict(cik=cik,company=name,reporting_dates=len(rs),
               six_metric_dates=sum(r['six_metrics_ready'] for r in rs),
               normalized_quarter_dates=sum(r['quarter_metrics_ready'] for r in rs),
               debt_ready_dates=sum(r['all_metrics_with_debt_ready'] for r in rs),
               unresolved_metrics=';'.join(m for m in MAPPING if any(x[m+'_status']!='present' for x in rs)))
        summary.append(r)
    write(OUT/'company_resolution.csv',summary)
    log=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),companies=len(COMPANIES),reporting_dates=len(records),
             metrics={m:dict(Counter(r[m+'_status'] for r in records)) for m in MAPPING},
             normalized_quarter_dates=sum(r['quarter_metrics_ready'] for r in records),
             with_debt_dates=sum(r['all_metrics_with_debt_ready'] for r in records),
             metadata_discrepancies=len(corrections),companyfacts_hashes=hashes)
    (OUT/'resolution_log.json').write_text(json.dumps(log,indent=2)+'\n')
    decisions=[]
    for r in summary:
        complete=r['reporting_dates']==12 and r['normalized_quarter_dates']==12
        decisions.append(dict(cik=r['cik'],company=r['company'],
                              decision='eligible_core_ratio_sample' if complete else 'exclude_from_complete_core_sample',
                              reason='12 normalized dates with six core metrics' if complete else
                              ('Standard gross-interest/operating-income mapping unavailable: '+r['unresolved_metrics'] if r['unresolved_metrics'] else 'Reporting-date boundary or duration/tag continuity gap'),
                              debt_decision='available_all_dates' if r['debt_ready_dates']==12 else 'do_not_impute_missing_debt_components'))
    write(OUT/'sample_decisions.csv',decisions)
    report=['# Resolved SEC completeness audit','',
            'This report supersedes the initial audit in ../REPORT.md. Original results remain as a historical baseline. No database schema was changed.','',
            '## Scope and fixes','',
            '- Target: actual reporting dates from January 1, 2023 through December 31, 2025, rather than unverified fiscal-year labels. There are 599 dates: 12 for 49 companies and 11 for Flowers Foods. Its next annual reporting date is in January 2026, outside this calendar-date window; this is a boundary effect, not a fabricated missing quarter.',
            '- Added 2022 filing batches for prior-period context and 2026 Q1 for late-filed 2025 results. The target analysis window remains 2023–2025.',
            '- Corrected InterestExpenseNonOperating to the actual case-sensitive tag InterestExpenseNonoperating.',
            '- Supplemented compact quarterly face-statement files with official SEC companyfacts. Matching requires the exact original accession, USD, actual reporting end date, and fiscal-duration start. Later-accession comparative/restated values are not substituted.',
            '- InterestExpenseDebt is a documented fallback for gross debt interest. Its narrower scope is labeled; net interest, tax penalties, and cash interest paid are never substituted.',
            '- Fiscal metadata discrepancies are preserved in metadata_discrepancies.csv. Fiscal period is inferred from duration and form; calendar-date grouping avoids asserting that inconsistent source fiscal-year labels are corrected.',
            '- Standalone-quarter facts are preferred; otherwise current YTD minus previous YTD requires the identical tag and fiscal start. Q4 uses annual minus Q3. Cross-filing derivations retain previous accession and need review for accounting/restatement changes.',
            '- Debt uses the explicitly reported combined short/long-term total, or explicit ShortTermBorrowings plus total LongTermDebt (or current/noncurrent components). Never add a total and its components; never infer absent components as zero. Lease treatment still requires confirmation from the company disclosures before comparing debt ratios across issuers.',
            '', '## Results','', '| Metric | Present | Unavailable |','| --- | ---: | ---: |']
    for m in MAPPING:
        counts=Counter(r[m+'_status'] for r in records)
        report.append(f"| {m} | {counts['present']} | {len(records)-counts['present']} |")
    eligible=sum(r['reporting_dates']==12 and r['normalized_quarter_dates']==12 for r in summary)
    report += ['',f'{eligible} companies have six core metrics on all 12 normalized dates. Across all 50 companies, {log["normalized_quarter_dates"]} dates pass core normalization; {log["with_debt_dates"]} additionally have an explicit debt amount. These are distinct readiness levels.',
               '', '## Prepared 10-company pilot','',
               ', '.join(pilot_names)+'.','',
               'The pilot has 120 rows with assets, current assets, current liabilities, revenue, operating income, and interest expense, including standalone duration values. It is ready for current-ratio and interest-coverage development. It is not a fully validated total-debt sample; debt gaps and lease-basis differences remain flagged.','',
               'Local files: data/processed/pilot_10_financials.csv, resolved_financials.csv, and metric_provenance.csv. These financial data artifacts remain ignored by Git.','',
               '## Disposition of remaining gaps','',
               'sample_decisions.csv explicitly excludes incomplete companies from the complete-core sample. Missing standard gross interest or operating income is classified as unavailable under the approved mappings, not zero. Company-specific disclosures may support future manual mappings; the script makes no unsupported inference.','',
               'Use current ratio and interest coverage for the complete-core pilot. Enable debt-to-assets only where an explicit debt amount and comparable lease treatment are validated; do not generate covenant pass/fail results from missing inputs.','',
               '## Reproduce','',
               '```sh','python3 scripts/download_sec_data.py --quarters 2022q1 2022q2 2022q3 2022q4 2026q1',
               'python3 scripts/fetch_companyfacts.py','python3 scripts/resolve_completeness.py','```','',
               'Source definitions: [SEC Financial Statement Data Sets](https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets) and [SEC XBRL API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces). API response SHA-256 hashes are in resolution_log.json; tag definitions are in mapping_definitions.csv.','']
    (OUT/'REPORT.md').write_text('\n'.join(report))
    print(json.dumps({k:v for k,v in log.items() if k!='companyfacts_hashes'}),flush=True)

if __name__=='__main__': main()
