#!/usr/bin/env python3
"""FC-wise shipment plan for AFRIYANA INDIA (Amazon.in) - 05 Oct 2026 run.

Inputs (all in this folder, produced by the browser pulls):
  r1_sales.tsv              ASIN x location units sold, 19 Sep - 3 Oct 2026
  r1_stock_scope.tsv        ASIN x location SELLABLE ending balance, 3 Oct 2026
  r1_fc_total_stock.tsv     location -> total SELLABLE (all ASINs)
  r1_products.tsv           ASIN -> MSKU, short product name (brand + product + size)
  r2_fc_state.tsv           plannable FC x shipping state units (non-VTNF)
  r2_nonplan_state.tsv      POOLED / MICRO state totals + per-ASIN VTNF state split
  r2_msku_asin.tsv          MSKU -> ASIN for the window
  r3_shipment_detail.tsv    open inbound shipments
  r3_asin_fc_outstanding.tsv  ASIN x destination outstanding inbound
  r3_extra_products.tsv     names for inbound-only (out-of-scope) ASINs
"""
import os
import csv, json, math
from collections import defaultdict

D = os.environ.get('AFRIYANA_DIR', os.path.dirname(os.path.abspath(__file__))) + '/'

# ---- per-run settings: update these each week ----
RUN_DATE = '2026-10-05'                      # date the plan is built
WINDOW = ['2026-09-19', '2026-10-03']        # first / last settled day used

WINDOW_DAYS = 15
COVER_DAYS = 45
LINE_MIN = 2
TARGET_THRESHOLD = 6

CAP = {
 'AMD2': (16152, 15962), 'ATX1': (750, 595), 'BLR7': (750, 296), 'BLR8': (1458, 1011),
 'BOM5': (750, 428), 'BOM7': (750, 470), 'CCX1': (750, 271), 'CJB1': (2618, 2267),
 'DED4': (750, 123), 'DEL4': (750, 291), 'DEL5': (750, 498), 'DEX3': (750, 593),
 'GAX1': (3897, 3687), 'HYD3': (873, 545), 'HYD8': (763, 606), 'JPX2': (1225, 1130),
 'LDX1': (750, 457), 'LKO1': (7246, 7063), 'MAA4': (16880, 16523), 'NAX1': (750, 565),
 'PNQ2': (750, 691), 'PNQ3': (750, 571),
 'DED3': (5000, 4919), 'DED5': (5000, 2614),
}
IXD = ['DED3', 'DED5']

STATE_FIX = {
 'AS': 'ASSAM', 'CHATTISGARH': 'CHHATTISGARH', 'DL': 'DELHI', 'NEW DELHI': 'DELHI',
 'GOA INDIA': 'GOA', 'HR': 'HARYANA', 'JK': 'JAMMU & KASHMIR', 'PB': 'PUNJAB',
 'RJ': 'RAJASTHAN', 'RAJSTHAN': 'RAJASTHAN', 'TG': 'TELANGANA', 'TN': 'TAMIL NADU',
 'TAMILNADU': 'TAMIL NADU', 'UP': 'UTTAR PRADESH', 'UTTAR PARDESH': 'UTTAR PRADESH',
 'WB': 'WEST BENGAL', 'WESTBENGAL': 'WEST BENGAL', 'KA': 'KARNATAKA', 'AP': 'ANDHRA PRADESH',
 'BR': 'BIHAR', 'MH': 'MAHARASHTRA', 'GJ': 'GUJARAT', 'CH': 'CHANDIGARH', 'JH': 'JHARKHAND',
 'MP': 'MADHYA PRADESH', 'NORTH GOA': 'GOA',
 'DADRA & NAGAR HAVELI': 'DADRA AND NAGAR HAVELI AND DAMAN AND DIU',
 'DAMAN & DIU': 'DADRA AND NAGAR HAVELI AND DAMAN AND DIU',
}
def norm_state(s):
    s = s.strip().upper()
    return STATE_FIX.get(s, s)


def rd(name):
    with open(D + name) as f:
        return list(csv.DictReader(f, delimiter='\t'))

