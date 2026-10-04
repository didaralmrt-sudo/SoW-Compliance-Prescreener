"""Deterministic keyword + currency/amount baseline. Standard library only.
No API, language model, ground-truth access, case-ID rules or learned thresholds.
Limitations: no entity resolution, ownership allocation, general negation,
period reasoning or reliable separation of several same-category sources.
"""
import copy,json,re,time
from pathlib import Path
BASELINE_VERSION='keyword_money_v1'
MONEY=re.compile(r'(?<![A-Za-z])(SGD|USD|HKD|EUR|GBP|CNY|RMB)\s*([0-9][0-9,]*(?:\.[0-9]+)?)(?![0-9])',re.I)
KEYWORDS={
 'salary':r'薪资|工资|salary|salaries|payroll',
 'gift':r'赠与|赠予|gift|donation',
 'inheritance':r'遗产|继承|inheritance|inherited|estate distribution',
 'investment':r'基金|赎回|分红|股息|投资收益|fund|redemption|dividend|investment gain|investment return',
 'equity_sale':r'股权.{0,8}(?:出售|转让)|(?:出售|转让).{0,12}股权|equity sale|share sale|sale of shares|share transfer'}
INJECTION=re.compile(r'忽略.{0,12}指令|不要报告差异|ignore.{0,30}instructions|输出无问题',re.I)
NONPAYMENT=re.compile(r'未支付任何|未收到|尚未满足|尚未交割|payment remains pending|has not been paid|not yet paid',re.I)
PAID=re.compile(r'到账|已收到|实际收到|全额记入|credited|payment.{0,20}completed|paid in full|settled',re.I)

def categories(text):
    return {k for k,p in KEYWORDS.items() if re.search(p,text,re.I)}

def category(text,fallback='unknown'):
    found=categories(text)
    if len(found)==1:return next(iter(found))
    if not found:return fallback
    # Explicit dividends/fund text takes precedence over a generic equity mention.
    if 'investment' in found and re.search(r'基金|赎回|分红|股息|fund|redemption|dividend',text,re.I):return 'investment'
    return fallback

def basis(cat,text):
    if cat=='investment':
        if re.search(r'净收益|net (?:investment )?gain|investment gain',text,re.I):return 'investment_net_gain'
        if re.search(r'本金|principal|contributed',text,re.I):return 'investment_principal'
        if re.search(r'分红|股息|dividend',text,re.I):return 'investment_dividend'
        return 'redemption_total'
    if cat=='equity_sale':
        return 'equity_paid_proceeds' if re.search(r'收到|收款|到账|received|credited',text,re.I) else 'equity_agreed_proceeds'
    return {'salary':'salary_net_total','gift':'gift_cash','inheritance':'inheritance_cash'}.get(cat,'unspecified')

def clause(text,position):
    # Keep thousands commas intact; use sentence/Chinese clause boundaries.
    bounds=[0]+[m.end() for m in re.finditer(r'[，；;。]|\.(?!\d)',text)]+[len(text)]
    for a,b in zip(bounds,bounds[1:]):
        if a<=position<b:return text[a:b]
    return text

def extract(doc,fallback):
    text=' '.join(l['text'] for l in doc['lines']);cat=category(text,fallback);items=[]
    for line in doc['lines']:
        for match in MONEY.finditer(line['text']):
            local=clause(line['text'],match.start());kind=category(local,cat)
            items.append({'source_label':kind,'amount':float(match[2].replace(',','')),
                'currency':match[1].upper().replace('RMB','CNY'),'amount_basis':basis(kind,local),
                '_category':kind,'_ref':{'doc_id':doc['doc_id'],'line_id':line['line_id'],'quote':line['text']}})
    return items

