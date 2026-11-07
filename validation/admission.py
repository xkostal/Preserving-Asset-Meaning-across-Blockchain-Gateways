"""Executable, profile-relative admission model for the accompanying chapter.

Input assertions are deterministic fixtures representing upstream verification
results. This module does not verify signatures, blockchain finality, or law.
Only non-negative integer quantities and JSON-compatible records are supported.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

ACCEPT, REJECT, DEFER = 'ACCEPT', 'REJECT', 'DEFER'

@dataclass(frozen=True)
class Decision:
    outcome: str
    reasons: tuple[str, ...] = ()

def digest(record: dict) -> str:
    """Deterministic encoding for this restricted fixture domain, not full JCS."""
    payload=json.dumps(record,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
    return hashlib.sha256(payload.encode('ascii')).hexdigest()

def resolve(bad: list[str], missing: list[str]) -> Decision:
    if bad: return Decision(REJECT,tuple(sorted(set(bad+missing))))
    if missing: return Decision(DEFER,tuple(sorted(set(missing))))
    return Decision(ACCEPT)

def syntax(c: dict) -> Decision:
    try:
        for side in ('source','target'):
            a=c[side]
            for name in ('network','contract','asset_id','claim_id','issuer','claim_class'):
                if not isinstance(a[name],str) or not a[name]: return Decision(REJECT,('MALFORMED',))
            for name in ('raw_amount','decimals'):
                if type(a[name]) is not int or a[name]<0: return Decision(REJECT,('MALFORMED',))
            if a['decimals']>36: return Decision(REJECT,('UNSUPPORTED_PRECISION',))
            if not isinstance(a['rights'],list) or not isinstance(a['controls'],list):
                return Decision(REJECT,('MALFORMED',))
            if any(not isinstance(x,str) for x in a['rights']+a['controls']):
                return Decision(REJECT,('MALFORMED',))
        if c['operation'] not in ('migration','wrapping','verification'):
            return Decision(REJECT,('MALFORMED_OPERATION',))
        if not isinstance(c['context_id'],str) or not c['context_id']:
            return Decision(REJECT,('MALFORMED_CONTEXT',))
    except (KeyError,TypeError): return Decision(REJECT,('MALFORMED',))
    return Decision(ACCEPT)

def check(c: dict, world: dict, level: str='full') -> Decision:
    d=syntax(c)
    if d.outcome!=ACCEPT or level=='syntax': return d
    if level not in ('semantic','full'): raise ValueError(level)
    s,t,m=c['source'],c['target'],c['mapping']
    bad,missing=[],[]
    for side,a in (('source',s),('target',t)):
        if [a['network'],a['contract'],a['asset_id']] != m[side+'_locator']:
            bad.append('LOCATOR_BINDING')
    if s['claim_id']!=m['claim_id'] or t['claim_id']!=m['claim_id']: bad.append('CLAIM_IDENTITY')
    if s['issuer']!=m['source_issuer'] or t['issuer']!=m['target_issuer']:
        bad.append('ISSUER_BINDING')
    if t['claim_class']!=m['target_class'] or s['claim_class']!=m['source_class']:
        bad.append('CLAIM_CLASS')
    if s['raw_amount']*10**t['decimals'] != t['raw_amount']*10**s['decimals']:
        bad.append('QUANTITY')
    rights=set(t['rights'])
    if not set(m['required_rights']).issubset(rights): bad.append('RIGHT_LOSS')
    if not rights.issubset(m['allowed_rights']): bad.append('RIGHT_EXPANSION')
    if not set(m['required_controls']).issubset(t['controls']): bad.append('CONTROL_LOSS')
    if s['expires_at']!=t['expires_at']: bad.append('ASSET_EXPIRY')
    if c['operation']!=m['operation']: bad.append('OPERATION_CHANGE')
    if level=='semantic': return resolve(bad,missing)
    def obligation(value,reason):
        if value is False: bad.append(reason)
        elif value is not True: missing.append(reason+'_UNKNOWN')
    obligation(m.get('approved'),'MAPPING_APPROVAL')
    if m['id'] in world['revoked_mappings']: bad.append('MAPPING_REVOKED')
    if c['policy_version']!=world['policy_version']: missing.append('POLICY_REFRESH')
    for name in ('issuer_authority','recipient_eligibility','legal_recognition','delegation_scope'):
        obligation(c['approvals'].get(name),name.upper())
    if c['approval_authority'] in world['revoked_authorities']: bad.append('AUTHORITY_REVOKED')
    if world['now']>s['expires_at']: bad.append('ASSET_EXPIRED')
    if world['now']>c['approval_valid_until']: missing.append('APPROVAL_REFRESH')
    e=c['evidence']
    obligation(e.get('authenticated'),'EVIDENCE_AUTHENTICITY')
    if e.get('finalized') is not True: missing.append('FINALITY_PENDING')
    if world['now']-e['observed_at']>e['max_age']: missing.append('EVIDENCE_REFRESH')
    if e['observed_at']>world['now']: bad.append('FUTURE_OBSERVATION')
    if c['source_frozen'] is True: bad.append('SOURCE_FROZEN')
    elif c['source_frozen'] is not False: missing.append('SOURCE_STATUS_UNKNOWN')
    obligation(c.get('jurisdiction_compatible'),'JURISDICTION_APPROVAL')
    return resolve(bad,missing)

class ReservationGate:
    """Single-process illustration of context binding and local reservation.

    No consensus, durable recovery, ledger transaction, or distributed atomicity
    is implemented. A committed reservation is deliberately not reusable.
    """
    def __init__(self): self.reservations={}
    @staticmethod
    def source_key(c):
        a=c['source']; return (a['network'],a['contract'],a['asset_id'])
    def reserve(self,c,world):
        d=check(c,world)
        if d.outcome!=ACCEPT: return d
        key=self.source_key(c)
        if key in self.reservations: return Decision(REJECT,('SOURCE_RESERVED',))
        self.reservations[key]=(digest(c),'RESERVED')
        return d
    def commit(self,c,world):
        key=self.source_key(c)
        item=self.reservations.get(key)
        if item is None: return Decision(REJECT,('NO_RESERVATION',))
        if item[1]!='RESERVED': return Decision(REJECT,('ALREADY_COMMITTED',))
        if item[0]!=digest(c): return Decision(REJECT,('CONTEXT_CHANGED',))
        d=check(c,world)
        if d.outcome==ACCEPT: self.reservations[key]=(item[0],'COMMITTED')
        return d

def base_case():
    s=dict(network='network-A',contract='issuer-vault',asset_id='asset-7',claim_id='issuer-X:claim-7',
           issuer='issuer-X',claim_class='redeemable-unit',raw_amount=1000000,decimals=6,
           rights=['redeem','transfer'],controls=['freeze','revoke'],expires_at=1000)
    t=deepcopy(s); t.update(network='network-B',contract='certificate-ledger',asset_id='representation-7',
                          raw_amount=1000000000000000000,decimals=18)
    m=dict(id='mapping-1',claim_id='issuer-X:claim-7',source_locator=['network-A','issuer-vault','asset-7'],
           target_locator=['network-B','certificate-ledger','representation-7'],
           source_issuer='issuer-X',target_issuer='issuer-X',source_class='redeemable-unit',
           target_class='redeemable-unit',required_rights=['redeem','transfer'],
           allowed_rights=['redeem','transfer'],required_controls=['freeze','revoke'],
           operation='migration',approved=True)
    c=dict(context_id='context-1',source=s,target=t,mapping=m,operation='migration',policy_version=1,
           approvals=dict(issuer_authority=True,recipient_eligibility=True,legal_recognition=True,delegation_scope=True),
           approval_authority='authority-1',approval_valid_until=100,
           evidence=dict(authenticated=True,finalized=True,observed_at=10,max_age=50),
           source_frozen=False,jurisdiction_compatible=True)
    w=dict(now=20,policy_version=1,revoked_mappings=[],revoked_authorities=[])
    return c,w