# ---------------------------------------------------------------- load
sales_rows = rd('r1_sales.tsv')
stock_rows = rd('r1_stock_scope.tsv')
fctot_rows = rd('r1_fc_total_stock.tsv')
prod_rows = rd('r1_products.tsv')
fcstate_rows = rd('r2_fc_state.tsv')
np_rows = rd('r2_nonplan_state.tsv')
msku_rows = rd('r2_msku_asin.tsv')
ship_rows = rd('r3_shipment_detail.tsv')
inb_rows = rd('r3_asin_fc_outstanding.tsv')
extra_rows = rd('r3_extra_products.tsv')

PRODUCT = {r['ASIN']: r['PRODUCT'] for r in prod_rows}
MSKU = {r['ASIN']: r['MSKU'] for r in prod_rows}
# prefer the MSKU that actually sold in the window
for r in msku_rows:
    MSKU[r['ASIN']] = r['MSKU']
EXTRA_PRODUCT = {r['ASIN']: r['PRODUCT'] for r in extra_rows}
EXTRA_MSKU = {r['ASIN']: r['MSKU'] for r in extra_rows}

# destinations: capacity-table FCs that actually sold in the window (IXD excluded here)
obs = defaultdict(float)          # (asin, fc) observed units at plannable FCs
nonplan_units = defaultdict(float)  # asin -> units at VTNF + micro nodes
vtnf_units = defaultdict(float)
micro_units = defaultdict(float)
loc_units = defaultdict(float)
for r in sales_rows:
    a, fc, u = r['ASIN'], r['FC'], int(r['UNITS'])
    loc_units[fc] += u
    if fc in CAP and fc not in IXD:
        obs[(a, fc)] += u
    elif fc == 'VTNF':
        vtnf_units[a] += u
        nonplan_units[a] += u
    else:
        micro_units[a] += u
        nonplan_units[a] += u

ASINS = sorted({r['ASIN'] for r in sales_rows})
DEST = sorted([fc for fc in CAP if fc not in IXD and loc_units.get(fc, 0) > 0])
NONPLAN_LOCS = sorted([fc for fc in loc_units if fc not in CAP and fc != 'VTNF'])

stock = defaultdict(float)
vtnf_stock = defaultdict(float)
for r in stock_rows:
    a, fc, q = r['ASIN'], r['FC'], int(r['SELLABLE'])
    if fc == 'VTNF':
        vtnf_stock[a] += q
    elif fc in CAP:
        stock[(a, fc)] += q
FC_TOTAL_STOCK = {r['FC']: int(r['TOTAL_SELLABLE']) for r in fctot_rows}

inbound_af = defaultdict(float)     # (asin, dest) outstanding
inbound_asin = defaultdict(float)
inbound_fc = defaultdict(float)
inbound_shipcount = {}
for r in inb_rows:
    a, fc, q = r['ASIN'], r['DEST'], float(r['OUTSTANDING'])
    inbound_af[(a, fc)] += q
    inbound_asin[a] += q
    inbound_fc[fc] += q
    inbound_shipcount[a] = int(r['OPEN_SHIPMENTS'])

# ---------------------------------------------------------------- state -> FC map
state_fc = defaultdict(lambda: defaultdict(float))
for r in fcstate_rows:
    st = norm_state(r['STATE_RAW'])
    state_fc[st][r['FC']] += int(r['UNITS'])
CLEAN_STATES = sorted(state_fc)

pooled_state = defaultdict(float)
micro_state = defaultdict(float)
asin_state = defaultdict(lambda: defaultdict(float))
for r in np_rows:
    u = int(r['UNITS'])
    if r['SECTION'] == 'POOLED':
        pooled_state[norm_state(r['KEY1'])] += u
    elif r['SECTION'] == 'MICRO':
        micro_state[norm_state(r['KEY1'])] += u
    else:
        asin_state[r['KEY1']][norm_state(r['KEY2'])] += u

# national FC mix (last-resort fallback)
nat = defaultdict(float)
for st, d in state_fc.items():
    for fc, u in d.items():
        nat[fc] += u
nat_tot = sum(nat.values())
NATIONAL_MIX = {fc: u / nat_tot for fc, u in nat.items()}

# pooled state mix (used when a state has no non-VTNF history)
pooled_fc = defaultdict(float)
for st, u in pooled_state.items():
    share = state_fc.get(st)
    if share:
        tot = sum(share.values())
        for fc, v in share.items():
            pooled_fc[fc] += u * v / tot
    else:
        for fc, p in NATIONAL_MIX.items():
            pooled_fc[fc] += u * p
pooled_tot = sum(pooled_fc.values())
POOLED_MIX = {fc: v / pooled_tot for fc, v in pooled_fc.items()}