def predict(case):
    t=time.perf_counter();decl=case['declaration'];docs=case['documents']
    text=' '.join(l['text'] for l in decl['lines']);types=categories(text)
    source_type=next(iter(types)) if len(types)==1 else ('mixed' if types else 'unknown')
    fallback=source_type if source_type!='mixed' else 'unknown'
    # Last mentioned amount within category/currency is a simple declared-amount
    # heuristic, not an assessment-case exception. All source quotes are retained.
    groups={}
    for f in extract(decl,fallback):groups[(f['_category'],f['currency'])]=f
    claims=list(groups.values());facts=[]
    for doc in docs:
        doc_text=' '.join(l['text'] for l in doc['lines'])
        for f in extract(doc,fallback):
            f['transaction_status']='pending' if NONPAYMENT.search(f['_ref']['quote']) else ('completed' if PAID.search(f['_ref']['quote']) else 'unknown')
            facts.append(f)
    # Merge exact fact duplicates, not different amounts or financial concepts.
    unique={}
    for f in facts:
        key=tuple(f[k] for k in ('source_label','amount','currency','amount_basis','transaction_status'))
        unique.setdefault(key,f)
    facts=list(unique.values());issues=[];evidence=[];missing=[]
    def issue(code,refs=()):
        if code not in issues:issues.append(code)
        for ref in refs:
            entry={**ref,'supports_field':'issue_codes'}
            if entry not in evidence:evidence.append(entry)
    for i,f in enumerate(claims):evidence.append({**f['_ref'],'supports_field':f'claims[{i}].amount'})
    for i,f in enumerate(facts):
        evidence.extend([{**f['_ref'],'supports_field':f'supported_facts[{i}].{field}'} for field in ('amount','transaction_status')])
    if not docs and text.strip():issue('missing_evidence');missing.append('No supporting documents supplied.')
    for c in claims:
        same=[f for f in facts if f['_category']==c['_category'] and f['currency']==c['currency'] and f['amount_basis']==c['amount_basis']]
        if same and not any(abs(f['amount']-c['amount'])<=0.01 for f in same):issue('amount_mismatch',[c['_ref'],same[0]['_ref']])
        elif docs and not same:issue('insufficient_information',[c['_ref']]);missing.append('No amount matched under the baseline keyword/category/currency/basis rules.')
    for doc in docs:
        for l in doc['lines']:
            ref={'doc_id':doc['doc_id'],'line_id':l['line_id'],'quote':l['text']}
            if NONPAYMENT.search(l['text']):issue('transaction_not_completed',[ref])
    for doc in [decl,*docs]:
        for l in doc['lines']:
            if INJECTION.search(l['text']):issue('prompt_injection',[{'doc_id':doc['doc_id'],'line_id':l['line_id'],'quote':l['text']}])
    usable=any(l['text'].strip() for doc in [decl,*docs] for l in doc['lines'])
    if not usable:source_type='unknown';action='insufficient_input';issue('insufficient_information')
    elif not claims:action='human_review';issue('insufficient_information');missing.append('No declaration currency/amount matched the baseline regex.')
    else:action='human_review' if issues else 'no_issue_detected'
    def clean(f):return {k:v for k,v in f.items() if not k.startswith('_')}
    output={'source_type':source_type,'claims':[clean(f) for f in claims],'supported_facts':[clean(f) for f in facts],
        'review_action':action,'issue_codes':issues,'evidence':evidence,'calculations':[],'missing_information':missing}
    return {'case_id':case['case_id'],'pipeline_version':BASELINE_VERSION,'status':'rule_output',
        'candidate_output':copy.deepcopy(output),'validated_output':output,'latency_seconds':time.perf_counter()-t,
        'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0,'cost':0},
        'cost_note':'No model API; CPU/runtime cost not estimated.'}

def run(input_path,output_dir):
    obj=json.loads(Path(input_path).read_text())
    if 'ground_truth' in obj:raise ValueError('Baseline accepts inputs-only JSON.')
    cases=obj['inputs'];dest=Path(output_dir);dest.mkdir(parents=True,exist_ok=True)
    for c in cases:
        record=predict(c)
        (dest/(c['case_id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
    (dest/'inputs_used.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2))
    return dest
