"""Generate the declared conformance cases, evaluate baselines, and test traces."""
from copy import deepcopy
from pathlib import Path
import csv,json,hashlib
from admission import ACCEPT,REJECT,DEFER,base_case,check,ReservationGate,digest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
cases=[]
def add(name,group,expected,mutator=lambda c,w:None):
    c,w=base_case(); mutator(c,w)
    cases.append(dict(name=name,group=group,expected=expected,context=c,world=w))
def setpath(obj,path,value):
    for key in path[:-1]: obj=obj[key]
    obj[path[-1]]=value
def change(path,value): return lambda c,w:setpath(c,path,value)

add('valid-different-decimals','valid',ACCEPT)
add('valid-same-decimals','valid',ACCEPT,lambda c,w:c['target'].update(raw_amount=1000000,decimals=6))
def property_case(c,w):
    for side in ('source','target'):
        c[side].update(claim_class='property-certificate',raw_amount=1,decimals=0,
                       rights=['hold-certificate','transfer'],controls=['freeze','revoke','correction'])
    c['mapping'].update(source_class='property-certificate',target_class='property-certificate',
                        required_rights=['hold-certificate','transfer'],allowed_rights=['hold-certificate','transfer'],
                        required_controls=['freeze','revoke','correction'])
add('valid-property-certificate','valid',ACCEPT,property_case)
add('valid-exact-fraction','valid',ACCEPT,lambda c,w:(c['source'].update(raw_amount=1234000),c['target'].update(raw_amount=1234000000000000000)))
add('negative-quantity','syntax',REJECT,change(['target','raw_amount'],-1))
add('noninteger-quantity','syntax',REJECT,change(['target','raw_amount'],1.5))
add('unsupported-decimals','syntax',REJECT,change(['target','decimals'],37))
add('missing-context','syntax',REJECT,change(['context_id'],''))
add('wrong-source-locator','semantic',REJECT,change(['source','contract'],'other-vault'))
add('wrong-target-locator','semantic',REJECT,change(['target','asset_id'],'other-asset'))
add('same-symbol-different-claim','semantic',REJECT,change(['target','claim_id'],'issuer-Y:claim-7'))
add('both-claims-substituted','semantic',REJECT,lambda c,w:(c['source'].update(claim_id='forged-claim'),c['target'].update(claim_id='forged-claim')))
add('issuer-substitution','semantic',REJECT,change(['target','issuer'],'issuer-Y'))
add('certificate-promoted-to-title','semantic',REJECT,change(['target','claim_class'],'legal-title'))
add('quantity-rounding','semantic',REJECT,change(['target','raw_amount'],999999999999999999))
add('redemption-lost','semantic',REJECT,change(['target','rights'],['transfer']))
add('new-right-added','semantic',REJECT,change(['target','rights'],['redeem','transfer','fractionalize']))
add('freeze-capability-lost','semantic',REJECT,change(['target','controls'],['revoke']))
add('revocation-capability-lost','semantic',REJECT,change(['target','controls'],['freeze']))
add('expiry-extended','semantic',REJECT,change(['target','expires_at'],2000))
add('migration-changed-to-wrapping','semantic',REJECT,change(['operation'],'wrapping'))
add('mapping-not-approved','institutional',REJECT,change(['mapping','approved'],False))
add('mapping-approval-unavailable','institutional',DEFER,change(['mapping','approved'],None))
add('mapping-revoked','institutional',REJECT,lambda c,w:w['revoked_mappings'].append('mapping-1'))
add('policy-version-changed','temporal',DEFER,lambda c,w:w.update(policy_version=2))
add('issuer-authorization-denied','institutional',REJECT,change(['approvals','issuer_authority'],False))
add('recipient-status-unknown','institutional',DEFER,change(['approvals','recipient_eligibility'],None))
add('legal-recognition-pending','institutional',DEFER,change(['approvals','legal_recognition'],None))
add('legal-recognition-denied','institutional',REJECT,change(['approvals','legal_recognition'],False))
add('delegation-out-of-scope','institutional',REJECT,change(['approvals','delegation_scope'],False))
add('authority-revoked','institutional',REJECT,lambda c,w:w['revoked_authorities'].append('authority-1'))
add('approval-expired','temporal',DEFER,change(['approval_valid_until'],15))
add('underlying-asset-expired','temporal',REJECT,lambda c,w:(c['source'].update(expires_at=15),c['target'].update(expires_at=15)))
add('fabricated-root-assertion','evidence',REJECT,change(['evidence','authenticated'],False))
add('source-not-finalized','evidence',DEFER,change(['evidence','finalized'],False))
add('evidence-too-old','temporal',DEFER,change(['evidence','observed_at'],-40))
add('observation-in-future','temporal',REJECT,change(['evidence','observed_at'],30))
add('source-frozen','institutional',REJECT,change(['source_frozen'],True))
add('source-status-unavailable','institutional',DEFER,change(['source_frozen'],None))
add('jurisdiction-approval-pending','institutional',DEFER,change(['jurisdiction_compatible'],None))
add('jurisdiction-approval-denied','institutional',REJECT,change(['jurisdiction_compatible'],False))
add('known-loss-and-pending-approval','combined',REJECT,lambda c,w:(c['target'].update(rights=['transfer']),c['approvals'].update(legal_recognition=None)))
add('revoked-mapping-and-stale-policy','combined',REJECT,lambda c,w:(w['revoked_mappings'].append('mapping-1'),w.update(policy_version=2)))

