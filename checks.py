"""Free, network-blocked checks for evaluation tooling; synthetic fixtures only."""
import copy,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
import baseline,evaluate

def fixture():
    case={'case_id':'CHECK','declaration':{'doc_id':'D','lines':[{'line_id':'L1','text':'I received a gift of USD 120.'}]},
          'documents':[{'doc_id':'S','lines':[{'line_id':'L1','text':'Gift payment of USD 120 credited.'}]}]}
    return case

class Checks(unittest.TestCase):
    def test_simple_gift(self):
        r=baseline.predict(fixture());self.assertEqual(r['validated_output']['review_action'],'no_issue_detected')
        self.assertEqual(r['usage']['cost'],0);self.assertEqual(r['usage']['total_tokens'],0)
    def test_currency_adjacent_to_chinese(self):
        c=fixture();c['declaration']['lines'][0]['text']='本人收到赠与USD 120，已到账。'
        r=baseline.predict(c)
        self.assertEqual(r['validated_output']['claims'][0]['amount'],120)
    def test_case_id_has_no_effect(self):
        c=fixture();a=baseline.predict(c)['validated_output'];c['case_id']='DIFFERENT'
        self.assertEqual(a,baseline.predict(c)['validated_output'])
    def test_missing_documents(self):
        c=fixture();c['documents']=[]
        self.assertIn('missing_evidence',baseline.predict(c)['validated_output']['issue_codes'])
    def test_amount_difference(self):
        c=fixture();c['documents'][0]['lines'][0]['text']='Gift USD 90 credited.'
        self.assertIn('amount_mismatch',baseline.predict(c)['validated_output']['issue_codes'])
    def test_reference_integrity(self):
        c=fixture();o=baseline.predict(c)['validated_output']
        self.assertTrue(evaluate.evidence_audit(o,c)['reference_integrity_ok'])
        o['evidence'][0]['doc_id']='S'
        self.assertFalse(evaluate.evidence_audit(o,c)['reference_integrity_ok'])
    def test_manual_score_required(self):
        c=fixture();r=baseline.predict(c)
        truth={'expected':copy.deepcopy(r['validated_output']),
               'scoring':{'required_issue_codes':[],'allowed_extra_issue_codes':[],'must_match':{'expected.claims[0].amount':120}}}
        row=evaluate.assess(c,truth,r,'baseline','dev',{})
        self.assertEqual(row['full_task_manual'],'PENDING')
        self.assertIsNone(evaluate.summarize([row])['full_task_accuracy'])
    def test_no_array_order_assumption(self):
        truth={'expected':{'claims':[{'amount':120,'currency':'USD'},{'amount':50,'currency':'SGD'}],'supported_facts':[]},
               'scoring':{'must_match':{'expected.claims[0].amount':120,'expected.claims[1].amount':50}}}
        output={'claims':list(reversed(truth['expected']['claims'])),'supported_facts':[]}
        self.assertTrue(evaluate.required_numeric_coverage(truth,output)['claims'])
    def test_extra_issue_not_allowed(self):
        c=fixture();r=baseline.predict(c);gt={'expected':copy.deepcopy(r['validated_output']),
             'scoring':{'required_issue_codes':[],'allowed_extra_issue_codes':[],'must_match':{}}}
        r['validated_output']['issue_codes']=['amount_mismatch']
        self.assertFalse(evaluate.assess(c,gt,r,'baseline','dev',{})['issue_set_match'])

def run_checks():
    with patch('urllib.request.urlopen',side_effect=AssertionError('No network in free checks')):
        result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    if not result.wasSuccessful():raise RuntimeError('评估工具免费自检失败，请保留错误并停止付费步骤。')
    return result.testsRun
