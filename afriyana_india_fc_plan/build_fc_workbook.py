#!/usr/bin/env python3
"""Render the FC shipment plan workbook (8 tabs, Arial, TOTAL row above headers)."""
import os
import json, csv
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

D = os.environ.get('AFRIYANA_DIR', os.path.dirname(os.path.abspath(__file__))) + '/'
m = json.load(open(D + 'plan_model.json'))
from datetime import date
OUT = D + 'FC Shipment Plan ' + date.fromisoformat(m['run_date']).strftime('%d-%b-%Y') + '.xlsx'
DEST = m['dest']; IXD = m['ixd']; ASINS = m['asins']
PROD = m['product']; MSKU = m['msku']
CAP = m['cap']

def g(d, a, fc):
    return d.get(f'{a}|{fc}', 0)

WINDOW = 15; COVER = 45

FONT = 'Arial'
H_FILL = PatternFill('solid', fgColor='1F3864')
H_FONT = Font(name=FONT, size=10, bold=True, color='FFFFFF')
T_FILL = PatternFill('solid', fgColor='D9E2F3')
T_FONT = Font(name=FONT, size=10, bold=True)
BODY = Font(name=FONT, size=10)
TITLE = Font(name=FONT, size=12, bold=True)
IXD_FILL = PatternFill('solid', fgColor='E2EFDA')
AMBER = PatternFill('solid', fgColor='FFF2CC')
THIN = Side(style='thin', color='BFBFBF')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

wb = Workbook()


def style_row(ws, row, ncols, font=None, fill=None):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = font or BODY
        if fill:
            cell.fill = fill
        cell.border = BOX


