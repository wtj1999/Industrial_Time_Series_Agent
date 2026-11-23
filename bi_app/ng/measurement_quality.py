"""Automatic measurement cleaning within tenant, line and NG/OK cohorts."""

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import NgError

CONTEXT = {"tenant_id", "technics_line_name", "device_name", "shift", "produce_order_code", "technics_step_code"}
FORBIDDEN = {"ng_type", "product_quality", "_group"}
MAD_CONTEXT = ("tenant_id", "technics_line_name")
MAD_GROUP_BY = (*MAD_CONTEXT, "quality_group")
AUDIT_CONTEXT = {"tenant_id", "technics_line_name", "device_name", "produce_order_code"}


def mad_group(identity, cohort):
    return tuple(str(identity.get(k)) if identity.get(k) is not None else '未知' for k in MAD_CONTEXT)+(cohort,)


class RuleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SourceRule(RuleModel):
    id: str = Field(min_length=1)
    when: dict[str, list[str]] = Field(default_factory=dict)
    start: datetime | None = None
    end: datetime | None = None
    action: Literal["convert", "quarantine_unit"] = "convert"
    source_unit: str = ""
    scale: float = Field(default=1, gt=0)
    offset: float = 0
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_scope(self):
        if self.start and self.end and self.start >= self.end:
            raise ValueError("来源时间范围无效")
        if any(k not in CONTEXT for k in self.when) or any(not v for v in self.when.values()):
            raise ValueError("来源条件只能使用生产上下文，不能使用NG/OK标签")
        return self


class InvalidFlag(RuleModel):
    column: str
    values: list[str] = Field(min_length=1)


class FieldRule(RuleModel):
    table: str
    column: str
    confirmed: bool = False
    standard_unit: str | None = None
    physical_min: float | None = None
    physical_max: float | None = None
    raw_sentinels: list[float] = Field(default_factory=list)
    invalid_flags: list[InvalidFlag] = Field(default_factory=list)
    sources: list[SourceRule] = Field(default_factory=list)
    require_source_match: bool = False
    group_by: list[str] = Field(default_factory=lambda: list(MAD_CONTEXT))

    @model_validator(mode="after")
    def valid_bounds(self):
        if self.physical_min is not None and self.physical_max is not None and self.physical_min > self.physical_max:
            raise ValueError("物理范围上下限颠倒")
        if self.sources and not self.standard_unit:
            raise ValueError("来源单位规则必须声明标准单位")
        if any(k not in CONTEXT for k in self.group_by) or any(f.column in FORBIDDEN for f in self.invalid_flags):
            raise ValueError("清洗不能以结果标签作为条件")
        # Keep older files readable, but apply the user-confirmed grouping everywhere.
        self.group_by = list(MAD_CONTEXT)
        if len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError("来源规则ID重复")
        return self