STATES_NO_HISTORY = sorted([st for st in pooled_state if st not in state_fc])


def route(units_by_state):
    out = defaultdict(float)
    for st, u in units_by_state.items():
        share = state_fc.get(st)
        if share:
            tot = sum(share.values())
            for fc, v in share.items():
                out[fc] += u * v / tot
        else:
            for fc, p in POOLED_MIX.items():
                out[fc] += u * p
    return out


PER_ASIN_ROUTED = {a for a in ASINS if vtnf_units.get(a, 0) >= 15}

routed = defaultdict(float)   # (asin, fc)
routing_basis = {}
for a in ASINS:
    tot_np = nonplan_units.get(a, 0.0)
    if tot_np <= 0:
        routing_basis[a] = 'n/a (no VTNF / off-network units)'
        continue
    if a in PER_ASIN_ROUTED:
        r1 = route(asin_state.get(a, {}))      # that ASIN's own VTNF states
        s1 = sum(r1.values())
        mix = {fc: v / s1 for fc, v in r1.items()} if s1 else POOLED_MIX
        routing_basis[a] = 'per-ASIN VTNF state mix'
    else:
        mix = POOLED_MIX
        routing_basis[a] = 'pooled state mix'
    # drop sub-0.5 crumbs, rescale to the exact unit total
    raw = {fc: tot_np * p for fc, p in mix.items()}
    keep = {fc: v for fc, v in raw.items() if v >= 0.5}
    if not keep:
        keep = {max(raw, key=raw.get): raw[max(raw, key=raw.get)]}
    ks = sum(keep.values())
    for fc, v in keep.items():
        routed[(a, fc)] = tot_np * v / ks

CRUMBS_DROPPED = sum(1 for a in ASINS for fc in DEST
                     if (a, fc) not in routed and nonplan_units.get(a, 0) > 0)

# ---------------------------------------------------------------- effective demand
eff = defaultdict(float)
for a in ASINS:
    own_obs = sum(obs.get((a, fc), 0) for fc in DEST)
    tot_dem = own_obs + nonplan_units.get(a, 0.0)
    if own_obs < 3 and tot_dem > 0:
        # fair-share rule: too little of its own FC history to pick FCs from
        raw = {fc: tot_dem * p for fc, p in POOLED_MIX.items()}
        keep = {fc: v for fc, v in raw.items() if v >= 0.5}
        if not keep:
            keep = {max(raw, key=raw.get): raw[max(raw, key=raw.get)]}
        ks = sum(keep.values())
        for fc, v in keep.items():
            eff[(a, fc)] = tot_dem * v / ks
        routing_basis[a] = 'fair share (pooled mix, <3 own FC units)'
    else:
        for fc in DEST:
            v = obs.get((a, fc), 0) + routed.get((a, fc), 0.0)
            if v > 0:
                eff[(a, fc)] = v

# ---------------------------------------------------------------- targets / gaps
target = {}
gross_gap = {}
for (a, fc), v in eff.items():
    t = v / WINDOW_DAYS * COVER_DAYS
    target[(a, fc)] = t
    gross_gap[(a, fc)] = max(0.0, t - stock.get((a, fc), 0))

# net off open inbound at ASIN level
net_gap = {}
inbound_credit = {}
for a in ASINS:
    gaps = {fc: g for fc, g in ((fc, gross_gap.get((a, fc), 0.0)) for fc in DEST) if g > 0}
    tot_gap = sum(gaps.values())
    credit = min(inbound_asin.get(a, 0.0), tot_gap)
    inbound_credit[a] = credit
    remaining = tot_gap - credit
    if tot_gap <= 0:
        continue
    for fc, g in gaps.items():
        net_gap[(a, fc)] = remaining * g / tot_gap

# ---------------------------------------------------------------- line rules
plan = {}
below_threshold_units = 0.0
below_threshold_lines = 0
for (a, fc), g in net_gap.items():
    if g <= 0:
        continue
    if target[(a, fc)] < TARGET_THRESHOLD:
        below_threshold_units += g
        below_threshold_lines += 1
        continue
    plan[(a, fc)] = max(LINE_MIN, int(round(g)))

