"""SoW prescreen: one case -> one OpenRouter call -> validated evidence + audit file.
Standard library only. No labels are read during inference. Evidence presence and
arithmetic are deterministic; semantic support remains subject to human review.
"""
import argparse
import copy
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parent
SOURCES={'equity_sale','salary','investment','inheritance','gift','mixed','unknown'}
ACTIONS={'no_issue_detected','human_review','insufficient_input'}
STATUS={'completed','pending','unknown','not_applicable'}
ISSUES={'amount_mismatch','ownership_proceeds_mismatch','transaction_not_completed','missing_evidence','insufficient_information','currency_not_comparable','conflicting_documents','prompt_injection'}
FIELDS={'source_type','claims','supported_facts','review_action','issue_codes','evidence','calculations','missing_information'}
INJECTION=re.compile(r'忽略.{0,12}指令|不要报告差异|ignore.{0,30}instructions|输出无问题',re.I)
NUMBERS=re.compile(r'(?<![A-Za-z0-9.])\d[\d,]*(?:\.\d+)?\s*%?')

def load_cases(path):
    """Read inputs only; reject a combined input/ground-truth file."""
    obj=json.loads(Path(path).read_text(encoding='utf-8'))
    if 'ground_truth' in obj: raise ValueError('Use inputs-only file, never combined labels.')
    cases=obj['inputs']
    if not isinstance(cases,list): raise ValueError('inputs must be a list')
    ids=[c['case_id'] for c in cases]
    if len(set(ids))!=len(ids): raise ValueError('Duplicate case IDs')
    for c in cases:
        documents(c)
    return cases

def documents(case):
    """Index case-local lines; prevent ambiguous document and line IDs."""
    result={}
    for doc in [case['declaration'],*case['documents']]:
        if doc['doc_id'] in result: raise ValueError('Duplicate document ID')
        lines={}
        for line in doc['lines']:
            if line['line_id'] in lines: raise ValueError('Duplicate line ID')
            if not isinstance(line['text'],str): raise ValueError('Line text must be string')
            lines[line['line_id']]=line['text']
        result[doc['doc_id']]=lines
    return result