results=[]; summary=[]
for level in ('syntax','semantic','full'):
    rows=[]
    for item in cases:
        d=check(item['context'],item['world'],level)
        rows.append(dict(baseline=level,name=item['name'],group=item['group'],expected=item['expected'],
                         actual=d.outcome,reasons=';'.join(d.reasons)))
    results+=rows
    summary.append(dict(baseline=level,cases=len(rows),matches=sum(x['actual']==x['expected'] for x in rows),
                        unsupported_accepts=sum(x['actual']==ACCEPT and x['expected']!=ACCEPT for x in rows),
                        valid_not_accepted=sum(x['actual']!=ACCEPT and x['expected']==ACCEPT for x in rows)))
assert all(x['actual']==x['expected'] for x in results if x['baseline']=='full')

# Stateful traces exercise the admission-to-commit boundary separately.
trace=[]
def record(name,actual,expected):
    trace.append(dict(name=name,actual=actual,expected=expected)); assert actual==expected,(name,actual,expected)
c,w=base_case(); g=ReservationGate()
record('initial-reservation',g.reserve(c,w).outcome,ACCEPT)
other=deepcopy(c); other['context_id']='competing-context'
record('competing-reservation',g.reserve(other,w).outcome,REJECT)
record('commit-existing-reservation',g.commit(c,w).outcome,ACCEPT)
record('duplicate-commit',g.commit(c,w).outcome,REJECT)
record('new-reservation-after-commit',g.reserve(other,w).outcome,REJECT)
c,w=base_case(); g=ReservationGate(); g.reserve(c,w)
changed=deepcopy(c); changed['target']['rights'].append('fractionalize')
record('changed-context-at-commit',g.commit(changed,w).outcome,REJECT)
record('original-context-after-failed-change',g.commit(c,w).outcome,ACCEPT)
c,w=base_case(); g=ReservationGate(); g.reserve(c,w); w['policy_version']=2
record('policy-change-before-commit',g.commit(c,w).outcome,DEFER)
c,w=base_case(); g=ReservationGate(); g.reserve(c,w); w['revoked_authorities'].append('authority-1')
record('authority-revoked-before-commit',g.commit(c,w).outcome,REJECT)
c,w=base_case(); g=ReservationGate(); g.reserve(c,w); w['now']=101
record('approval-expired-before-commit',g.commit(c,w).outcome,DEFER)
c,w=base_case(); g=ReservationGate(); g.reserve(c,w); w['now']=1001
record('asset-expired-before-commit',g.commit(c,w).outcome,REJECT)
c,w=base_case(); g=ReservationGate()
record('commit-without-reservation',g.commit(c,w).outcome,REJECT)

(HERE/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
(HERE/'summary.json').write_text(json.dumps(dict(summary=summary,traces=trace),indent=2)+'\n')
with (HERE/'results.csv').open('w',newline='') as f:
    wr=csv.DictWriter(f,fieldnames=list(results[0])); wr.writeheader(); wr.writerows(results)
tex=[]
for x in summary:
    label={'syntax':'Syntactic','semantic':'Semantic','full':'Full admission'}[x['baseline']]
    tex.append(f"{label} & {x['matches']}/{x['cases']} & {x['unsupported_accepts']} & {x['valid_not_accepted']} \\\\")
(ROOT/'chapter-asset-meaning'/'results-rows.tex').write_text('\\newcommand{\\amResultRows}{%\n'+'\n'.join(tex)+'\n}\n')
(ROOT/'chapter-asset-meaning'/'results-macros.tex').write_text(
    f"\\newcommand{{\\amCaseCount}}{{{len(cases)}}}\n\\newcommand{{\\amTraceCount}}{{{len(trace)}}}\n"+
    f"\\newcommand{{\\amValidCount}}{{{sum(x['expected']==ACCEPT for x in cases)}}}\n"+
    f"\\newcommand{{\\amSyntaxExact}}{{{summary[0]['matches']}}}\n"+
    f"\\newcommand{{\\amSemanticExact}}{{{summary[1]['matches']}}}\n"+
    f"\\newcommand{{\\amSyntaxUnsupported}}{{{summary[0]['unsupported_accepts']}}}\n"+
    f"\\newcommand{{\\amSemanticUnsupported}}{{{summary[1]['unsupported_accepts']}}}\n")
print(json.dumps(dict(summary=summary,trace_checks=len(trace),all_trace_checks_passed=True),indent=2))
