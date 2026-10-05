---
name: amazon-india-inventory-planning
description: Weekly FC-wise shipment plan for AFRIYANA INDIA on Amazon.in (Seller Central via Claude in Chrome). Runs Sundays.
---

Build the weekly FC-wise shipment plan for AFRIYANA INDIA PRIVATE LIMITED on Amazon.in.

DATA COLLECTION (Claude-in-Chrome against sellercentral.amazon.in; session already logged in).
Use the Chrome browser named "INDIA".
The Amazon session drops often. If it asks for a password or a one-time passcode, STOP - never
enter credentials. Save whatever aggregates you already have to the outputs folder, tell the user
which report you were on, and ask them to sign in. The Chrome extension also loses its tab group
periodically, which wipes BOTH sessionStorage and localStorage on the sellercentral origin. Do
not rely on browser storage surviving: as soon as each report is aggregated, pull the aggregates
out of the browser and write them to a file in the outputs folder before moving on. Keep the raw
daily ASIN x date x location cube for the sampling ASINs too, so an exclusion rule can be
re-applied later without re-pulling the reports.

BROWSER NOTE (21 Sep 2026): the connected browsers report as "Browser 1" / "Browser 2" and the
names do not identify which holds the live Seller Central session - it varies run to run. Probe
one, and if it lands on Sign in, select the other. `select_browser` frequently does not stick:
after calling it, call `tabs_context_mcp` and confirm you got the group you expect before acting.
If a tool returns "Tab N is not in Claude's tab group", re-call select_browser then
tabs_context_mcp and retry - do not assume the session has expired.

CRITICAL - DO NOT TRUNCATE TITLES. When emitting data from the browser, derive the product name
(brand + product + unit size) INSIDE the browser from the FULL title, and emit the finished short
name. Never emit a title clipped to a fixed character count and shorten it afterwards - Amazon
puts the size at the END of the title, so clipping destroys it.