def numeric(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and Decimal(str(x)).is_finite()

def numbers(text):
    result=set()
    for m in NUMBERS.finditer(text):
        s=m.group().strip(); percentage=s.endswith('%')
        try:
            n=Decimal(s.rstrip('%').replace(',','').strip())
            result.add(n/100 if percentage else n)
        except InvalidOperation: pass
    return result

def check_ref(ref,docs):
    return (isinstance(ref,dict) and isinstance(ref.get('quote'),str) and bool(ref['quote'].strip())
        and ref.get('doc_id') in docs and ref.get('line_id') in docs[ref['doc_id']]
        and ref['quote'] in docs[ref['doc_id']][ref['line_id']])

def resolve_amount(obj,path):
    m=re.fullmatch(r'(claims|supported_facts)\[(\d+)\]\.amount',str(path))
    if not m: raise ValueError('Invalid amount target')
    return obj[m[1]][int(m[2])],m[1]

PIPELINE_VERSION = "v4_1_evidence_binding"
OUTPUT_SCHEMA = {'type': 'object', 'properties': {'source_type': {'type': 'string', 'enum': ['equity_sale', 'salary', 'investment', 'inheritance', 'gift', 'mixed', 'unknown']}, 'claims': {'type': 'array', 'items': {'type': 'object', 'properties': {'source_label': {'type': 'string'}, 'amount': {'type': ['number', 'null']}, 'currency': {'type': ['string', 'null']}, 'amount_basis': {'type': 'string'}}, 'required': ['source_label', 'amount', 'currency', 'amount_basis'], 'additionalProperties': False}}, 'supported_facts': {'type': 'array', 'items': {'type': 'object', 'properties': {'source_label': {'type': 'string'}, 'amount': {'type': ['number', 'null']}, 'currency': {'type': ['string', 'null']}, 'amount_basis': {'type': 'string'}, 'transaction_status': {'type': 'string', 'enum': ['completed', 'pending', 'unknown', 'not_applicable']}}, 'required': ['source_label', 'amount', 'currency', 'amount_basis', 'transaction_status'], 'additionalProperties': False}}, 'review_action': {'type': 'string', 'enum': ['no_issue_detected', 'human_review', 'insufficient_input']}, 'issue_codes': {'type': 'array', 'items': {'type': 'string', 'enum': ['amount_mismatch', 'ownership_proceeds_mismatch', 'transaction_not_completed', 'missing_evidence', 'insufficient_information', 'currency_not_comparable', 'conflicting_documents', 'prompt_injection']}}, 'evidence': {'type': 'array', 'items': {'type': 'object', 'properties': {'supports_field': {'type': 'string', 'description': 'Literal field path, e.g. claims[0].amount or supported_facts[0].transaction_status. Never a financial value.'}, 'doc_id': {'type': 'string'}, 'line_id': {'type': 'string'}, 'quote': {'type': 'string'}}, 'required': ['supports_field', 'doc_id', 'line_id', 'quote'], 'additionalProperties': False}}, 'calculations': {'type': 'array', 'items': {'type': 'object', 'properties': {'operation': {'type': 'string', 'enum': ['add', 'subtract', 'multiply', 'divide']}, 'operands': {'type': 'array', 'items': {'type': 'number'}}, 'result': {'type': 'null'}, 'currency': {'type': 'string'}, 'purpose': {'type': 'string'}, 'target_field': {'type': ['string', 'null']}, 'evidence_refs': {'type': 'array', 'items': {'type': 'object', 'properties': {'doc_id': {'type': 'string'}, 'line_id': {'type': 'string'}, 'quote': {'type': 'string'}}, 'required': ['doc_id', 'line_id', 'quote'], 'additionalProperties': False}}}, 'required': ['operation', 'operands', 'result', 'currency', 'purpose', 'target_field', 'evidence_refs'], 'additionalProperties': False}}, 'missing_information': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['source_type', 'claims', 'supported_facts', 'review_action', 'issue_codes', 'evidence', 'calculations', 'missing_information'], 'additionalProperties': False}

def structure_errors(value, schema, path='output'):
    """Validate the response's structure before evidence checks; no data repair."""
    types = schema.get('type', [])
    types = [types] if isinstance(types, str) else types
    predicates = {'object':lambda x:isinstance(x,dict),
                  'array':lambda x:isinstance(x,list),
                  'string':lambda x:isinstance(x,str),
                  'number':numeric, 'null':lambda x:x is None}
    if not any(predicates[t](value) for t in types):
        return [f'{path}: expected {types}, got {type(value).__name__}']
    errors=[]
    if 'enum' in schema and value not in schema['enum']:
        errors.append(f'{path}: value outside allowed enum')
    if isinstance(value,dict):
        properties=schema.get('properties',{})
        for key in schema.get('required',[]):
            if key not in value:errors.append(f'{path}.{key}: missing required field')
        if schema.get('additionalProperties') is False:
            for key in set(value)-set(properties):errors.append(f'{path}.{key}: unexpected field')
        for key in set(value)&set(properties):
            errors.extend(structure_errors(value[key],properties[key],f'{path}.{key}'))
    elif isinstance(value,list):
        for i,item in enumerate(value):
            errors.extend(structure_errors(item,schema['items'],f'{path}[{i}]'))
    return errors

# Compact wire format: choose source lines next to each fact. The application,
# not the model, constructs v4 field paths and copies the original line text.
REQUEST_SCHEMA = copy.deepcopy(OUTPUT_SCHEMA)
LINE_REF = {'type':'object','properties':{'doc_id':{'type':'string'},'line_id':{'type':'string'}},
            'required':['doc_id','line_id'],'additionalProperties':False}
for _kind in ('claims','supported_facts'):
    _item=REQUEST_SCHEMA['properties'][_kind]['items']
    _item['properties']['amount_evidence']={'type':'array','items':copy.deepcopy(LINE_REF)}
    _item['required'].append('amount_evidence')
    if _kind=='supported_facts':
        _item['properties']['status_evidence']={'type':'array','items':copy.deepcopy(LINE_REF)}
        _item['required'].append('status_evidence')
_issue=REQUEST_SCHEMA['properties']['evidence']['items']
del _issue['properties']['quote'];_issue['required'].remove('quote')
_issue['properties']['supports_field']={'type':'string','enum':['issue_codes']}
REQUEST_SCHEMA['properties']['calculations']['items']['properties']['evidence_refs']['items']=copy.deepcopy(LINE_REF)


def attach_source_lines(wire, case):
    """Convert validated wire data to v4 form without changing financial values.
    Invalid IDs are rejected; no fuzzy search or automatic alternative source.
    """
    errors=structure_errors(wire,REQUEST_SCHEMA)
    if errors: raise ValueError('Response structure: '+'; '.join(errors))
    docs=documents(case);out=copy.deepcopy(wire)
    def hydrate(ref):
        try: quote=docs[ref['doc_id']][ref['line_id']]
        except KeyError: raise ValueError('Unknown evidence document/line ID') from None
        return {**ref,'quote':quote}
    evidence=[{**hydrate({'doc_id':e['doc_id'],'line_id':e['line_id']}),
               'supports_field':e['supports_field']} for e in out['evidence']]
    for kind in ('claims','supported_facts'):
        for i,f in enumerate(out[kind]):
            for ref in f.pop('amount_evidence'):
                evidence.append({**hydrate(ref),'supports_field':f'{kind}[{i}].amount'})
            if kind=='supported_facts':
                for ref in f.pop('status_evidence'):
                    evidence.append({**hydrate(ref),'supports_field':f'{kind}[{i}].transaction_status'})
    out['evidence']=evidence
    for c in out['calculations']:
        c['evidence_refs']=[hydrate(e) for e in c['evidence_refs']]
    return out


def consolidate_exact_facts(obj):
    """Merge only identical facts; remap paths while keeping all source refs.
    Amount/basis/status/currency/name differences prevent a merge.
    """
    remap={};events=[]
    for kind in ('claims','supported_facts'):
        unique=[];seen={}
        for i,f in enumerate(obj[kind]):
            signature=json.dumps(f,sort_keys=True,ensure_ascii=False)
            if signature not in seen:
                seen[signature]=len(unique);unique.append(f)
            j=seen[signature];remap[f'{kind}[{i}]']=f'{kind}[{j}]'
            if i!=j:events.append({'from':f'{kind}[{i}]','to':f'{kind}[{j}]','reason':'exact_duplicate_or_index_shift'})
        obj[kind]=unique
    def target(path):
        if not isinstance(path,str):return path
        return re.sub(r'^(claims|supported_facts)\[\d+\]',lambda m:remap.get(m[0],m[0]),path)
    for e in obj['evidence']:e['supports_field']=target(e['supports_field'])
    for c in obj['calculations']:c['target_field']=target(c['target_field'])
    return events


def validate_output(candidate,case):
    """Check schema, quotes, provenance, numbers and arithmetic. Never consult labels.
    A green check verifies mechanical consistency, not semantic truth/authenticity.
    """
    obj=copy.deepcopy(candidate);errors=[];checks=[];docs=documents(case)
    structural_errors=structure_errors(obj,OUTPUT_SCHEMA)
    if structural_errors:
        if isinstance(obj,dict):obj['review_action']='human_review'
        return obj if isinstance(obj,dict) else None, {'schema_ok':False,'mechanical_checks_ok':False,'errors':structural_errors,'forced_review':True}

    if not isinstance(obj,dict): return None,{'schema_ok':False,'errors':['Output is not object']}
    if set(obj)!=FIELDS: errors.append('Top-level fields do not match contract')
    if (not isinstance(obj.get('source_type'),str) or obj.get('source_type') not in SOURCES):errors.append('Invalid source_type')
    if (not isinstance(obj.get('review_action'),str) or obj.get('review_action') not in ACTIONS):errors.append('Invalid review_action')
    for name in ['claims','supported_facts','issue_codes','evidence','calculations','missing_information']:
        if not isinstance(obj.get(name),list):errors.append(f'{name} must be array')
    if errors:
        obj['review_action']='human_review'
        return obj,{'schema_ok':False,'errors':errors,'forced_review':True}
    if any(not isinstance(i,str) or i not in ISSUES for i in obj['issue_codes']):errors.append('Invalid issue code')
    if any(not isinstance(i,str) for i in obj['missing_information']):errors.append('Invalid missing_information')
    for name in ['claims','supported_facts']:
        required={'source_label','amount','currency','amount_basis'}|({'transaction_status'} if name=='supported_facts' else set())
        for i,f in enumerate(obj[name]):
            if not isinstance(f,dict) or set(f)!=required:
                errors.append(f'{name}[{i}] invalid fields');continue
            if not isinstance(f['source_label'],str) or not isinstance(f['amount_basis'],str):errors.append(f'{name}[{i}] invalid text')
            if f['amount'] is not None and (not numeric(f['amount']) or f['amount']<0):errors.append(f'{name}[{i}] invalid amount')
            if f['currency'] is not None and not re.fullmatch('[A-Z]{3}',str(f['currency'])):errors.append(f'{name}[{i}] invalid currency')
            if name=='supported_facts' and (not isinstance(f['transaction_status'],str) or f['transaction_status'] not in STATUS):errors.append(f'{name}[{i}] invalid status')
    if errors:
        obj['review_action']='human_review'
        return obj,{'schema_ok':False,'errors':errors,'forced_review':True}
    normalization_events=consolidate_exact_facts(obj)
    schema_ok=True
    initial_action=obj['review_action']
    if not obj['claims'] and not obj['supported_facts'] and any(
        line['text'].strip() for doc in [case['declaration'],*case['documents']] for line in doc['lines']
    ):
        errors.append('Nonempty input returned no facts; human must check whether usable wealth information was omitted')
    for i,e in enumerate(obj['evidence']):
        if not check_ref(e,docs) or not isinstance(e.get('supports_field'),str):
            errors.append(f'evidence[{i}] missing/invalid quote or target')
    verified_results=[];verified_targets=set();passed_calculations=set();valid_amount_paths=set()
    for i,c in enumerate(obj['calculations']):
        try:
            if not isinstance(c,dict):raise ValueError('calculation not object')
            op=c['operation']; operands=c['operands'];refs=c['evidence_refs']
            if not isinstance(op,str) or op not in {'add','subtract','multiply','divide'} or not isinstance(operands,list) or len(operands)!=2 or not all(numeric(v) for v in operands):raise ValueError('invalid operands/operator')
            if not isinstance(refs,list):raise ValueError('evidence_refs must be array')
            if not isinstance(c.get('currency'),str) or not re.fullmatch('[A-Z]{3}',c['currency']):raise ValueError('invalid calculation currency')
            if not refs or not all(check_ref(e,docs) and not INJECTION.search(e['quote']) for e in refs):raise ValueError('invalid arithmetic evidence')
            ref_docs={e['doc_id'] for e in refs}
            prior={v for v,currency,source_docs in verified_results if currency==c['currency'] and source_docs<=ref_docs}
            available=set().union(*(numbers(e['quote']) for e in refs))|prior
            a,b=map(lambda v:Decimal(str(v)),operands)
            if a not in available or b not in available:raise ValueError('operand not in evidence or prior verified calculation')
            if op=='divide' and b==0:raise ValueError('division by zero')
            result={'add':lambda:a+b,'subtract':lambda:a-b,'multiply':lambda:a*b,'divide':lambda:a/b}[op]()
            if not result.is_finite():raise ValueError('nonfinite result')
            if c.get('result') is not None and (not numeric(c['result']) or abs(Decimal(str(c['result']))-result)>Decimal('0.01')):raise ValueError('model result differs from Python')
            c['result']=float(result)
            if c.get('target_field'):
                f,kind=resolve_amount(obj,c['target_field'])
                allowed_docs={case['declaration']['doc_id']} if kind=='claims' else {x['doc_id'] for x in case['documents']}
                if any(r['doc_id'] not in allowed_docs for r in refs):raise ValueError('derived fact cites wrong source')
                if f['currency']!=c.get('currency'):raise ValueError('derived fact currency mismatch')
                if result<0:raise ValueError('negative derived monetary fact')
                if f['amount'] is not None and abs(Decimal(str(f['amount']))-result)>Decimal('0.01'):raise ValueError('fact conflicts with computed result')
                f['amount']=float(result);verified_targets.add(c['target_field'])
            verified_results.append((result,c['currency'],ref_docs));passed_calculations.add(i)
            checks.append({'calculation':i,'python_result':float(result),'arithmetic_verified':True,'semantic_operand_relation':'requires_human_check'})
        except (KeyError,TypeError,ValueError,IndexError,InvalidOperation,ZeroDivisionError) as exc:
            errors.append(f'calculation[{i}]: {exc}')
    for name in ['claims','supported_facts']:
        allowed={case['declaration']['doc_id']} if name=='claims' else {x['doc_id'] for x in case['documents']}
        for i,f in enumerate(obj[name]):
            path=f'{name}[{i}]'
            if f['amount'] is not None and path+'.amount' not in verified_targets:
                refs=[e for e in obj['evidence'] if isinstance(e,dict) and e.get('supports_field') == path+'.amount' and check_ref(e,docs)]
                refs=[e for e in refs if e['doc_id'] in allowed and not INJECTION.search(e['quote'])]
                values=set().union(*(numbers(e['quote']) for e in refs)) if refs else set()
                explicit_zero=f['amount']==0 and any(re.search(r'未支付任何|未收到|no (?:payment|money)|nothing (?:paid|received)',e['quote'],re.I) for e in refs)
                if Decimal(str(f['amount'])) not in values and not explicit_zero:errors.append(f'{path}.amount lacks numeric evidence from correct source')
                else:valid_amount_paths.add(path+'.amount')
            if path+'.amount' in verified_targets:valid_amount_paths.add(path+'.amount')
            if f['amount_basis'].startswith('salary_net_total') and not re.search(r':\d{4}(?:-\d{4})?$',f['amount_basis']):
                errors.append(f'{path}: salary amount_basis must preserve its period')
                valid_amount_paths.discard(path+'.amount')
            if name=='supported_facts':
                refs=[e for e in obj['evidence'] if isinstance(e,dict) and e.get('supports_field') == path+'.transaction_status' and check_ref(e,docs) and e['doc_id'] in allowed and not INJECTION.search(e['quote'])]
                if not refs:errors.append(f'{path}.transaction_status lacks document evidence')
    # Compare only independently evidenced facts. A mismatch candidate is NOT
    # proof of semantic comparability; label/basis equality cannot provide that.
    comparison_candidates=[]
    for ci,claim in enumerate(obj['claims']):
        cp=f'claims[{ci}].amount'
        if cp not in valid_amount_paths or claim['currency'] is None:continue
        matches=[(j,f) for j,f in enumerate(obj['supported_facts'])
                 if all(f[k]==claim[k] for k in ['source_label','amount_basis','currency'])
                 and f'supported_facts[{j}].amount' in valid_amount_paths]
        if case['documents'] and not matches:
            errors.append(f'{cp}: no evidenced comparable personal amount; review required')
        for j,f in matches:
            delta=Decimal(str(claim['amount']))-Decimal(str(f['amount']))
            if abs(delta)>Decimal('0.01'):
                comparison_candidates.append({'claim_index':ci,'fact_index':j,
                    'numeric_difference':float(delta),'currency':claim['currency'],
                    'semantic_comparability':'not_proven_by_field_equality'})
                # Keep financial issue codes model-attributed. Never turn an
                # unverified period/basis assignment into a confirmed mismatch.
                obj['review_action']='human_review'
    support_text='\n'.join(l['text'] for d in case['documents'] for l in d['lines'])
    allocation_context=(re.search(r'\d(?:[\d.]*)(?:%|％)',support_text) and
        re.search(r'全部股权估值|公司整体估值|整体交易对价|company valuation|equity valuation|total (?:sale|transaction) consideration',support_text,re.I))
    if allocation_context and obj['source_type'] in {'equity_sale','mixed'}:
        if not any(c['purpose']=='equity_allocation' and i in passed_calculations
                   and any(f['amount'] is not None and f['currency']==c['currency']
                           and f['amount_basis'] in {'equity_paid_proceeds','equity_agreed_proceeds'}
                           and abs(Decimal(str(f['amount']))-Decimal(str(c['result'])))<=Decimal('0.01')
                           for f in obj['supported_facts'])
                   for i,c in enumerate(obj['calculations'])):
            errors.append('Equity allocation context requires an evidenced allocation calculation')
    if 'conflicting_documents' in obj['issue_codes'] and len(case['documents'])<2:
        errors.append('conflicting_documents requires at least two supporting documents')
    usable=any(l['text'].strip() for doc in [case['declaration'],*case['documents']] for l in doc['lines'])
    if not usable:
        if obj['source_type']!='unknown' or any(obj[n] for n in ['claims','supported_facts','evidence','calculations']):errors.append('Empty input has fabricated facts')
        obj['review_action']='insufficient_input'
        if 'insufficient_information' not in obj['issue_codes']:obj['issue_codes'].append('insufficient_information')
    elif not case['documents']:
        if obj['supported_facts']:errors.append('No documents but supported facts present')
        obj['review_action']='human_review'
        if 'missing_evidence' not in obj['issue_codes']:obj['issue_codes'].append('missing_evidence')
    injection_evidence=[]
    for doc_id,lines in docs.items():
        for line_id,text in lines.items():
            if INJECTION.search(text):
                injection_evidence.append({'supports_field':'issue_codes','doc_id':doc_id,'line_id':line_id,'quote':text})
    if injection_evidence:
        if 'prompt_injection' not in obj['issue_codes']:obj['issue_codes'].append('prompt_injection')
        for e in injection_evidence:
            if e not in obj['evidence']:obj['evidence'].append(e)
    if usable and (errors or obj['issue_codes'] or obj['missing_information']):obj['review_action']='human_review'
    return obj,{'schema_ok':schema_ok,'mechanical_checks_ok':not errors,'errors':errors,'arithmetic_checks':checks,'normalization_events':normalization_events,'comparison_candidates':comparison_candidates,'injection_rule_evidence':injection_evidence,'forced_review':bool(errors) or obj['review_action']!=initial_action,'amount_matching_scope':'Only evidenced matching label/basis/currency pairs are numerical candidates. Differences trigger review but do not create confirmed mismatch labels. Period, ownership and semantic support require review.','limitations':'Verbatim quote presence and arithmetic do not prove semantic support. Human checks remain necessary; injection detector covers only listed patterns.'}

def call_model(case,key,model):
    """One nonstreaming request; preserve usage and errors, no silent retries."""
    system=(ROOT/'prompts/system.txt').read_text(encoding='utf-8')
    payload={'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps({'declaration':case['declaration'],'documents':case['documents']},ensure_ascii=False)}],'temperature':0,'max_tokens':3500,'response_format':{'type':'json_schema','json_schema':{'name':'sow_prescreen','strict':True,'schema':REQUEST_SCHEMA}},'provider':{'require_parameters':True}}
    req=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    t=time.perf_counter()
    try:
        with urllib.request.urlopen(req,timeout=120) as response:obj=json.load(response)
    except urllib.error.HTTPError as e:
        # Do not print response bodies or credentials.
        raise RuntimeError(f'OpenRouter HTTP {e.code}; check account/model/credits; HTTP 400/404 may mean no compatible structured-output provider. No format fallback was used') from None
    elapsed=time.perf_counter()-t
    return obj,elapsed,hashlib.sha256(system.encode()).hexdigest()

def run(input_path,output_dir,case_ids=None,model='openai/gpt-4o-mini'):
    """One request per input/configuration, with a persistent local request ledger.
    No retries, fallback model, judge call or automatic repair call. Errors stop
    new calls. Cache reuse is marked and never presented as a fresh experiment.
    """
    cases=load_cases(input_path)
    if case_ids:
        wanted=set(case_ids);cases=[c for c in cases if c['case_id'] in wanted]
        if {c['case_id'] for c in cases}!=wanted:raise ValueError('Unknown case ID')
    if not cases or len(cases)>10:raise ValueError('Select between 1 and 10 cases per run')
    key=(os.environ.get('OPENROUTER_API_KEY') or os.environ.get('MY_PRIVATE_OPENROUTER_KEY') or '').strip()
    if not key:raise RuntimeError('OPENROUTER_API_KEY is not set')
    directory=Path(output_dir);directory.mkdir(parents=True,exist_ok=True)
    ledger=ROOT/'request_cache';ledger.mkdir(exist_ok=True)
    code=Path(__file__).read_text(encoding='utf-8')
    prompt=(ROOT/'prompts/system.txt').read_text(encoding='utf-8')
    run_id=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');dest=directory/run_id;dest.mkdir()
    (dest/'system_prompt.txt').write_text(prompt,encoding='utf-8')
    (dest/'pipeline_snapshot.py').write_text(code,encoding='utf-8')
    (dest/'inputs_used.json').write_text(json.dumps({'inputs':cases},ensure_ascii=False,indent=2),encoding='utf-8')
    records=[];new_calls=0
    for case in cases:
        fingerprint=hashlib.sha256(json.dumps({'case':case,'model':model,'prompt':prompt,
            'code':code},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        cached=ledger/(fingerprint+'.json');lock=ledger/(fingerprint+'.attempted')
        rec={'case_id':case['case_id'],'requested_model':model,'pipeline_version':PIPELINE_VERSION,
             'response_format':'json_schema_strict','run_id':run_id,'request_fingerprint':fingerprint,
             'input_sha256':hashlib.sha256(json.dumps(case,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
        if cached.exists():
            original=json.loads(cached.read_text(encoding='utf-8'))
            rec={**original,'run_id':run_id,'reused_from_run_id':original['run_id'],'cache_reused':True,'new_api_call':False}
        elif lock.exists():
            rec.update(status='error',error='An earlier request started but has no saved result. Automatic repeat blocked to prevent double charging.',cache_reused=False,new_api_call=False,latency_seconds=0)
        else:
            # O_EXCL prevents concurrent/repeated notebook cells sending twice.
            fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w') as f:f.write(run_id)
            rec.update(cache_reused=False,new_api_call=True);new_calls+=1;t=time.perf_counter()
            try:
                response,elapsed,prompt_hash=call_model(case,key,model)
                rec.update(latency_seconds=elapsed,prompt_sha256=prompt_hash,provider_response=response,
                           usage=response.get('usage') or {},actual_model=response.get('model'))
                choice=response['choices'][0];rec['finish_reason']=choice.get('finish_reason')
                raw=choice['message'].get('content','');rec['raw_output']=raw
                if choice.get('finish_reason')=='length':raise ValueError('Output truncated; no automatic retry')
                if choice['message'].get('refusal'):raise ValueError('Provider refusal; no automatic retry')
                wire=json.loads(raw);rec['raw_model_object']=wire
                candidate=attach_source_lines(wire,case);rec['candidate_output']=candidate
                rec['evidence_binding']='Source text and field paths attached deterministically; raw_model_object unchanged'
                validated,audit=validate_output(candidate,case);rec.update(validated_output=validated,validation=audit)
                rec['status']='ok' if audit.get('mechanical_checks_ok') else 'validation_failed'
            except Exception as exc:
                rec['status']='error';rec['error']=str(exc).replace(key,'[REDACTED]')
                rec.setdefault('latency_seconds',time.perf_counter()-t)
            cached.write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
        (dest/(case['case_id']+'.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
        records.append(rec)
        print(case['case_id'],rec['status'],'复用历史结果' if rec.get('cache_reused') else '本轮结果',
              'action:',(rec.get('validated_output') or {}).get('review_action','unavailable'))
        if rec['status']=='error':
            print('停止后续请求，避免继续扣费。请下载当前结果。');break
    costs=[r.get('usage',{}).get('cost') for r in records if numeric(r.get('usage',{}).get('cost'))]
    new_costs=[r.get('usage',{}).get('cost') for r in records if r.get('new_api_call') and numeric(r.get('usage',{}).get('cost'))]
    summary={'run_id':run_id,'requested_cases':len(cases),'cases':len(records),'new_api_calls':new_calls,
        'reused_cases':sum(bool(r.get('cache_reused')) for r in records),
        'successful_mechanical_checks':sum(r['status']=='ok' for r in records),
        'task_accuracy':'not_scored; mechanical checks are not task accuracy',
        'total_reported_cost_usd':sum(costs) if costs else None,
        'new_reported_cost_usd':sum(new_costs) if new_costs else (0 if new_calls==0 else None),
        'cost_missing_cases':len(records)-len(costs),
        'cost_note':'Total includes original costs for reused outputs; new cost counts only this run. Do not add totals across overlapping runs.',
        'total_reported_prompt_tokens':sum(r.get('usage',{}).get('prompt_tokens') or 0 for r in records),
        'total_reported_completion_tokens':sum(r.get('usage',{}).get('completion_tokens') or 0 for r in records),
        'mean_latency_seconds':sum(r['latency_seconds'] for r in records)/len(records),
        'results_dir':str(dest)}
    (dest/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2));return dest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',default=str(ROOT/'data/dev_inputs.json'));p.add_argument('--output',default=str(ROOT/'results'));p.add_argument('--case',action='append');p.add_argument('--model',default='openai/gpt-4o-mini');a=p.parse_args();run(a.inputs,a.output,a.case,a.model)
