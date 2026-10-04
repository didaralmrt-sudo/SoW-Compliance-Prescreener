"""Shared evaluation/reporting for baseline and saved AI outputs.
Never imported by inference; labels enter only this offline evaluation module.
No array-index comparison across systems. Numeric coverage is NOT semantic alignment.
Full-case passes require explicit human decisions against the fixed rubric.
"""
from collections import Counter
from decimal import Decimal
import html,json,re
from pathlib import Path

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def num(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool)
def money_key(f):return (Decimal(str(f['amount'])),f.get('currency'))

def required_numeric_coverage(truth,output):
    required=truth['scoring']['must_match'];expected=truth['expected'];result={}
    for kind in ['claims','supported_facts']:
        indices={int(m[1]) for key in required if (m:=re.fullmatch(r'expected\.'+kind+r'\[(\d+)\]\.amount',key))}
        need=Counter(money_key(expected[kind][i]) for i in indices if num(expected[kind][i].get('amount')))
        have=Counter(money_key(f) for f in output.get(kind,[]) if isinstance(f,dict) and num(f.get('amount')))
        result[kind]=all(have[k]>=v for k,v in need.items())
        if 'expected.'+kind in required and required['expected.'+kind]==[]:result[kind]=output.get(kind)==[]
    wanted=[]
    for key,value in required.items():
        m=re.fullmatch(r'expected\.calculations\[(\d+)\]\.result',key)
        if m and num(value):wanted.append((Decimal(str(value)),expected['calculations'][int(m[1])].get('currency')))
    found=[(Decimal(str(c['result'])),c.get('currency')) for c in output.get('calculations',[]) if isinstance(c,dict) and num(c.get('result'))]
    result['required_calculation_values']=all(any(abs(a-b)<=Decimal('0.01') and ca==cb for b,cb in found) for a,ca in wanted) if wanted else None
    return result

def evidence_audit(output,case):
    docs={d['doc_id']:{l['line_id']:l['text'] for l in d['lines']} for d in [case['declaration'],*case['documents']]}
    refs=output.get('evidence',[]);bad=[];good_targets=set();support_ids={d['doc_id'] for d in case['documents']}
    for i,e in enumerate(refs):
        target=e.get('supports_field','');quote=e.get('quote');doc=e.get('doc_id')
        ok=isinstance(quote,str) and bool(quote.strip()) and quote in docs.get(doc,{}).get(e.get('line_id'),'')
        match=re.fullmatch(r'(claims|supported_facts)\[(\d+)\]\.(amount|transaction_status)',target)
        if match:
            kind,idx,field=match.groups();idx=int(idx)
            ok=ok and idx<len(output.get(kind,[])) and (doc==case['declaration']['doc_id'] if kind=='claims' else doc in support_ids)
        elif target!='issue_codes':ok=False
        if ok:good_targets.add(target)
        else:bad.append(i)
    missing=[]
    for kind in ['claims','supported_facts']:
        for i,f in enumerate(output.get(kind,[])):
            target=f'{kind}[{i}].amount'
            derived=any(c.get('target_field')==target and num(c.get('result')) for c in output.get('calculations',[]))
            if f.get('amount') is not None and target not in good_targets and not derived:missing.append(target)
            if kind=='supported_facts' and f'{kind}[{i}].transaction_status' not in good_targets:missing.append(f'{kind}[{i}].transaction_status')
    return {'entries':len(refs),'invalid_entries':bad,'missing_targets':missing,
            'reference_integrity_ok':not bad and not missing,
            'semantic_support':'requires_manual_review; exact quotations alone are insufficient'}

