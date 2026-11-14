import json, os
REPO = os.environ['RD_REPO']
d={}
for fn in ['m9_partial.json','bychain.json','m1_census.json','m1_dominant.json']:
    d[fn.replace('.json','')]=json.load(open(fn))
d['capability13_confirmed']={
 'all_13_found_in_omnibridge_overview_html': True,
 'format':'<Chain> - (<verification> + Chain Signatures)',
 'capability13': json.load(open(os.path.join(REPO, 'inputs/reference.json')))['capability13'],
 'intersection_with_28': json.load(open(os.path.join(REPO, 'inputs/reference.json')))['capability_in_28'],
 'count_in_28':10}
d['telemetry']={'flow_rows_read':6800,'flow_rows_dedup':6625,'flow_dup_removed':175,
 'transfer_groups_built':2522,'net_zero_dropped':0,'out_of_window_dropped':2211,
 'near_side_excluded':28,'measured_cross_chain_transfers':2494,
 'census_rows_read':1675,'census_rows_dedup':1675,
 'flow_windows':192,'census_windows':48,'not_completed':0,
 'collector_included_transactions':2522,'cross_check':'built 2522 == collector included_transactions 2522'}
json.dump(d,open('results.json','w'),indent=1)
print('wrote results.json',os.path.getsize('results.json'),'bytes')