class QualityRules(RuleModel):
    version: str = "1"
    min_records: int = Field(default=50, ge=10)
    modified_z_limit: float = Field(default=5.0, gt=0)
    fields: list[FieldRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_fields(self):
        if len({(f.table,f.column) for f in self.fields}) != len(self.fields):
            raise ValueError("表字段规则重复")
        return self


def safe(value):
    if isinstance(value,int) and not isinstance(value,bool) and abs(value)>9007199254740991:
        return str(value)
    if value is None or isinstance(value,(str,int,bool)):
        return value
    if isinstance(value,float) and math.isfinite(value):
        return value
    return str(value)


def number(value):
    if value is None or isinstance(value,str) and not value.strip():
        return None,"missing"
    if isinstance(value,bool):
        return None,"non_numeric"
    try:
        v=float(value)
        return (v,"valid") if math.isfinite(v) else (None,"non_finite")
    except (ValueError,TypeError,OverflowError):
        return None,"non_numeric"


def multimodal(values):
    """Conservative histogram valley guard; never deletes a minority mode."""
    if min(values) == max(values):
        return False
    if not math.isfinite(max(values)-min(values)):
        return True
    import numpy as np
    counts,_=np.histogram(values,bins=min(20,max(5,int(math.sqrt(len(values))))))
    peaks=[i for i,c in enumerate(counts) if c >= max(5,len(values)*.1)
           and (i==0 or c>=counts[i-1]) and (i==len(counts)-1 or c>=counts[i+1])]
    return any(b-a>=2 and min(counts[a+1:b]) < .25*min(counts[a],counts[b]) for a in peaks for b in peaks if b>a)


class MeasurementQuality:
    def __init__(self, rules=None):
        self.rules=rules or QualityRules()
        self.revision=hashlib.sha256(self.rules.model_dump_json().encode()).hexdigest()
        self.config={(f.table,f.column):f for f in self.rules.fields if f.confirmed}
        self.records={}
        self.fields={}
        self.field_records=defaultdict(set)
        self.rule_cache={}
        self.column_cache={}
        self.flags=set()
        self.baselines=[]

    @classmethod
    def load(cls, settings):
        path=Path(settings.catalog_root)/settings.factory_id/'measurement_quality_rules.json'
        if not path.exists():
            return cls()
        try:
            return cls(QualityRules.model_validate_json(path.read_text(encoding='utf-8')))
        except (OSError,ValueError) as exc:
            raise NgError("测量清洗规则无效，请检查measurement_quality_rules.json",503) from exc

    def rule(self, field):
        if field['id'] not in self.rule_cache:
            self.rule_cache[field['id']]=self.config.get((field['process']['table'],field['column'])) or FieldRule(table=field['process']['table'],column=field['column'])
        return self.rule_cache[field['id']]

    def columns(self, field):
        if field['id'] in self.column_cache:
            return self.column_cache[field['id']]
        rule=self.rule(field)
        extra={f.column for f in rule.invalid_flags} | {k for s in rule.sources for k in s.when}
        if not extra.issubset(set(field['process']['columns'])):
            raise NgError(f"清洗规则引用了字典中未核验的来源/有效性列：{field['name']}，请先核验DDL字典",503)
        self.column_cache[field['id']]=extra | (AUDIT_CONTEXT & set(field['process']['columns']))
        return self.column_cache[field['id']]

    def apply(self, field, row, product_key, group):
        self.fields[field['id']]=field
        rule=self.rule(field)
        raw=row.get(field['column'])
        clock=field['process']['sort_time_field']
        identity={k:safe(row.get(k)) for k in {'tenant_id','product_code','produce_id',clock,*self.columns(field)}}
        fingerprint=json.dumps([field['id'],group,identity,safe(raw)],sort_keys=True,ensure_ascii=False)
        ref=hashlib.sha256(fingerprint.encode()).hexdigest()
        if ref not in self.records:
            value,status=number(raw)
            entry={'record_ref':ref,'field_id':field['id'],'cohort':group,'identity':identity,'original_value':safe(raw),'value':value,
                   'status':status,'reason':{'missing':'缺失测量','non_numeric':'无法解析为数值','non_finite':'非有限数值','valid':'有效数值'}[status],'converted':False,'source_rule':None,'rule_version':self.rules.version,
                   'rule_revision':self.revision,'unit':rule.standard_unit,'uses':defaultdict(set)}
            if status=='valid':
                if value in rule.raw_sentinels:
                    entry.update(value=None,status='sentinel',reason='字段已确认的原始占位值')
                elif any(str(row.get(f.column)) in f.values for f in rule.invalid_flags):
                    entry.update(value=None,status='invalid_flag',reason='已确认的测量无效标志')
                else:
                    timestamp=row.get(clock)
                    try:
                        timestamp=timestamp if isinstance(timestamp,datetime) else datetime.fromisoformat(str(timestamp))
                    except (ValueError,TypeError):
                        timestamp=None
                    matches=[s for s in rule.sources if all(str(row.get(k)) in v for k,v in s.when.items())
                             and (s.start is None or timestamp is not None and timestamp>=s.start)
                             and (s.end is None or timestamp is not None and timestamp<s.end)]
                    if len(matches)>1 or rule.require_source_match and not matches:
                        entry.update(value=None,status='unit_unconfirmed',reason='来源单位未确认或规则重叠，隔离数值')
                    elif matches:
                        source=matches[0]
                        entry['source_rule']=source.id
                        if source.action=='quarantine_unit':
                            entry.update(value=None,status='unit_unconfirmed',reason=source.reason)
                        else:
                            normalized=value*source.scale+source.offset
                            entry.update(value=normalized,converted=source.scale!=1 or source.offset!=0,reason=source.reason)
                            if not math.isfinite(normalized):
                                entry.update(value=None,status='conversion_overflow',reason='单位换算结果非有限值')
                    if entry['value'] is not None and ((rule.physical_min is not None and entry['value']<rule.physical_min)
                                                       or (rule.physical_max is not None and entry['value']>rule.physical_max)):
                        entry.update(value=None,status='outside_physical_range',reason='超出已确认物理范围或仪器量程')
            self.records[ref]=entry
            self.field_records[field['id']].add(ref)
        self.records[ref]['uses'][group].add(tuple(product_key))
        return ref,self.records[ref]['value']

    def detect(self, field_id, allowed=None):
        buckets=defaultdict(list)
        for ref in sorted(self.field_records[field_id]):
            row=self.records[ref]
            if row['value'] is not None and (allowed is None or ref in allowed):
                key=mad_group(row['identity'],row['cohort'])
                buckets[key].append((ref,row['value']))
        flagged=set()
        baselines=[]
        for group,rows in buckets.items():
            values=[v for _,v in rows]
            baseline={'field_id':field_id,'group':list(group),'records':len(rows),'median':None,'mad':None,'lower':None,'upper':None,'status':'insufficient'}
            if len(rows)>=self.rules.min_records:
                center=median(values)
                mad=median(abs(v-center) for v in values)
                baseline.update(median=center if math.isfinite(center) else None,mad=mad if math.isfinite(mad) else None,status='applied')
                if not math.isfinite(center) or not math.isfinite(mad):
                    baseline['status']='unstable_scale'
                elif mad==0:
                    baseline['status']='zero_mad'
                elif multimodal(values):
                    baseline['status']='suspected_multimodal'
                else:
                    half=self.rules.modified_z_limit*mad/.6745
                    baseline.update(lower=center-half,upper=center+half)
                    flagged.update(ref for ref,v in rows if abs(.6745*((v-center)/mad))>self.rules.modified_z_limit)
            baselines.append(baseline)
        return flagged,baselines

    def finalize(self):
        for field_id in self.fields:
            flags,baselines=self.detect(field_id)
            self.flags.update(flags)
            self.baselines.extend(baselines)

    def value(self, ref, exclude=True):
        return None if exclude and ref in self.flags else self.records[ref]['value']

    def ledger(self, exclude=True):
        fields=[]
        for field_id,field in self.fields.items():
            rows=[self.records[ref] for ref in self.field_records[field_id]]
            affected={g:set() for g in ('NG','OK')}
            for r in rows:
                if r['value'] is None or exclude and r['record_ref'] in self.flags:
                    for g in affected:
                        affected[g].update(r['uses'].get(g,set()))
            original_valid=sum(number(r['original_value'])[1]=='valid' for r in rows)
            invalid=sum(r['status'] not in {'valid','missing'} for r in rows)
            flagged=sum(r['record_ref'] in self.flags for r in rows)
            fields.append({'field_id':field_id,'name':field['name'],'process_name':field['process']['name'],
                           'standard_unit':self.rule(field).standard_unit,'configured':(field['process']['table'],field['column']) in self.config,
                           'records':len(rows),'original_valid':original_valid,'converted':sum(r['converted'] for r in rows),
                           'missing':sum(r['status']=='missing' for r in rows),'removed':invalid,'flagged':flagged,
                           'algorithm_removed':invalid+(flagged if exclude else 0),
                           'limits':[b for b in self.baselines if b['field_id']==field_id],
                           'statistically_excluded':flagged if exclude else 0,
                           'remaining':sum(r['value'] is not None for r in rows)-(flagged if exclude else 0),
                           'reasons':dict(Counter(r['status'] for r in rows if r['status']!='valid')),
                           'affected_products':{g:len(keys) for g,keys in affected.items()}})
        return {'version':self.rules.version,'revision':self.revision,'exclude_statistical':exclude,'policy':'automatic_by_tenant_line_label','fields':fields,'group_by':list(MAD_GROUP_BY),
                'min_records':self.rules.min_records,'modified_z_limit':self.rules.modified_z_limit,'baselines':self.baselines,
                'note':'每个工序、字段内按租户、产线及NG/OK分别计算MAD并自动剔除。只保留当前NG及确认OK。原始记录按组内源记录去重，共享记录分别进入NG/OK组时各计一次；不删除产品的NG/OK标签。'}

    def audit(self):
        return [{k:v for k,v in r.items() if k!='uses'} | {'statistical_suspect':ref in self.flags,
                 'normalized_value':r['value'],'value':self.value(ref),
                 'status':'mad_outlier' if ref in self.flags else r['status'],
                 'statistical_reason':'超出本组MAD上下限，已剔除此字段值' if ref in self.flags else None,
                 'affected_products':{g:len(keys) for g,keys in r['uses'].items()}}
                for ref,r in self.records.items() if r['status']!='valid' or r['converted'] or ref in self.flags]

    def model_preprocessor(self, observations_by_field):
        """Train-only thresholds; holdout cleaning never consults validation labels."""
        def preprocess(products, inputs, train, validation):
            from .root_cause import collapse_observations
            # A target product is a row, even when its upstream codes also occur in later sets.
            training_keys={products[i]['_key'] for i in train}
            result=[]
            all_flags=set()
            excluded_associations=0
            for data in inputs:
                field=data['field']
                observations=observations_by_field[field['id']]
                allowed={ref for row,ref in observations if row[1] in training_keys}
                _,baselines=self.detect(field['id'],allowed)
                fitted={tuple(b['group']):b for b in baselines if b['status']=='applied'}
                flagged=set()
                for row,ref in observations:
                    record=self.records[ref]
                    if row[1] in training_keys:
                        candidates=[fitted.get(mad_group(record['identity'],record['cohort']))]
                    else:
                        # A future product's label is unavailable: remove only outside BOTH learned ranges.
                        candidates=[fitted.get(mad_group(record['identity'],g)) for g in ('NG','OK')]
                    if all(candidates) and all(abs(.6745*((row[0]-b['median'])/b['mad']))>self.rules.modified_z_limit for b in candidates):
                        flagged.add((row[1],ref))
                all_flags.update(ref for key,ref in flagged)
                excluded_associations+=len(flagged)
                result.append(collapse_observations(field,[row for row,ref in observations if (row[1],ref) not in flagged]))
            return result,{'method':'training_cohort_MAD_holdout_label_blind_union','fit_products':len(training_keys),'flagged_records':len(all_flags),'flagged_associations':excluded_associations}
        return preprocess