def assess(case,truth,record,system,split,manual):
    output=record.get('validated_output') or {};expected=truth['expected'];scoring=truth['scoring']
    required=set(scoring['required_issue_codes']);allowed=required|set(scoring['allowed_extra_issue_codes'])
    codes=set(output.get('issue_codes',[]));coverage=required_numeric_coverage(truth,output)
    audit=evidence_audit(output,case)
    decision=manual.get(case['case_id'],{});verdict=decision.get('overall','PENDING')
    if verdict not in {'PASS','FAIL','PENDING'}:raise ValueError('Manual overall must be PASS/FAIL/PENDING')
    action_ok=output.get('review_action')==expected['review_action'];type_ok=output.get('source_type')==expected['source_type']
    codes_ok=required<=codes<=allowed
    necessary=[bool(output),action_ok,type_ok,codes_ok,audit['reference_integrity_ok'],coverage['claims'],coverage['supported_facts']]
    if coverage['required_calculation_values'] is not None:necessary.append(coverage['required_calculation_values'])
    if verdict=='PASS' and not all(necessary):raise ValueError(f'{split}/{system}/{case["case_id"]}: manual PASS conflicts with a necessary automatic check; inspect before scoring.')
    if verdict!='PENDING' and not decision.get('reason','').strip():raise ValueError('Give a brief reason for each human decision.')
    return {'split':split,'system':system,'case_id':case['case_id'],'record_status':record.get('status','missing_record'),
        'expected_action':expected['review_action'],'action':output.get('review_action'),
        'action_match':action_ok,'source_type_match':type_ok,'issue_set_match':codes_ok,
        'required_numeric_coverage':coverage,'shared_evidence_audit':audit,
        'full_task_manual':verdict,'manual_reason':decision.get('reason',''),
        'api_cost_usd':record.get('usage',{}).get('cost'),'prompt_tokens':record.get('usage',{}).get('prompt_tokens'),
        'completion_tokens':record.get('usage',{}).get('completion_tokens'),'latency_seconds':record.get('latency_seconds'),
        'cache_reused':record.get('cache_reused',False),'pipeline_version':record.get('pipeline_version'),
        'pipeline_errors':record.get('validation',{}).get('errors',[])}

def summarize(rows):
    n=len(rows);review=[r for r in rows if r['expected_action']=='human_review'];normal=[r for r in rows if r['expected_action']=='no_issue_detected']
    costs=[r['api_cost_usd'] for r in rows if num(r['api_cost_usd'])];lat=[r['latency_seconds'] for r in rows if num(r['latency_seconds'])]
    decided=sum(r['full_task_manual']!='PENDING' for r in rows)
    return {'cases':n,'action_matches':sum(r['action_match'] for r in rows),'source_type_matches':sum(r['source_type_match'] for r in rows),
        'issue_set_matches':sum(r['issue_set_match'] for r in rows),
        'reference_integrity_passes':sum(r['shared_evidence_audit']['reference_integrity_ok'] for r in rows),
        'review_required':len(review),'required_cases_referred':sum(r['action']=='human_review' for r in review),
        'normal_cases':len(normal),'normal_cases_referred':sum(r['action']=='human_review' for r in normal),
        'api_cost_usd':float(sum(Decimal(str(c)) for c in costs)) if costs else None,'cost_missing_cases':n-len(costs),
        'mean_latency_seconds':sum(lat)/len(lat) if lat else None,
        'prompt_tokens':sum(r['prompt_tokens'] or 0 for r in rows),'completion_tokens':sum(r['completion_tokens'] or 0 for r in rows),
        'human_decisions_completed':decided,'full_task_pass_count':sum(r['full_task_manual']=='PASS' for r in rows) if decided==n else None,
        'full_task_accuracy':sum(r['full_task_manual']=='PASS' for r in rows)/n if decided==n and n else None}