# ---------------------------------------------------------------- capacity passes
cap_limit = {}
for fc in DEST:
    cap, avail = CAP[fc]
    headroom_cap = cap - FC_TOTAL_STOCK.get(fc, 0) - inbound_fc.get(fc, 0)
    cap_limit[fc] = max(0.0, min(headroom_cap, avail - 0.0))

OVER_BEFORE = {fc: round(FC_TOTAL_STOCK.get(fc, 0) + inbound_fc.get(fc, 0) - CAP[fc][0])
               for fc in DEST if FC_TOTAL_STOCK.get(fc, 0) + inbound_fc.get(fc, 0) > CAP[fc][0]}

PLAN_PRECAP = dict(plan)
PRECAP_FC = defaultdict(float)
for (a, fc), q in PLAN_PRECAP.items():
    PRECAP_FC[fc] += q

blocked = defaultdict(float)   # asin -> units the FC network could not take
trim_log = []
for fc in DEST:
    limit = int(math.floor(cap_limit[fc]))
    lines = {a: q for (a, f), q in plan.items() if f == fc}
    tot = sum(lines.values())
    if tot <= limit:
        continue
    # pass A: trim largest lines down to the 2-unit minimum
    order = sorted(lines, key=lambda a: -lines[a])
    for a in order:
        if tot <= limit:
            break
        cut = min(lines[a] - LINE_MIN, tot - limit)
        if cut > 0:
            lines[a] -= cut
            blocked[a] += cut
            tot -= cut
    # pass B: drop whole lines, largest first
    if tot > limit:
        for a in sorted(lines, key=lambda a: -lines[a]):
            if tot <= limit:
                break
            blocked[a] += lines[a]
            tot -= lines[a]
            lines[a] = 0
    trim_log.append((fc, limit))
    for a in list(lines):
        if lines[a] <= 0:
            plan.pop((a, fc), None)
        else:
            plan[(a, fc)] = lines[a]

# re-offer trimmed units to FCs that still have both an unmet gap and headroom
used = defaultdict(float)
for (a, fc), q in plan.items():
    used[fc] += q
for a in sorted(blocked, key=lambda x: -blocked[x]):
    left = blocked[a]
    if left <= 0:
        continue
    cands = []
    for fc in DEST:
        room = cap_limit[fc] - used[fc]
        unmet = net_gap.get((a, fc), 0.0) - plan.get((a, fc), 0)
        if room >= 1 and unmet >= 1 and target.get((a, fc), 0) >= TARGET_THRESHOLD:
            cands.append((fc, min(room, unmet)))
    for fc, room in sorted(cands, key=lambda x: -x[1]):
        if left <= 0:
            break
        take = int(min(left, room))
        if take <= 0:
            continue
        if (a, fc) in plan:
            plan[(a, fc)] += take
        elif take >= LINE_MIN:
            plan[(a, fc)] = take
        else:
            continue
        used[fc] += take
        left -= take
    blocked[a] = left

# ---------------------------------------------------------------- IXD overflow
ixd_headroom = {}
for fc in IXD:
    cap, avail = CAP[fc]
    h1 = cap - FC_TOTAL_STOCK.get(fc, 0) - inbound_fc.get(fc, 0)
    h2 = avail - inbound_fc.get(fc, 0)
    ixd_headroom[fc] = max(0.0, min(h1, h2))

ixd_plan = defaultdict(float)
ixd_used = {fc: 0.0 for fc in IXD}
unplaced = defaultdict(float)
tot_head = sum(ixd_headroom.values())
for a in sorted(blocked, key=lambda x: -blocked[x]):
    left = int(round(blocked[a]))
    if left <= 0:
        continue
    if tot_head <= 0:
        unplaced[a] = left
        continue
    alloc = {}
    for fc in IXD:
        room = ixd_headroom[fc] - ixd_used[fc]
        alloc[fc] = max(0.0, left * ixd_headroom[fc] / tot_head)
    for fc in sorted(IXD, key=lambda f: -alloc[f]):
        room = ixd_headroom[fc] - ixd_used[fc]
        take = int(min(max(0, round(alloc[fc])), room, left))
        if take >= LINE_MIN:
            ixd_plan[(a, fc)] += take
            ixd_used[fc] += take
            left -= take
    # sweep the remainder into whichever cross-dock still has room
    for fc in sorted(IXD, key=lambda f: -(ixd_headroom[f] - ixd_used[f])):
        if left <= 0:
            break
        room = int(ixd_headroom[fc] - ixd_used[fc])
        take = min(left, room)
        if take <= 0:
            continue
        if (a, fc) in ixd_plan or take >= LINE_MIN:
            ixd_plan[(a, fc)] += take
            ixd_used[fc] += take
            left -= take
    if left > 0:
        unplaced[a] = left