REPORT 1 - Inventory Ledger (volumes + stock)
  Fulfilment Reports > Inventory Ledger > Download. Summary view, location = Fulfilment centre,
  time period = Daily, Date range = Exact dates. Request .csv.
  The date controls are Katal web components, not native selects. Set the dropdown by assigning
  .value and dispatching a CustomEvent('change'). If Exact dates will not take a scripted entry,
  fall back to "Last 30 days" - a wider span is what this step wants anyway - and note the
  substitution in the Method tab.
  WINDOW: 15 FULL SETTLED DAYS. Amazon lags ~2 days, so ask for a wider span than you need
  (about 20 calendar days), see which dates actually come back, and take the LAST 15 settled
  days - extend backwards, never pad with partial recent days. Judge partiality by comparing
  each recent day's total customer-shipment units against the window mean; if the last day is in
  normal range it is settled. Divide daily rates by 15 and say which exact dates were used.
  Gives FC-wise sales ("Customer Shipments", negative) and FC-wise inventory ("Ending Warehouse
  Balance", Disposition = SELLABLE, on the last settled date). Also the only source of full
  product titles - extract the unit size from them here.

REPORT 2 - Amazon Fulfilled Shipments (destination geography)
  Same 15-day window, Exact dates, .csv. Columns needed: FC (col 45), Shipping State (col 29),
  Merchant SKU (col 13), Shipped Quantity (col 15), Shipment Date (col 8). There is no ASIN
  column - build an MSKU -> ASIN map from the ledger first. This report contains buyer PII -
  aggregate INSIDE the browser and bring back only aggregates. Never transfer customer-
  identifying fields.
  Cross-check the window total against the ledger's customer-shipment total; they should agree
  to within a unit or two.

REPORT 3 - Open inbound shipments
  Do NOT scrape the contents iframe - use the JSON APIs, which are far faster and complete:
    list:  /fba/shippingqueue/api/v1/shipment/listShipments?pageSize=101&orderBy=SHIPMENT_UPDATE_DATE&isOrderAscending=false&t2pLaunched=true
           gives shipmentId, destinationFC, shipmentStatus, createdDate, lastUpdatedDate,
           mskus, expectedQuantity, locatedQuantity, workflowType, poId.
    items: /fba/wmsr/eligibilities/{shipmentId}?withInquiry=true&withDiscrepancies=true
           -> discrepancies.items[] with merchantSKU, asin, expectedQuantity,
           totalLocatedQuantity. Fetch in batches of ~8 concurrently.
  Keep statuses IN_TRANSIT, CHECKED_IN, RECEIVING. Outstanding = max(0, expected - located),
  floored at zero.
  KNOWN GAP: for some in-transit shipments the items endpoint returns a PARTIAL line list (line
  expected < shipment expected). Shipment-level outstanding is authoritative - distribute each
  shipment's outstanding across its known ASIN lines pro-rata to line-level outstanding, falling
  back to line expected where no line outstanding exists. Check the totals tie and say so.
  RECORD THE DESTINATION PER SHIPMENT - the IXD overflow step below needs outstanding inbound
  split by cross-dock, not just per ASIN.

To read reports 1 and 2 without local file access: once Done, click Download, use
read_network_requests to capture the /listing/downloadfile?...documentId=... URL, and fetch it
with javascript_tool (build the URL with new URL() + searchParams.set() - a literal query string
gets blocked). Parse in-browser. To move bulk results back, write the text into the page
(document.body.innerHTML = '<pre id=D></pre>' then set textContent) and read it with
get_page_text - that returns tens of thousands of characters intact, whereas a javascript_tool
return value truncates at roughly 1,100. Note get_page_text can be refused as "Cookie/query
string data" if the emitted text looks like a query string - emit clean TSV. Keep the emitted
table compact by dropping FC demand entries below 1.4 units (they can never clear the line
threshold) - never by clipping titles.

SAMPLING EXCLUSIONS
Product sampling inflates apparent demand and RECURS. Sampling ASINs:
  B0H11QZXVC AROMATICO Neem Oil 100ml
  B0FP9K4MGR AROMATICO Kumkumadi Tailam Face Oil 100ml
  B0D4QRCB9T AROMATICO Lavender Mint Massage Oil 300ml
  B0GZPZLV8M AYURVIDA Rosehip Oil 60ml
  B0CVND98DQ AROMATICO Rosemary Essential Oil 30ml
RULE (user instruction, 21 Aug 2026 - supersedes all earlier event lists):
  - Quantity: 100 units of EACH of these five ASINs, i.e. 500 units in total.
  - Dates: the sampling ran 7-10 August 2026 inclusive. Remove the units ONLY from customer
    shipments dated 7, 8, 9 or 10 Aug 2026 that fall inside the window. Do NOT spill the
    removal onto 11 Aug or any later day.
  - Within those four dates, take the units from the highest-volume day first, pro-rata across
    the locations selling on that day. If the four days hold fewer than 100 units for an ASIN,
    remove what is there and report the shortfall rather than reaching outside 7-10 Aug.
  - If the settled window does not overlap 7-10 Aug 2026 at all, ZERO units are removable. Say
    so plainly rather than reaching for a substitute date range.
Apply the identical removal to Report 2 rows before building the state -> FC map.
Report how many units were excluded and from which ASINs. At the start of each run ask the user
to confirm the 100-units-each figure and the sampling dates for that period, and whether any new
sampling ASINs were added. On an unattended run, carry the figures forward and list the
confirmations you could not take in the Method tab.

DEMAND MODEL - REGIONAL
VTNF is our own Seller Flex warehouse in Gurgaon, not an Amazon FC. Because FC stock runs out it
services orders nationwide, so its demand must NOT be spread on the national FC mix:
1. From NON-VTNF rows of Report 2 build a state -> FC service map (what share of each state's
   units each FC served). Normalise state names, map abbreviations (MH -> MAHARASHTRA, GJ ->
   GUJARAT, TN/Tamilnadu -> TAMIL NADU, UP -> UTTAR PRADESH, PB -> PUNJAB, TG -> TELANGANA,
   JK -> JAMMU & KASHMIR, KA -> KARNATAKA, AP -> ANDHRA PRADESH, BR -> BIHAR, WB -> WEST BENGAL,
   "New delhi" -> DELHI, CH -> CHANDIGARH, JH -> JHARKHAND, MP -> MADHYA PRADESH, RJ/Rajsthan ->
   RAJASTHAN, Uttar Pardesh -> UTTAR PRADESH, Westbengal -> WEST BENGAL, Chattisgarh ->
   CHHATTISGARH, North Goa -> GOA). Expect ~33 clean destination states.
2. Push each VTNF row's units through that map using its Shipping State. States with no non-VTNF
   history fall back to the pooled state map, then to the national FC mix.
3. Effective FC demand for an ASIN = its observed Amazon FC sales + its routed VTNF units.
4. Route per-ASIN where that ASIN shipped 15+ units from VTNF; otherwise use the pooled mix.
5. Drop routed fractions below 0.5 units per ASIN x FC and rescale the rest so each ASIN's
   routed total still equals its exact VTNF units. Sub-half-unit crumbs can never clear the
   6-unit target threshold, so this changes no line. Say it was done.

OTHER RULES
- Scope: every ASIN with at least one unit sold in the window (after sampling exclusions).
- VTNF stock is treated as ZERO and is never a supply constraint.
- Target 45 days of cover. FC target = 45-day requirement x that FC's regional demand share.
- Gross gap = FC target minus current sellable stock, floored at zero.
- NET OFF OPEN INBOUND: credit each ASIN's outstanding inbound units against its gross gap and
  scale the remaining need pro-rata across the FCs still showing a gap. Credit at ASIN level, not
  pinned to DED3/DED5. Report "Inbound on Open Shipments" per ASIN and per FC.
- Minimum 2 units per ASIN x FC line; only open a line where the 45-day target is 6+ units.
  For ASINs with under 3 units of their own FC sales use a fair-share rule when picking FCs.
  Report how much net gap sat under the 6-unit threshold and was deliberately not actioned.
- "To Procure" = TOTAL planned shipment (FC lines + IXD overflow) minus VTNF stock, floored at
  zero. Flag those ASINs PROCURE.
- Skip FCs with no sales in the window. DEX8 and JPX1 have never appeared in our data; Amazon
  assigns destination FCs via Send to Amazon so we cannot direct stock to a new FC.
- COVER BASIS: measure cover on the FC tabs against EFFECTIVE demand (observed FC sales plus
  routed VTNF), because that is what the plan is sized to. Keep "units sold" as the raw observed
  figure in its own column so the two are not confused.

FC CAPACITY CONSTRAINT - ACTIVE
Enforce, per FC: current sellable stock + already inbound + planned shipment <= Capacity Units,
and additionally cap planned shipment at that FC's Available Space. The tighter of the two binds.
For the capacity test, spread each ASIN's credited inbound across its own gapped FCs pro-rata.
Apply AFTER the inbound netting and the line-minimum rules. Where an FC would breach its cap:
pass A trims that FC's largest lines down to the 2-unit minimum; pass B, only if still over,
drops whole lines largest-first. Then offer the trimmed units to FCs that still have both an
unmet gap and headroom.
Some FCs are ALREADY over their stated Capacity Units on sellable stock plus open inbound alone,
before any new shipment. Plan zero units into those, and call them out separately in the
expansion case - it means the capacity file is stale or Amazon has re-cut the limit.

IXD OVERFLOW (user instruction, 21 Aug 2026) - do NOT leave capacity-blocked units unshipped
Whatever the FC network cannot accept goes to the Amazon IXD cross-docks DED3 and DED5, which
receive and distribute onward. This replaces the old "never a planned destination" rule.
  - IXD headroom per cross-dock = min(Capacity - sellable stock - outstanding open inbound to
    that cross-dock, Available Space - outstanding open inbound to that cross-dock), floored at 0.
    Use the per-shipment destinations captured in Report 3.
  - Allocate each ASIN's blocked units pro-rata to the free space at each cross-dock, keeping the
    2-unit line minimum, then sweep any remainder into whichever cross-dock still has room.
  - Anything that still cannot be placed is reported as "Still unplaced" per ASIN.
  - As of 21 Aug 2026 DED5 is nearly full (2,614 available against ~2,398 units of open inbound),
    so DED3 takes almost all of it. Re-derive this every run - do not assume the split.
  - State plainly that IXD gets stock into Amazon's network sooner but does NOT create space at
    the constrained FCs, so the capacity expansion case still stands.

CAPACITY TABLE - units. Source: user file "FC Wise capacity.xlsx", received 21 Aug 2026.
Ask the user to confirm or resend it at the start of each run, since Available Space moves weekly.
  FC     Capacity  Available        FC     Capacity  Available
  AMD2     16152     15962          streams to IXD:
  ATX1       750       595          DED3      5000      4919
  BLR7       750       296          DED5      5000      2614
  BLR8      1458      1011
  BOM5       750       428
  BOM7       750       470
  CCX1       750       271
  CJB1      2618      2267
  DED4       750       123
  DEL4       750       291
  DEL5       750       498
  DEX3       750       593
  GAX1      3897      3687
  HYD3       873       545
  HYD8       763       606
  JPX2      1225      1130
  LDX1       750       457
  LKO1      7246      7063
  MAA4     16880     16523
  NAX1       750       565
  PNQ2       750       691
  PNQ3       750       571
  DEL8 50000/50000, DEL2 1500/1497, DEX8 750/750, JPX1 750/750 have never carried our stock or
  sales - not destinations.

PRESENT STOCK
Current SELLABLE stock per FC from Report 1 on the last settled date. Not reserved or unsellable.

PRODUCT NAMES (user preference, reaffirmed 21 Aug 2026)
Brand + Product Name + UNIT SIZE. ALWAYS INCLUDE THE UNIT SIZE - hard requirement. Many ASINs
differ only by size (five separate "AROMATICO Sandalwood Diffuser Oil" ASINs at 30ml, 250ml,
500ml and 1L), so a name without a size is unusable for picking stock.
  - Size means the volume or weight of one item: 10ml, 30ml, 60ml, 100ml, 250ml, 300ml, 500ml,
    1L, 60g, 88gm, 200gm, 500gm, etc.
  - Take it from the Seller SKU where present, else from the FULL product title. Ignore sizes
    that are part of an auto-generated SKU code (pattern XX-XXXX-XXXX).
  - Multipacks additionally get "Pack of N" AFTER the size, e.g. "CUTIKLES Anti-Fungal Nail
    Repair Serum 30ml Pack of 3". Singles get no count.
  - Strip all benefit/feature copy, including anything after the first full stop.
  - Brands: AROMATICO, TMPE, CUTIKLES, INTIAID, AYURVIDA, MINERAYA, CIRCADIAN CARE.
  - If a size genuinely cannot be determined, write the name without it and list those ASINs in
    the run summary. Do not guess from sibling SKUs. Known open items with no size anywhere in
    the title: B0FHBH57NS "TMPE Ayurvedic Herbal Massage Potli Pack of 2", B0CYPNXGQX "TMPE
    Stainless Steel Foot Scraper Pedi File Refill Pack of 2", B0G93FGZDQ "TMPE Professional
    Cuticle Oil Refill Pack".
  - Note two duplicate listing pairs that legitimately share a name: B0CVQJS2NC / B0GDTPNJFG
    (Sandalwood Diffuser Oil 1L) and B0CVQL2SF9 / B0GDTCJZNQ (Sandalwood Diffuser Oil 30ml).

OUTPUT
An .xlsx in the outputs folder, "FC Shipment Plan DD-Mon-YYYY.xlsx", Arial throughout. EVERY
table's TOTAL row goes ABOVE the column headers, never at the bottom. Tabs:
1. "Shipment Plan" - ASIN, Product, MSKU, Ship to, Line type (FC / IXD overflow), FC units sold,
   current FC stock, 45-day target, SHIP QTY, stock after, cover after. IXD rows show n/a in the
   demand columns and are shaded. Freeze panes + autofilter.
2. "FC Summary" - per destination incl. DED3/DED5: units sold, effective demand, daily rate,
   current stock, cover now, already inbound, planned inbound, SKU lines, stock after, cover
   after, capacity, available space, headroom after, constrained by capacity, largest product.
3. "FC Capacity" - the expansion case. Per destination: capacity, available space, effective
   demand, sellable stock, inbound allocated, planned shipment, total held after, capacity used
   %, available space used %, which limit binds, "At limit?" (YES / no / IXD), units we could NOT
   place, capacity we would have needed, extra capacity to request, cover after, cover if
   granted. Shade at-limit rows amber and IXD rows green. Follow with a plain-English expansion
   case: the FCs at their limit, the blocked units, the total ask, why they cannot be re-routed,
   and that IXD is a workaround rather than a fix.
4. "ASIN Summary" - ASIN, Product, MSKU, demand split (FCs vs VTNF), VTNF share %, daily rate,
   45-day requirement, FC stock, VTNF stock, cover now, gross gap, inbound, net gap, Ship to FCs,
   Redirected to IXD, Total shipment, Still unplaced, To Procure, cover after, demand mix basis,
   status.
5. "ASIN x FC Matrix" - ASIN, Product, MSKU, pivot of ship quantities by destination incl. IXD.
6. "Regional Demand" - per destination state: VTNF units, % of VTNF demand, Amazon FC units to
   the same state, top 3 FCs serving it. Plus a table explaining why any destination receives
   little or nothing (low velocity, already above target, capacity capped, IXD cross-dock,
   never stocked).
7. "Inbound Shipments" - ALWAYS include this sheet (user instruction, 21 Sep 2026). Two tables.
   TOP: one row per open shipment - Shipment ID, Destination, Status, Created, Last updated,
   Age (days), MSKUs, Units expected, Units located, Units outstanding, % received, Workflow, PO.
   BOTTOM: outstanding units per ASIN - ASIN, Product, MSKU, Units outstanding, Open shipments,
   and the destination split written as "FC units" largest first (e.g. "DED3 200, BLR8 165").
   Shade the DED3/DED5 rows green, and shade amber any shipment still In transit 14+ days after
   it was created so stuck freight is obvious. Freeze panes + autofilter on the shipment table.
   Both tables get their own TOTAL row ABOVE their own headers.
   The two inbound totals will NOT match, and that is correct: this sheet carries every
   outstanding unit, while "ASIN Summary" is limited to ASINs that sold in the window. Label the
   out-of-scope ASINs in the Product column, and say so on the Method tab quoting both figures,
   so the gap is never read as an error.
   Save the per-shipment and per-ASIN aggregates to the outputs folder as r3_shipment_detail.tsv
   before building, the same as every other report.
8. "Method & Assumptions" - data sources, exact settled dates, sampling exclusions and units
   removed, routing logic, inbound netting, capacity constraint, IXD overflow rule and headroom
   derivation, cover basis, every rule above, and limitations.

Use real formulas, run the xlsx skill's recalc.py, confirm zero errors, and cross-check that
TOTAL shipment (FC + IXD) ties across the Shipment Plan, FC Summary, ASIN Summary and ASIN x FC
Matrix tabs, that no destination breaches either its Capacity or its Available Space, that
every product name carries a unit size, and that the Inbound Shipments outstanding total ties to
the FC Summary "already inbound" column. Present with present_files and summarise: total units
split FC vs IXD, lines, FCs receiving, units already inbound netted off, units the FCs could not
take and where they went, anything still unplaced, the FCs at their limit and the extra capacity
to request, units to procure and the ASINs driving it, the sampling units excluded, and the open
inbound position - how many shipments are open, units outstanding, and any shipment stuck In
transit for 14+ days.

Note: stale LibreOffice lock files (.~lock.* and ~$*) make recalc hang - write to a fresh
filename and copy into the outputs folder at the end.

LESSONS FROM THE 5 OCT 2026 RUN (added 5 Oct 2026 - apply on every run)
- REUSE THE SCRIPTS. build_fc_plan.py and build_fc_workbook.py are in the
  AFRIYANA_Dashboard_Automation folder (also in GitHub vinbhard/claude, folder
  afriyana_india_fc_plan/). Do not rewrite them. Update the per-run settings block at the top of
  build_fc_plan.py (RUN_DATE, WINDOW) and the CAP table if a new capacity file arrived, then
  update the run-specific sentences on the Method tab in build_fc_workbook.py (built date,
  ledger date range requested, settled days, last-day vs mean check, sampling overlap, Report 2
  column notes, capacity-file date). The workbook filename follows RUN_DATE automatically.
  If the folder still has the 5 Oct copies, set D at the top of both scripts to that folder
  (or set AFRIYANA_DIR).
- SAVE INTO OUTPUTS TOO. Copy every r1_/r2_/r3_ TSV, plan_model.json, both scripts and the final
  workbook into the task's outputs folder as well as AFRIYANA_Dashboard_Automation, so a task
  export carries them.
- QUOTE THE SUMMARY FROM THE WORKBOOK. Every figure in the final summary must be read back from
  the recalculated workbook, not remembered from the model run. On 5 Oct the summary said
  "209 ASINs flagged PROCURE" while the workbook correctly showed To Procure = 0 (VTNF stock
  covered every shipped ASIN). Count PROCURE flags from the ASIN Summary Status column and quote
  the To Procure TOTAL cell. If it is zero, say "nothing to procure".
- REPORT 2 COLUMN LAYOUT has shifted by one since the column numbers above were written. Locate
  the FC, Shipping State, Merchant SKU, Shipped Quantity and Shipment Date columns BY HEADER NAME,
  never by position.
- CAPACITY TEST BASIS. On 5 Oct the capacity test used actual per-destination open inbound from
  Report 3 instead of pro-rata credited inbound. Keep doing that (it reflects what will physically
  arrive at each FC) and state it on the Method tab.
- OFF-NETWORK MICRO-NODES. Locations that are neither VTNF nor in the capacity table (11 nodes,
  68 units on 5 Oct) are routed like VTNF, not used as destinations. Keep this and state it.
- CAPACITY FILE. The table above is still the 21 Aug 2026 file. Before starting, look in
  AFRIYANA_Dashboard_Automation for a newer "FC Wise capacity*.xlsx". If one is there, use it and
  say so. If not, carry the 21 Aug figures forward and flag them as stale in the summary.
- OPEN-INBOUND WATCHLIST from 5 Oct: FBA15M8D1G39 (HYD3, 40 days in transit, 67 units) and
  FBA15MFDQV40 (DED3, 25 days, 1,057 units). Say whether each is still open, and list any other
  shipment that is now 14+ days in transit.
- RECALC. LibreOffice needs its Calc component. If recalc.py reports that the source file
  "could not be loaded", that is the cause, not a bad workbook.