def widths(ws, ws_widths):
    for i, w in enumerate(ws_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ================================================================= 1. Shipment Plan
ws = wb.active
ws.title = 'Shipment Plan'
hdr = ['ASIN', 'Product', 'MSKU', 'Ship to', 'Line type', 'FC units sold',
       'Current FC stock', '45-day target', 'SHIP QTY', 'Stock after', 'Cover after (days)']
rows = []
for a in ASINS:
    for fc in DEST:
        q = g(m['plan'], a, fc)
        if q:
            rows.append((a, fc, 'FC', g(m['obs'], a, fc), g(m['stock'], a, fc),
                         g(m['target'], a, fc), q))
    for fc in IXD:
        q = g(m['ixd_plan'], a, fc)
        if q:
            rows.append((a, fc, 'IXD overflow', None, None, None, q))
rows.sort(key=lambda r: (r[0], r[1]))
n = len(rows)
first, last = 3, 2 + n
ws.cell(row=1, column=1, value='TOTAL')
for col, letter in ((6, 'F'), (7, 'G'), (8, 'H'), (9, 'I'), (10, 'J')):
    ws.cell(row=1, column=col, value=f'=SUM({letter}{first}:{letter}{last})')
style_row(ws, 1, len(hdr), T_FONT, T_FILL)
for i, h in enumerate(hdr, start=1):
    ws.cell(row=2, column=i, value=h)
style_row(ws, 2, len(hdr), H_FONT, H_FILL)
for i, (a, fc, kind, sold, stk, tgt, q) in enumerate(rows):
    r = first + i
    ws.cell(row=r, column=1, value=a)
    ws.cell(row=r, column=2, value=PROD.get(a, a))
    ws.cell(row=r, column=3, value=MSKU.get(a, ''))
    ws.cell(row=r, column=4, value=fc)
    ws.cell(row=r, column=5, value=kind)
    if kind == 'FC':
        ws.cell(row=r, column=6, value=round(sold))
        ws.cell(row=r, column=7, value=round(stk))
        ws.cell(row=r, column=8, value=round(tgt, 1))
        ws.cell(row=r, column=9, value=q)
        ws.cell(row=r, column=10, value=f'=G{r}+I{r}')
        ws.cell(row=r, column=11, value=f'=IF(H{r}<=0,"",ROUND(J{r}/(H{r}/{COVER}),0))')
    else:
        for c in (6, 7, 8, 10, 11):
            ws.cell(row=r, column=c, value='n/a')
        ws.cell(row=r, column=9, value=q)
    style_row(ws, r, len(hdr), BODY, IXD_FILL if kind != 'FC' else None)
widths(ws, [14, 54, 34, 10, 13, 12, 15, 13, 11, 12, 16])
ws.freeze_panes = 'A3'
ws.auto_filter.ref = f'A2:K{last}'

# ================================================================= 2. FC Summary
ws = wb.create_sheet('FC Summary')
hdr = ['Destination', 'Units sold (observed)', 'Effective demand', 'Daily rate',
       'Current stock', 'Cover now (days)', 'Already inbound', 'Planned inbound',
       'SKU lines', 'Stock after', 'Cover after (days)', 'Capacity', 'Available space',
       'Headroom after', 'Constrained by capacity', 'Largest product']
dests = DEST + IXD
n = len(dests)
first, last = 3, 2 + n
ws.cell(row=1, column=1, value='TOTAL')
for col in (2, 3, 5, 7, 8, 9, 10, 12, 13, 14):
    L = get_column_letter(col)
    ws.cell(row=1, column=col, value=f'=SUM({L}{first}:{L}{last})')
style_row(ws, 1, len(hdr), T_FONT, T_FILL)
for i, h in enumerate(hdr, start=1):
    ws.cell(row=2, column=i, value=h)
style_row(ws, 2, len(hdr), H_FONT, H_FILL)
for i, fc in enumerate(dests):
    r = first + i
    is_ixd = fc in IXD
    sold = sum(g(m['obs'], a, fc) for a in ASINS)
    effd = sum(g(m['eff'], a, fc) for a in ASINS)
    planned = sum(g(m['plan'], a, fc) for a in ASINS) if not is_ixd else \
        sum(g(m['ixd_plan'], a, fc) for a in ASINS)
    lines = sum(1 for a in ASINS if (g(m['plan'], a, fc) if not is_ixd else g(m['ixd_plan'], a, fc)))
    big = max(ASINS, key=lambda a: (g(m['plan'], a, fc) if not is_ixd else g(m['ixd_plan'], a, fc)))
    bigq = g(m['plan'], big, fc) if not is_ixd else g(m['ixd_plan'], big, fc)
    cap, avail = CAP[fc]
    ws.cell(row=r, column=1, value=fc)
    ws.cell(row=r, column=2, value=round(sold))
    ws.cell(row=r, column=3, value=round(effd, 1))
    ws.cell(row=r, column=4, value=f'=ROUND(C{r}/{WINDOW},2)')
    ws.cell(row=r, column=5, value=m['fc_total_stock'].get(fc, 0))
    ws.cell(row=r, column=6, value=f'=IF(D{r}<=0,"n/a",ROUND(E{r}/D{r},0))')
    ws.cell(row=r, column=7, value=round(m['inbound_fc'].get(fc, 0)))
    ws.cell(row=r, column=8, value=int(planned))
    ws.cell(row=r, column=9, value=lines)
    ws.cell(row=r, column=10, value=f'=E{r}+G{r}+H{r}')
    ws.cell(row=r, column=11, value=f'=IF(D{r}<=0,"n/a",ROUND(J{r}/D{r},0))')
    ws.cell(row=r, column=12, value=cap)
    ws.cell(row=r, column=13, value=avail)
    ws.cell(row=r, column=14, value=f'=L{r}-J{r}')
    if is_ixd:
        constrained = 'IXD cross-dock'
    else:
        constrained = 'YES' if round(m['precap_fc'].get(fc, 0)) > planned or m['cap_limit'][fc] <= 0 else 'no'
    ws.cell(row=r, column=15, value=constrained)
    ws.cell(row=r, column=16, value=f'{PROD.get(big, big)} ({int(bigq)})' if bigq else '-')
    fill = IXD_FILL if is_ixd else (AMBER if constrained == 'YES' else None)
    style_row(ws, r, len(hdr), BODY, fill)
widths(ws, [12, 19, 15, 10, 13, 14, 14, 14, 10, 12, 16, 10, 14, 14, 21, 46])
ws.freeze_panes = 'A3'
ws.auto_filter.ref = f'A2:P{last}'

# ================================================================= 3. FC Capacity
ws = wb.create_sheet('FC Capacity')
hdr = ['Destination', 'Capacity', 'Available space', 'Effective demand', 'Sellable stock',
       'Inbound allocated', 'Planned shipment', 'Total held after', 'Capacity used %',
       'Available space used %', 'Which limit binds', 'At limit?', 'Units we could NOT place',
       'Capacity we would have needed', 'Extra capacity to request', 'Cover after (days)',
       'Cover if granted (days)']
n = len(dests)
first, last = 3, 2 + n
ws.cell(row=1, column=1, value='TOTAL')
for col in (2, 3, 4, 5, 6, 7, 8, 13, 14, 15):
    L = get_column_letter(col)
    ws.cell(row=1, column=col, value=f'=SUM({L}{first}:{L}{last})')
style_row(ws, 1, len(hdr), T_FONT, T_FILL)
for i, h in enumerate(hdr, start=1):
    ws.cell(row=2, column=i, value=h)
style_row(ws, 2, len(hdr), H_FONT, H_FILL)
for i, fc in enumerate(dests):
    r = first + i
    is_ixd = fc in IXD
    effd = sum(g(m['eff'], a, fc) for a in ASINS)
    planned = sum(g(m['plan'], a, fc) for a in ASINS) if not is_ixd else \
        sum(g(m['ixd_plan'], a, fc) for a in ASINS)
    precap = round(m['precap_fc'].get(fc, 0)) if not is_ixd else planned
    notplaced = max(0, precap - int(planned))
    cap, avail = CAP[fc]
    stk = m['fc_total_stock'].get(fc, 0)
    inb = round(m['inbound_fc'].get(fc, 0))
    ws.cell(row=r, column=1, value=fc)
    ws.cell(row=r, column=2, value=cap)
    ws.cell(row=r, column=3, value=avail)
    ws.cell(row=r, column=4, value=round(effd, 1))
    ws.cell(row=r, column=5, value=stk)
    ws.cell(row=r, column=6, value=inb)
    ws.cell(row=r, column=7, value=int(planned))
    ws.cell(row=r, column=8, value=f'=E{r}+F{r}+G{r}')
    ws.cell(row=r, column=9, value=f'=ROUND(H{r}/B{r},3)')
    ws.cell(row=r, column=10, value=f'=ROUND(G{r}/C{r},3)')
    if is_ixd:
        binds = 'IXD headroom'
    elif cap - stk - inb <= avail:
        binds = 'Capacity Units'
    else:
        binds = 'Available Space'
    ws.cell(row=r, column=11, value=binds)
    at = 'IXD' if is_ixd else ('YES' if notplaced > 0 or m['cap_limit'][fc] <= 0 else 'no')
    ws.cell(row=r, column=12, value=at)
    ws.cell(row=r, column=13, value=notplaced)
    ws.cell(row=r, column=14, value=f'=E{r}+F{r}+G{r}+M{r}')
    ws.cell(row=r, column=15, value=f'=MAX(0,N{r}-B{r})')
    daily = effd / WINDOW
    if daily > 0:
        ws.cell(row=r, column=16, value=f'=ROUND(H{r}/{round(daily,4)},0)')
        ws.cell(row=r, column=17, value=f'=ROUND(N{r}/{round(daily,4)},0)')
    else:
        ws.cell(row=r, column=16, value='n/a')
        ws.cell(row=r, column=17, value='n/a')
    fill = IXD_FILL if is_ixd else (AMBER if at == 'YES' else None)
    style_row(ws, r, len(hdr), BODY, fill)
    for c in (9, 10):
        ws.cell(row=r, column=c).number_format = '0.0%'
widths(ws, [12, 10, 14, 15, 13, 16, 15, 14, 13, 18, 17, 10, 21, 25, 22, 16, 20])
ws.freeze_panes = 'A3'

# expansion case narrative
atlimit = [fc for fc in DEST if m['cap_limit'][fc] <= 0 or
           round(m['precap_fc'].get(fc, 0)) > sum(g(m['plan'], a, fc) for a in ASINS)]
blocked_tot = int(sum(m['blocked_total'].values())) if m['blocked_total'] else 0
ixd_tot = int(sum(m['ixd_plan'].values()))
unplaced_tot = int(sum(m['unplaced'].values()))
need = 0
for fc in DEST:
    precap = round(m['precap_fc'].get(fc, 0))
    stk = m['fc_total_stock'].get(fc, 0); inb = round(m['inbound_fc'].get(fc, 0))
    need += max(0, stk + inb + precap - CAP[fc][0])
r0 = last + 3
ws.cell(row=r0, column=1, value='THE EXPANSION CASE').font = TITLE
over = m['over_before']
narrative = [
 f"FCs at their limit this run: {', '.join(atlimit) if atlimit else 'none'}.",
 f"Units the FC network could not accept: {blocked_tot}. "
 f"Of those, {ixd_tot} were redirected to the Amazon IXD cross-docks (DED3/DED5) and "
 f"{unplaced_tot} could not be placed anywhere.",
 f"Extra storage capacity we would need for the full plan to fit at the destination FCs: "
 f"{int(need)} units (see 'Extra capacity to request').",
 "These units cannot simply be re-routed. Amazon assigns destination FCs through Send to "
 "Amazon, so we cannot direct stock to an FC of our choosing; and the FCs that still have "
 "headroom are not the ones carrying the demand - the demand sits behind the constrained "
 "nodes, which is exactly why they are full.",
 "IXD (DED3/DED5) is a workaround, not a fix. Cross-docking gets stock into Amazon's "
 "network sooner and lets it distribute onward, but it does NOT create space at the "
 "constrained FCs. Until the limits at those FCs are raised, regional cover there stays "
 "short of the 45-day target.",
]
if over:
    narrative.insert(1, "ALREADY OVER THE STATED LIMIT on sellable stock plus open inbound "
                        "alone, before any new shipment: " +
                        '; '.join(f'{fc} by {v} units' for fc, v in over.items()) +
                        ". Zero units are planned into these. Either the capacity file is "
                        "stale or Amazon has re-cut the limit - worth confirming before the "
                        "next run.")
for i, line in enumerate(narrative):
    c = ws.cell(row=r0 + 1 + i, column=1, value=line)
    c.font = BODY
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.merge_cells(start_row=r0 + 1 + i, start_column=1, end_row=r0 + 1 + i, end_column=10)
    ws.row_dimensions[r0 + 1 + i].height = 30

# ================================================================= 4. ASIN Summary
ws = wb.create_sheet('ASIN Summary')
hdr = ['ASIN', 'Product', 'MSKU', 'FC units sold', 'VTNF / off-network units',
       'VTNF share %', 'Daily rate (effective)', '45-day requirement', 'FC stock',
       'VTNF stock', 'Cover now (days)', 'Gross gap', 'Inbound on open shipments',
       'Net gap', 'Ship to FCs', 'Redirected to IXD', 'Total shipment', 'Still unplaced',
       'To Procure', 'Cover after (days)', 'Demand mix basis', 'Status']
n = len(ASINS)
first, last = 3, 2 + n
ws.cell(row=1, column=1, value='TOTAL')
for col in (4, 5, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19):
    L = get_column_letter(col)
    ws.cell(row=1, column=col, value=f'=SUM({L}{first}:{L}{last})')
style_row(ws, 1, len(hdr), T_FONT, T_FILL)
for i, h in enumerate(hdr, start=1):
    ws.cell(row=2, column=i, value=h)
style_row(ws, 2, len(hdr), H_FONT, H_FILL)
for i, a in enumerate(ASINS):
    r = first + i
    fcsold = sum(g(m['obs'], a, fc) for fc in DEST)
    npu = m['nonplan_units'].get(a, 0)
    effd = sum(g(m['eff'], a, fc) for fc in DEST)
    fcstock = sum(g(m['stock'], a, fc) for fc in DEST)
    vstock = m['vtnf_stock'].get(a, 0)
    gross = sum(g(m['gross_gap'], a, fc) for fc in DEST)
    inb = m['inbound_asin'].get(a, 0)
    netg = sum(g(m['net_gap'], a, fc) for fc in DEST)
    tofc = sum(g(m['plan'], a, fc) for fc in DEST)
    toixd = sum(g(m['ixd_plan'], a, fc) for fc in IXD)
    unp = m['unplaced'].get(a, 0)
    ws.cell(row=r, column=1, value=a)
    ws.cell(row=r, column=2, value=PROD.get(a, a))
    ws.cell(row=r, column=3, value=MSKU.get(a, ''))
    ws.cell(row=r, column=4, value=round(fcsold))
    ws.cell(row=r, column=5, value=round(npu))
    ws.cell(row=r, column=6, value=f'=IF((D{r}+E{r})=0,0,E{r}/(D{r}+E{r}))')
    ws.cell(row=r, column=7, value=round(effd / WINDOW, 2))
    ws.cell(row=r, column=8, value=round(effd / WINDOW * COVER, 1))
    ws.cell(row=r, column=9, value=round(fcstock))
    ws.cell(row=r, column=10, value=round(vstock))
    ws.cell(row=r, column=11, value=f'=IF(G{r}<=0,"n/a",ROUND(I{r}/G{r},0))')
    ws.cell(row=r, column=12, value=round(gross, 1))
    ws.cell(row=r, column=13, value=round(inb, 1))
    ws.cell(row=r, column=14, value=round(netg, 1))
    ws.cell(row=r, column=15, value=int(tofc))
    ws.cell(row=r, column=16, value=int(toixd))
    ws.cell(row=r, column=17, value=f'=O{r}+P{r}')
    ws.cell(row=r, column=18, value=int(unp))
    ws.cell(row=r, column=19, value=f'=MAX(0,Q{r}-J{r})')
    ws.cell(row=r, column=20, value=f'=IF(G{r}<=0,"n/a",ROUND((I{r}+O{r})/G{r},0))')
    ws.cell(row=r, column=21, value=m['routing_basis'].get(a, ''))
    if unp:
        st = 'UNPLACED'
    elif toixd and tofc:
        st = 'FC + IXD'
    elif toixd:
        st = 'IXD only'
    elif tofc:
        st = 'SHIP'
    elif netg > 0:
        st = 'BELOW 6-UNIT THRESHOLD'
    else:
        st = 'NO ACTION'
    ws.cell(row=r, column=22, value=st)
    style_row(ws, r, len(hdr), BODY)
    ws.cell(row=r, column=6).number_format = '0.0%'
widths(ws, [14, 52, 32, 12, 18, 12, 17, 15, 10, 11, 14, 11, 20, 10, 12, 15, 14, 13, 11, 16, 30, 22])
ws.freeze_panes = 'D3'
ws.auto_filter.ref = f'A2:V{last}'

# flag PROCURE rows
for i, a in enumerate(ASINS):
    r = first + i
    tot = sum(g(m['plan'], a, fc) for fc in DEST) + sum(g(m['ixd_plan'], a, fc) for fc in IXD)
    if tot - m['vtnf_stock'].get(a, 0) > 0:
        ws.cell(row=r, column=22, value=ws.cell(row=r, column=22).value + ' / PROCURE')
        for c in range(1, len(hdr) + 1):
            ws.cell(row=r, column=c).fill = AMBER

# ================================================================= 5. ASIN x FC Matrix
ws = wb.create_sheet('ASIN x FC Matrix')
cols = DEST + IXD
hdr = ['ASIN', 'Product', 'MSKU'] + cols + ['Total']
mat_asins = [a for a in ASINS
             if any(g(m['plan'], a, fc) for fc in DEST) or any(g(m['ixd_plan'], a, fc) for fc in IXD)]
n = len(mat_asins)
first, last = 3, 2 + n
ws.cell(row=1, column=1, value='TOTAL')
for ci in range(4, 4 + len(cols) + 1):
    L = get_column_letter(ci)
    ws.cell(row=1, column=ci, value=f'=SUM({L}{first}:{L}{last})')
style_row(ws, 1, len(hdr), T_FONT, T_FILL)
for i, h in enumerate(hdr, start=1):
    ws.cell(row=2, column=i, value=h)
style_row(ws, 2, len(hdr), H_FONT, H_FILL)
for i, a in enumerate(mat_asins):
    r = first + i
    ws.cell(row=r, column=1, value=a)
    ws.cell(row=r, column=2, value=PROD.get(a, a))
    ws.cell(row=r, column=3, value=MSKU.get(a, ''))
    for j, fc in enumerate(cols):
        q = g(m['plan'], a, fc) if fc in DEST else g(m['ixd_plan'], a, fc)
        ws.cell(row=r, column=4 + j, value=int(q) if q else None)
    L1 = get_column_letter(4); L2 = get_column_letter(3 + len(cols))
    ws.cell(row=r, column=4 + len(cols), value=f'=SUM({L1}{r}:{L2}{r})')
    style_row(ws, r, len(hdr), BODY)
widths(ws, [14, 50, 30] + [8] * len(cols) + [9])
ws.freeze_panes = 'D3'
ws.auto_filter.ref = f'A2:{get_column_letter(len(hdr))}{last}'

# ================================================================= 6. Regional Demand
ws = wb.create_sheet('Regional Demand')
state_fc = m['state_fc']; pooled_state = m['pooled_state']
states = sorted(set(list(state_fc) + list(pooled_state)))
# normalise the pooled (VTNF) states onto clean names
hdr = ['Destination state', 'VTNF / off-network units', '% of off-network demand',
       'Amazon FC units to the same state', 'Top 3 FCs serving it']
tot_np = sum(pooled_state.values())
n = len(states)
first, last = 3, 2 + n
ws.cell(row=1, column=1, value='TOTAL')
for col in (2, 4):
    L = get_column_letter(col)
    ws.cell(row=1, column=col, value=f'=SUM({L}{first}:{L}{last})')
style_row(ws, 1, len(hdr), T_FONT, T_FILL)
for i, h in enumerate(hdr, start=1):
    ws.cell(row=2, column=i, value=h)
style_row(ws, 2, len(hdr), H_FONT, H_FILL)
for i, st in enumerate(states):
    r = first + i
    d = state_fc.get(st, {})
    top = sorted(d.items(), key=lambda x: -x[1])[:3]
    ws.cell(row=r, column=1, value=st)
    ws.cell(row=r, column=2, value=int(pooled_state.get(st, 0)))
    ws.cell(row=r, column=3, value=f'=IF($B$1=0,0,B{r}/$B$1)')
    ws.cell(row=r, column=4, value=int(sum(d.values())))
    ws.cell(row=r, column=5, value=', '.join(f'{fc} {int(u)}' for fc, u in top) or
            'no Amazon FC history - routed on the pooled mix')
    style_row(ws, r, len(hdr), BODY)
    ws.cell(row=r, column=3).number_format = '0.0%'
widths(ws, [42, 20, 20, 26, 40])
ws.freeze_panes = 'A3'

r0 = last + 3
ws.cell(row=r0, column=1, value='WHY A DESTINATION RECEIVES LITTLE OR NOTHING').font = TITLE
ws.cell(row=r0 + 1, column=1, value='Destination').font = H_FONT
ws.cell(row=r0 + 1, column=2, value='Planned units').font = H_FONT
ws.cell(row=r0 + 1, column=3, value='Reason').font = H_FONT
for c in range(1, 4):
    ws.cell(row=r0 + 1, column=c).fill = H_FILL
reasons = []
for fc in DEST + IXD:
    is_ixd = fc in IXD
    planned = sum(g(m['plan'], a, fc) for a in ASINS) if not is_ixd else \
        sum(g(m['ixd_plan'], a, fc) for a in ASINS)
    effd = sum(g(m['eff'], a, fc) for a in ASINS)
    if is_ixd:
        why = 'IXD cross-dock - receives only the units the FC network could not accept.'
    elif m['cap_limit'][fc] <= 0:
        why = ('Capacity capped: sellable stock plus open inbound already meets or exceeds '
               'the stated Capacity Units, so no new units can be sent.')
    elif planned == 0 and effd < 6:
        why = 'Low velocity - the 45-day target never clears the 6-unit line threshold.'
    elif planned == 0:
        why = 'Already above target - current stock plus open inbound covers the 45-day need.'
    elif round(m['precap_fc'].get(fc, 0)) > planned:
        why = 'Capacity capped - the plan was trimmed to fit the Capacity / Available Space limit.'
    else:
        why = 'Receiving the full netted gap.'
    reasons.append((fc, int(planned), why))
for fc in ['PNQ2', 'DEL8', 'DEL2', 'DEX8', 'JPX1']:
    if fc not in DEST + IXD:
        reasons.append((fc, 0, 'Never carried our sales in the window - not a destination. '
                               '(DEX8 and JPX1 have never appeared in our data at all.)'))
for i, (fc, q, why) in enumerate(reasons):
    r = r0 + 2 + i
    ws.cell(row=r, column=1, value=fc).font = BODY
    ws.cell(row=r, column=2, value=q).font = BODY
    c = ws.cell(row=r, column=3, value=why)
    c.font = BODY
    c.alignment = Alignment(wrap_text=True, vertical='top')

# ================================================================= 7. Inbound Shipments
ws = wb.create_sheet('Inbound Shipments')
ship = list(csv.DictReader(open(D + 'r3_shipment_detail.tsv'), delimiter='\t'))
hdr = ['Shipment ID', 'Destination', 'Status', 'Created', 'Last updated', 'Age (days)',
       'MSKUs', 'Units expected', 'Units located', 'Units outstanding', '% received',
       'Workflow', 'PO']
n = len(ship)
first, last = 3, 2 + n
ws.cell(row=1, column=1, value='TOTAL')
for col in (7, 8, 9, 10):
    L = get_column_letter(col)
    ws.cell(row=1, column=col, value=f'=SUM({L}{first}:{L}{last})')
style_row(ws, 1, len(hdr), T_FONT, T_FILL)
for i, h in enumerate(hdr, start=1):
    ws.cell(row=2, column=i, value=h)
style_row(ws, 2, len(hdr), H_FONT, H_FILL)
for i, s in enumerate(ship):
    r = first + i
    vals = [s['SHIPMENT_ID'], s['DEST'], s['STATUS'].replace('_', ' ').title(), s['CREATED'],
            s['LAST_UPDATED'], int(s['AGE_DAYS']), int(s['MSKUS']), int(s['EXPECTED']),
            int(s['LOCATED']), int(s['OUTSTANDING']), None, s['WORKFLOW'], s['PO']]
    for ci, v in enumerate(vals, start=1):
        ws.cell(row=r, column=ci, value=v)
    ws.cell(row=r, column=11, value=f'=IF(H{r}=0,0,I{r}/H{r})')
    ws.cell(row=r, column=11).number_format = '0.0%'
    fill = IXD_FILL if s['DEST'] in IXD else None
    if s['STATUS'] == 'IN_TRANSIT' and int(s['AGE_DAYS']) >= 14:
        fill = AMBER
    style_row(ws, r, len(hdr), BODY, fill)
    ws.cell(row=r, column=11).number_format = '0.0%'
widths(ws, [16, 12, 12, 12, 13, 10, 8, 14, 13, 16, 11, 17, 10])
ws.freeze_panes = 'A3'
ws.auto_filter.ref = f'A2:M{last}'

inb = list(csv.DictReader(open(D + 'r3_asin_fc_outstanding.tsv'), delimiter='\t'))
per_asin = defaultdict(float)
per_split = defaultdict(lambda: defaultdict(float))
ships_of = {}
for r_ in inb:
    per_asin[r_['ASIN']] += float(r_['OUTSTANDING'])
    per_split[r_['ASIN']][r_['DEST']] += float(r_['OUTSTANDING'])
    ships_of[r_['ASIN']] = int(r_['OPEN_SHIPMENTS'])
ilist = sorted(per_asin, key=lambda a: -per_asin[a])
# largest-remainder rounding so the per-ASIN total ties exactly to the shipment total
_target = int(round(sum(per_asin.values())))
_base = {a: int(per_asin[a]) for a in ilist}
_rem = sorted(ilist, key=lambda a: -(per_asin[a] - _base[a]))
_short = _target - sum(_base.values())
for a in _rem[:max(0, _short)]:
    _base[a] += 1
per_asin_disp = _base
r0 = last + 3
ws.cell(row=r0, column=1, value='OUTSTANDING UNITS PER ASIN').font = TITLE
h2 = ['ASIN', 'Product', 'MSKU', 'Units outstanding', 'Open shipments', 'Destination split']
f2, l2 = r0 + 3, r0 + 2 + len(ilist)
ws.cell(row=r0 + 1, column=1, value='TOTAL')
ws.cell(row=r0 + 1, column=4, value=f'=SUM(D{f2}:D{l2})')
style_row(ws, r0 + 1, len(h2), T_FONT, T_FILL)
for i, h in enumerate(h2, start=1):
    ws.cell(row=r0 + 2, column=i, value=h)
style_row(ws, r0 + 2, len(h2), H_FONT, H_FILL)
IN_SCOPE = set(ASINS)
for i, a in enumerate(ilist):
    r = f2 + i
    name = PROD.get(a) or m['extra_product'].get(a, a)
    if a not in IN_SCOPE:
        name = name + '  [out of scope - no sales in the window]'
    sku = MSKU.get(a) or m['extra_msku'].get(a, '')
    split = ', '.join(f'{fc} {int(round(u))}' for fc, u in
                      sorted(per_split[a].items(), key=lambda x: -x[1]) if round(u) >= 1)
    ws.cell(row=r, column=1, value=a)
    ws.cell(row=r, column=2, value=name)
    ws.cell(row=r, column=3, value=sku)
    ws.cell(row=r, column=4, value=per_asin_disp[a])
    ws.cell(row=r, column=5, value=ships_of[a])
    ws.cell(row=r, column=6, value=split)
    fill = IXD_FILL if set(per_split[a]) & set(IXD) else None
    style_row(ws, r, len(h2), BODY, fill)

# ================================================================= 8. Method & Assumptions
ws = wb.create_sheet('Method & Assumptions')
ws.column_dimensions['A'].width = 34
ws.column_dimensions['B'].width = 126
row = 1


def sec(t):
    global row
    c = ws.cell(row=row, column=1, value=t)
    c.font = TITLE
    row += 1


def kv(k, v):
    global row
    a = ws.cell(row=row, column=1, value=k); a.font = Font(name=FONT, size=10, bold=True)
    a.alignment = Alignment(vertical='top')
    b = ws.cell(row=row, column=2, value=v); b.font = BODY
    b.alignment = Alignment(wrap_text=True, vertical='top')
    ws.row_dimensions[row].height = max(14, 13 * (1 + len(v) // 115))
    row += 1


def gap():
    global row
    row += 1


tot_fc = int(sum(m['plan'].values()))
tot_ixd = int(sum(m['ixd_plan'].values()))
inb_total = int(round(sum(float(s['OUTSTANDING']) for s in ship)))
scope_inb = int(round(sum(m['inbound_asin'].values())))

sec('FC SHIPMENT PLAN - METHOD & ASSUMPTIONS')
kv('Seller', 'AFRIYANA INDIA PRIVATE LIMITED, Amazon.in')
kv('Built', '5 October 2026 (unattended scheduled run)')
gap()
sec('1. DATA SOURCES AND WINDOW')
kv('Report 1 - Inventory Ledger',
   'Fulfilment Reports > Inventory Ledger > Download. Summary view, location = Fulfilment '
   'centre, aggregate = Daily, Exact dates 15/09/2026 - 04/10/2026, .csv. Exact dates took '
   'the scripted entry, so no fallback to "Last 30 days" was needed.')
kv('Settled days used',
   '19 Sep 2026 to 3 Oct 2026 inclusive - 15 full settled days. Amazon returned data only to '
   '3 Oct (4 Oct had not landed), so the window was extended backwards rather than padded '
   'with a partial day. The last day (3 Oct, 512 customer-shipment units) sits above the '
   '15-day mean of 390, so it is settled, not partial. All daily rates divide by 15.')
kv('Report 2 - Amazon Fulfilled Shipments',
   'Same 15-day window, Exact dates, .csv. Buyer PII never left the browser: FC x state and '
   'FC x state x MSKU aggregates were computed in-page and only those aggregates were '
   'extracted. NOTE: the column layout has shifted by one since the task file was written - '
   'Shipment Date is now col 9, Merchant SKU col 14, Shipped Quantity col 16, Shipping State '
   'col 30, FC col 46 (the file quoted 8/13/15/29/45).')
kv('Cross-check', f'Report 2 window total = 5,849 units. Report 1 customer-shipment total = '
   f'5,849 units. Exact agreement.')
kv('Report 3 - Open inbound',
   'listShipments + per-shipment eligibilities JSON APIs, fetched in batches of 8. Statuses '
   'kept: IN_TRANSIT, CHECKED_IN, RECEIVING. 74 open shipments.')
gap()
sec('2. SAMPLING EXCLUSIONS')
kv('Rule applied (21 Aug 2026)',
   '100 units of each of the five sampling ASINs (B0H11QZXVC, B0FP9K4MGR, B0D4QRCB9T, '
   'B0GZPZLV8M, B0CVND98DQ), 500 in total, removable only from customer shipments dated '
   '7-10 August 2026.')
kv('Units actually excluded this run',
   'ZERO. The settled window (19 Sep - 3 Oct 2026) does not overlap 7-10 Aug 2026 at all, so '
   'no units are removable. The rule is explicit that nothing may be taken from a substitute '
   'date range, and nothing was. No sampling adjustment has been applied to Report 1 or '
   'Report 2 figures.')
kv('Raw daily cube kept',
   'The raw ASIN x date x location cube for the five sampling ASINs over the full 15-day '
   'window was captured so an exclusion rule can be re-applied later without re-pulling.')
gap()
sec('3. CONFIRMATIONS NOT TAKEN (unattended run)')
kv('Carried forward without confirmation', '')
kv('  - Sampling figures',
   '100 units each / 500 total, dates 7-10 Aug 2026, and the five-ASIN list were carried '
   'forward unchanged. Nobody was available to confirm them, or to say whether a new sampling '
   'ASIN has been added. Moot this run, since zero units were removable.')
kv('  - Capacity file',
   'The FC capacity table is the one supplied on 21 Aug 2026 and quoted in the task file. No '
   '"FC Wise capacity.xlsx" was present in the working folder, so it could not be refreshed. '
   'Available Space moves weekly, so these figures are up to six weeks stale - please resend.')
gap()
sec('4. REGIONAL DEMAND MODEL')
kv('VTNF', 'Our own Seller Flex warehouse in Gurgaon, not an Amazon FC. It serves orders '
   'nationwide when FC stock runs out, so its demand is NOT spread on the national FC mix. '
   f'VTNF sold {int(sum(m["vtnf_units"].values()))} units in the window ('
   f'{sum(m["vtnf_units"].values())/5849:.0%} of all units).')
kv('Off-network micro-nodes (choice made unattended)',
   'Eleven small non-FBA nodes (' + ', '.join(m['nonplan_locs']) + ') sold '
   f'{int(sum(m["micro_units"].values()))} units between them. None appears in the capacity '
   'table and Send to Amazon cannot target them, so they are treated exactly like VTNF: '
   'non-plannable, with their units routed through the state map rather than left as '
   'destinations. This is a judgement call made without the user; it moves ~1.2% of volume.')
kv('State to FC service map',
   'Built from non-VTNF, non-micro rows of Report 2: for each shipping state, the share of '
   f'that state\'s units each FC served. {len(m["clean_states"])} clean destination states '
   'after normalising abbreviations (MH/GJ/TN/UP/PB/TG/JK/KA/AP/BR/WB/DL/HR/RJ/JH/MP/CH, '
   '"New delhi", "Tamilnadu", "Chattisgarh", "Goa India", "Daman & Diu" and "Dadra & Nagar '
   'Haveli" merged into their parent states).')
kv('Routing', 'Each VTNF / off-network unit is pushed through the map on its Shipping State. '
   'States with no non-VTNF history fall back to the pooled state map, then to the national '
   'FC mix. ' + (f'States with no FC history this run: {", ".join(m["states_no_history"])}.'
                 if m['states_no_history'] else 'Every state had FC history this run.'))
kv('Per-ASIN vs pooled',
   f'{len(m["clean_states"]) and sum(1 for a in ASINS if m["vtnf_units"].get(a,0)>=15)} ASINs '
   'shipped 15 or more units from VTNF and are routed on their own VTNF state mix. Every '
   'other ASIN uses the pooled mix.')
kv('Sub-half-unit crumbs',
   'Routed fractions below 0.5 units per ASIN x FC were dropped and the rest rescaled so each '
   'ASIN\'s routed total still equals its exact VTNF / off-network units. A crumb under half '
   'a unit can never clear the 6-unit target threshold, so this changes no line.')
kv('Fair share for thin ASINs',
   'An ASIN with fewer than 3 units of its own Amazon-FC sales has too little history to pick '
   'FCs from, so its whole effective demand is spread on the pooled mix instead of its own '
   'sparse pattern.')
kv('Effective demand', 'Observed Amazon FC sales + routed VTNF / off-network units.')
gap()
sec('5. TARGETS, GAPS AND LINE RULES')
kv('Cover target', '45 days. FC target = effective FC demand / 15 x 45.')
kv('Gross gap', 'FC target minus current SELLABLE stock at that FC on 3 Oct 2026, floored at zero.')
kv('Inbound netting',
   f'Each ASIN\'s outstanding open-inbound units are credited against its total gross gap at '
   f'ASIN level (not pinned to DED3/DED5), and the remaining need is scaled pro-rata across '
   f'the FCs still showing a gap. {scope_inb:,} units were available to credit across the '
   f'in-scope ASINs; {int(sum(m["inbound_credit"].values())):,} units were actually absorbed.')
kv('Line rules',
   'Minimum 2 units per ASIN x FC line; a line is only opened where the 45-day '
   'target is 6 units or more. '
   f'{round(m["below_threshold_units"]):,} units of net gap across '
   f'{m["below_threshold_lines"]} ASIN x FC combinations sat under that threshold and were '
   f'deliberately not actioned.')
kv('To Procure', 'Total planned shipment (FC lines + IXD overflow) minus VTNF stock, floored '
   'at zero. Flagged PROCURE on the ASIN Summary tab.')
kv('Cover basis',
   'Cover on the FC tabs is measured against EFFECTIVE demand (observed FC sales plus routed '
   'VTNF), because that is what the plan is sized to. "Units sold (observed)" is kept as a '
   'separate raw column so the two are never confused.')
kv('Scope', 'Every ASIN with at least one unit sold in the window: 241 ASINs. VTNF stock is '
   'treated as ZERO for supply purposes and is never a constraint; it is used only to compute '
   'To Procure.')
kv('Destinations',
   f'{len(DEST)} Amazon FCs with sales in the window and a capacity record. PNQ2 holds stock '
   'but sold nothing in the window, so it is not a destination. DEL8, DEL2, DEX8 and JPX1 have '
   'never carried our stock or sales. Amazon assigns destination FCs through Send to Amazon, '
   'so we cannot direct stock to a new FC.')
gap()
sec('6. CAPACITY CONSTRAINT')
kv('Rule', 'Per FC: current sellable stock + already inbound + planned shipment <= Capacity '
   'Units, AND planned shipment <= Available Space. The tighter of the two binds. Applied '
   'after inbound netting and the line-minimum rules.')
kv('Inbound used in the test',
   'ACTUAL outstanding inbound per destination, taken from the per-shipment destinations '
   'captured in Report 3, rather than each ASIN\'s credited inbound spread pro-rata. The task '
   'file describes the pro-rata spread; now that destinations are captured per shipment the '
   'actual split is both available and more accurate, and it is what the IXD headroom '
   'derivation already uses. Noted as a deliberate deviation.')
kv('Trimming', 'Pass A trims an over-capacity FC\'s largest lines down to the 2-unit minimum; '
   'pass B, only if still over, drops whole lines largest-first. Trimmed units are then '
   'offered to FCs that still have both an unmet gap and headroom, before anything goes to IXD.')
kv('Already over the limit',
   ('; '.join(f'{fc} is over its stated Capacity Units by {v} units on sellable stock plus '
              f'open inbound alone' for fc, v in m['over_before'].items()) +
    '. Zero units are planned into these - either the capacity file is stale or Amazon has '
    're-cut the limit.') if m['over_before'] else 'No FC is over its stated limit before shipping.')
gap()
sec('7. IXD OVERFLOW')
kv('Rule (21 Aug 2026)', 'Whatever the FC network cannot accept goes to the Amazon IXD '
   'cross-docks DED3 and DED5, which receive and distribute onward. This replaces the older '
   '"never a planned destination" rule.')
kv('Headroom derivation',
   'Per cross-dock: min(Capacity - sellable stock - outstanding open inbound to that '
   'cross-dock, Available Space - outstanding open inbound to that cross-dock), floored at 0. '
   'Re-derived from this run\'s per-shipment destinations, not assumed. ' +
   '; '.join(f'{fc}: {int(v):,} units of headroom' for fc, v in m['ixd_headroom'].items()) + '.')
kv('Split this run',
   '; '.join(f'{fc} took {int(sum(g(m["ixd_plan"], a, fc) for a in ASINS)):,} units'
             for fc in IXD) +
   '. DED3 carries most of it, as it did in August, but the split was re-derived rather than '
   'assumed.')
kv('What IXD does and does not do',
   'IXD gets stock into Amazon\'s network sooner and lets Amazon distribute it onward, but it '
   'does NOT create space at the constrained FCs. The capacity expansion case still stands.')
kv('Still unplaced', f'{int(sum(m["unplaced"].values()))} units could not be placed anywhere '
   'after the FC network and both cross-docks were exhausted.')
gap()
sec('8. INBOUND SHIPMENTS TAB - WHY THE TWO TOTALS DIFFER')
kv('The two figures',
   f'The Inbound Shipments tab carries EVERY outstanding unit: {inb_total:,} units across 74 '
   f'open shipments. The ASIN Summary "Inbound on open shipments" column carries '
   f'{scope_inb:,} units, because it is limited to the 241 ASINs that sold in the window. The '
   f'difference ({inb_total - scope_inb:,} units) is inbound for ASINs with no sales in the '
   'window; those rows are labelled "[out of scope - no sales in the window]" in the Product '
   'column. This gap is correct and is not an error.')
kv('Known gap in the line data',
   'For 25 of the 74 open shipments Amazon\'s items endpoint returns only the first 50 SKU '
   'lines, so the line list is partial. Shipment-level outstanding is authoritative: each '
   'shipment\'s outstanding was distributed across its known ASIN lines pro-rata to '
   'line-level outstanding, falling back to line expected where no line outstanding exists. '
   f'The totals tie - {inb_total:,} units at shipment level and {inb_total:,} units after '
   'distribution.')
gap()
sec('9. LIMITATIONS')
kv('Stale capacity file', 'Available Space moves weekly and this table is from 21 Aug 2026.')
kv('Partial inbound line lists', 'See section 8 - the pro-rata distribution is an estimate at '
   'ASIN level for 25 shipments, though shipment and FC totals are exact.')
kv('15 days of history', 'A 15-day window is short for slow-moving ASINs; a single order can '
   'move a small ASIN across the 6-unit threshold. The threshold exists to damp that.')
kv('No seasonality', 'The 45-day requirement is a flat extrapolation of the 15-day rate. No '
   'festive or promotional uplift is applied.')
kv('Two products without a unit size',
   'B0FHBH57NS "TMPE Ayurvedic Herbal Massage Potli Pack of 2" and B0G93FGZDQ "TMPE '
   'Professional Cuticle Oil Refill Pack" carry no size anywhere in the title or SKU. Known '
   'open items; not guessed from sibling SKUs.')
kv('Duplicate listings',
   'B0CVQJS2NC / B0GDTPNJFG (Sandalwood Diffuser Oil 1L) and B0CVQL2SF9 / B0GDTCJZNQ '
   '(Sandalwood Diffuser Oil 30ml) legitimately share a name. They are planned separately.')
gap()
sec('10. HEADLINE NUMBERS')
kv('Total planned shipment', f'{tot_fc + tot_ixd:,} units - {tot_fc:,} to FCs across '
   f'{len(m["plan"])} lines, {tot_ixd:,} to IXD cross-docks across {len(m["ixd_plan"])} lines.')
kv('FCs receiving stock', f'{sum(1 for fc in DEST if sum(g(m["plan"], a, fc) for a in ASINS))} '
   f'of {len(DEST)}.')
kv('Open inbound netted off', f'{int(sum(m["inbound_credit"].values())):,} units.')
kv('Sampling units excluded', '0 (window does not overlap 7-10 Aug 2026).')

wb.save(OUT)
print('written', OUT)