# ---------------------------------------------------------------- outputs
res = {
 'run_date': RUN_DATE,
 'window': WINDOW,
 'dest': DEST, 'ixd': IXD,
 'asins': ASINS,
 'product': {a: PRODUCT.get(a, EXTRA_PRODUCT.get(a, a)) for a in ASINS},
 'msku': {a: MSKU.get(a, EXTRA_MSKU.get(a, '')) for a in ASINS},
 'obs': {f'{a}|{fc}': obs[(a, fc)] for (a, fc) in obs},
 'eff': {f'{a}|{fc}': eff[(a, fc)] for (a, fc) in eff},
 'target': {f'{a}|{fc}': target[(a, fc)] for (a, fc) in target},
 'stock': {f'{a}|{fc}': stock[(a, fc)] for (a, fc) in stock},
 'vtnf_stock': dict(vtnf_stock),
 'vtnf_units': dict(vtnf_units), 'micro_units': dict(micro_units),
 'nonplan_units': dict(nonplan_units),
 'gross_gap': {f'{a}|{fc}': gross_gap[(a, fc)] for (a, fc) in gross_gap},
 'net_gap': {f'{a}|{fc}': net_gap[(a, fc)] for (a, fc) in net_gap},
 'plan': {f'{a}|{fc}': plan[(a, fc)] for (a, fc) in plan},
 'ixd_plan': {f'{a}|{fc}': ixd_plan[(a, fc)] for (a, fc) in ixd_plan},
 'unplaced': dict(unplaced),
 'inbound_af': {f'{a}|{fc}': inbound_af[(a, fc)] for (a, fc) in inbound_af},
 'inbound_asin': dict(inbound_asin), 'inbound_fc': dict(inbound_fc),
 'inbound_shipcount': inbound_shipcount,
 'inbound_credit': inbound_credit,
 'fc_total_stock': FC_TOTAL_STOCK,
 'cap': CAP, 'cap_limit': cap_limit, 'ixd_headroom': ixd_headroom,
 'routing_basis': routing_basis,
 'pooled_mix': POOLED_MIX,
 'state_fc': {st: dict(d) for st, d in state_fc.items()},
 'pooled_state': dict(pooled_state), 'micro_state': dict(micro_state),
 'asin_state': {a: dict(d) for a, d in asin_state.items()},
 'clean_states': CLEAN_STATES, 'states_no_history': STATES_NO_HISTORY,
 'loc_units': dict(loc_units),
 'nonplan_locs': NONPLAN_LOCS,
 'over_before': OVER_BEFORE,
 'precap_fc': dict(PRECAP_FC),
 'blocked_total': {a: v for a, v in blocked.items() if v > 0},
 'below_threshold_units': below_threshold_units,
 'below_threshold_lines': below_threshold_lines,
 'extra_product': EXTRA_PRODUCT, 'extra_msku': EXTRA_MSKU,
}
with open(D + 'plan_model.json', 'w') as f:
    json.dump(res, f)

tot_fc = sum(plan.values())
tot_ixd = sum(ixd_plan.values())
print('destinations          :', len(DEST))
print('ASINs in scope        :', len(ASINS))
print('window units          :', int(sum(loc_units.values())))
print('FC lines              :', len(plan), 'units', tot_fc)
print('IXD lines             :', len(ixd_plan), 'units', int(tot_ixd))
print('TOTAL shipment        :', tot_fc + int(tot_ixd))
print('still unplaced        :', int(sum(unplaced.values())), 'over', len(unplaced), 'ASINs')
print('inbound credited      :', round(sum(inbound_credit.values())))
print('below-6 target units  :', round(below_threshold_units), 'over', below_threshold_lines, 'lines')
print('FCs already over cap  :', OVER_BEFORE)
print('IXD headroom          :', {k: round(v) for k, v in ixd_headroom.items()})
print('IXD used              :', ixd_used)
for fc in DEST:
    u = sum(q for (a, f), q in plan.items() if f == fc)
    assert u <= math.floor(cap_limit[fc]) + 0.001, (fc, u, cap_limit[fc])
print('capacity check        : OK')