def report(inputs_path,labels_path,record_dirs,dest,split,manual_path=None):
    inputs=read(inputs_path)['inputs'];truth={x['case_id']:x for x in read(labels_path)['ground_truth']}
    if set(truth)!={c['case_id'] for c in inputs}:raise ValueError('Input/label IDs differ')
    manual=read(manual_path) if manual_path and Path(manual_path).exists() else {}
    rows=[];details=[]
    for system,record_dir in record_dirs.items():
        input_snapshot=Path(record_dir)/'inputs_used.json'
        if not input_snapshot.exists() or read(input_snapshot)!=read(inputs_path):raise ValueError(f'{system}: exact input snapshot missing/different')
        for case in inputs:
            cid=case['case_id'];file=Path(record_dir)/(cid+'.json')
            rec=read(file) if file.exists() else {'case_id':cid,'status':'missing_record'}
            if rec.get('case_id')!=cid:raise ValueError('Record identity mismatch')
            row=assess(case,truth[cid],rec,system,split,manual.get(split,{}).get(system,{}));rows.append(row)
            details.append((case,truth[cid],rec,row))
    summary={system:summarize([r for r in rows if r['system']==system]) for system in record_dirs}
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    (dest/'metrics.json').write_text(json.dumps({'split':split,'summary':summary,'cases':rows},ensure_ascii=False,indent=2))
    md=f'# {split} 对比结果\n\n行动/类型/问题集合匹配是分项指标，不是总体准确率。整体通过必须按固定规则人工确认。\n\n'
    md+='|系统|案例数|行动匹配|类型匹配|问题集合匹配|应转人工中实际转人工|正常中转人工|API费用USD|人工完成|\n|---|---:|---:|---:|---:|---|---|---|---|\n'
    for system,s in summary.items():
        md+=f"|{system}|{s['cases']}|{s['action_matches']}/{s['cases']}|{s['source_type_matches']}/{s['cases']}|{s['issue_set_matches']}/{s['cases']}|{s['required_cases_referred']}/{s['review_required']}|{s['normal_cases_referred']}/{s['normal_cases']}|{s['api_cost_usd']}|{s['human_decisions_completed']}/{s['cases']}|\n"
    md+='\n费用为每案例保留的独立响应费用，复用开发结果不是本次新支出。baseline API费用为0，未估算CPU成本。无响应案例保留在分母中。引用存在性不代表语义支持；AI引用文本由程序附上，不能称为模型自主引用准确率。\n'
    for system,s in summary.items():md+=f"\n{system} 完整任务通过数："+(f"{s['full_task_pass_count']}/{s['cases']}" if s['full_task_pass_count'] is not None else '待人工核验，不报告准确率。')+'\n'
    (dest/'summary.md').write_text(md)
    escaped=lambda obj:html.escape(json.dumps(obj,ensure_ascii=False,indent=2))
    page=['<!doctype html><meta charset="utf-8"><title>SoW fixed-rubric review</title><style>body{max-width:1100px;margin:30px auto;font:16px system-ui;line-height:1.6}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f6f8;padding:14px}summary{cursor:pointer;font-weight:bold}details{margin:18px 0;border:1px solid #ddd;padding:12px}h2{margin-top:35px}</style>',f'<h1>{html.escape(split)} 人工核验</h1><p>对 baseline 和 AI 使用相同的冻结答案。核对主体、金额口径、期间、币种、收款状态、证据语义、必需计算和全部问题码。顺序和来源名称同义改写可接受；不能只看数字出现或转人工。</p>']
    for case,gt,rec,row in details:
        page.append(f'<details><summary>{html.escape(row["system"])} · {html.escape(case["case_id"])} · {html.escape(row["full_task_manual"])}</summary>')
        for title,obj in [('分项检查（非总分）',row),('输入',case),('固定答案与原评分要求',gt),('系统实际输出',rec.get('validated_output')),('原始输出/错误',{'raw':rec.get('raw_output'),'error':rec.get('error'),'validation':rec.get('validation')})]:page.append(f'<h3>{title}</h3><pre>{escaped(obj)}</pre>')
        page.append('</details>')
    (dest/'manual_review.html').write_text('\n'.join(page))
    return summary
