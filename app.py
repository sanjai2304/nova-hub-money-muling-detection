
import os
import json
import pandas as pd
import networkx as nx
from flask import Flask, request, jsonify, render_template, send_file
from datetime import datetime, timedelta
import uuid
import io

app = Flask(__name__)

# --------------------------------------------------------------------------------
# CONFIG & CONSTANTS
# --------------------------------------------------------------------------------

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

FRAUD_SCORES = {
    'cycle': 40,
    'fan_in': 25,
    'fan_out': 25,
    'shell': 20,
    'high_velocity': 10
}

# --------------------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------------------

def parse_csv(file_stream):
    """
    Parses CSV into a DataFrame.
    Expected columns: transaction_id, sender_id, receiver_id, amount, timestamp
    """
    try:
        df = pd.read_csv(file_stream)
        required_cols = {'transaction_id', 'sender_id', 'receiver_id', 'amount', 'timestamp'}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing columns: {missing}")
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        raise ValueError(f"Error parsing CSV: {str(e)}")

def build_graph(df):
    """
    Builds a directed graph from the DataFrame.
    """
    G = nx.DiGraph()
    
    # Add nodes (accounts)
    senders = df['sender_id'].unique()
    receivers = df['receiver_id'].unique()
    all_accounts = set(senders) | set(receivers)
    G.add_nodes_from(all_accounts)
    
    # Add edges (transactions)
    # We store transaction details as edge attributes. 
    # Since NetworkX MultiDiGraph is better for multiple edges, but DiGraph is standard,
    # we will aggregate or just add them. For cycle detection, simplified DiGraph is often easier,
    # but we lose transaction-level info if we don't handle parallel edges.
    # Requirement: "Each transaction = directed edge".
    # We will use MultiDiGraph to allow multiple transactions between same pair.
    
    G_multi = nx.MultiDiGraph()
    
    for _, row in df.iterrows():
        G_multi.add_edge(
            row['sender_id'],
            row['receiver_id'],
            transaction_id=row['transaction_id'],
            amount=row['amount'],
            timestamp=row['timestamp']
        )
        
    return G_multi

def detect_cycles(G):
    """
    Detects cycles of length 3 to 5 using a length-limited DFS on the 2-core.
    Optimization: Reduces graph to 2-core to remove leaves/trees before searching.
    Returns: 
    - list of cycles (lists of nodes)
    """
    cycles_found = []
    G_simple = nx.DiGraph(G)
    
    # K-Core Optimization: Remove nodes with degree < 2 (cannot be part of a cycle)
    # This drastically reduces search space for transaction trees.
    try:
        # k=2 for cycles. Use core_number to handle directedness properly?
        # nx.k_core treats graph as undirected by default? No, relies on min degree.
        # For directed cycles, we need nodes with strictly (in >= 1 and out >= 1)?
        # nx.k_core on DiGraph checks total degree by default?
        # Let's just use simple pruning: Recursively remove nodes with in=0 or out=0.
        # But nx.k_core(G, k=2) is a good approximation for "involved in loops".
        core_nodes = nx.k_core(G_simple, k=2).nodes()
        G_search = G_simple.subgraph(core_nodes)
    except:
        G_search = G_simple

    seen_cycles = set()
    
    def dfs(start_node, current_node, path, depth):
        if depth > 5:
            return
        
        # Optimization: prioritize neighbors that point back to start?
        neighbors = list(G_search.neighbors(current_node))
        
        for neighbor in neighbors:
            if neighbor == start_node:
                if 3 <= depth <= 5:
                    # Normalize cycle
                    cycle = path[:]
                    min_node = min(cycle)
                    min_idx = cycle.index(min_node)
                    canonical = tuple(cycle[min_idx:] + cycle[:min_idx])
                    
                    if canonical not in seen_cycles:
                        seen_cycles.add(canonical)
                        cycles_found.append(list(canonical))
            elif neighbor not in path:
                dfs(start_node, neighbor, path + [neighbor], depth + 1)
    
    # Sort nodes by degree to start with likely hubs? Or least degree?
    # Starting with least degree might close cycles faster.
    nodes = sorted(list(G_search.nodes()), key=lambda n: G_search.degree(n))
    
    for node in nodes:
        dfs(node, node, [node], 1)
        
    return cycles_found

def analyze_smurfing(df, window_hours=72):
    """
    Detects Fan-in and Fan-out.
    Fan-in: >=10 senders -> 1 receiver within 72 hrs
    Fan-out: 1 sender -> >=10 receivers within 72 hrs
    """
    suspects = {'fan_in': [], 'fan_out': []}
    
    # Sort by time
    df_sorted = df.sort_values('timestamp')
    
    # Fan-in patterns (Group by receiver)
    for receiver, group in df_sorted.groupby('receiver_id'):
        if len(group) < 10:
            continue
        # distinct senders? Prompt says ">= 10 senders". Unique senders? 
        # "Fan-in: >=10 senders -> 1 receiver". implies unique senders.
        # Let's check unique senders in rolling window.
        
        # We need to check if ANY 72h window has >= 10 unique senders.
        # A simple check: if total unique senders >= 10 and (max_time - min_time) <= 72h?
        # Or sliding window.
        
        # Sliding window approach:
        txs = group.to_dict('records')
        # We need to find a sub-window where unique senders >= 10.
        # This is tricky in O(N). 
        # Simplified: Check specific windows or just check overall density if all txs close.
        # Actually, let's just check if there is a cluster of 10 unique senders within 72h.
        
        # Iterate through txs, treat as start of window
        for i in range(len(txs)):
            window_start = txs[i]['timestamp']
            window_end = window_start + timedelta(hours=window_hours)
            
            # Get txs in this window
            window_txs = [t for t in txs[i:] if t['timestamp'] <= window_end]
            unique_senders = set(t['sender_id'] for t in window_txs)
            
            if len(unique_senders) >= 10:
                suspects['fan_in'].append(receiver)
                break
                
    # Fan-out patterns (Group by sender)
    for sender, group in df_sorted.groupby('sender_id'):
        if len(group) < 10:
            continue
            
        txs = group.to_dict('records')
        for i in range(len(txs)):
            window_start = txs[i]['timestamp']
            window_end = window_start + timedelta(hours=window_hours)
            
            window_txs = [t for t in txs[i:] if t['timestamp'] <= window_end]
            unique_receivers = set(t['receiver_id'] for t in window_txs)
            
            if len(unique_receivers) >= 10:
                suspects['fan_out'].append(sender)
                break
                
    return suspects

def detect_layered_shell(G_multi):
    """
    Chain patterns where intermediate accounts have <= 3 total transactions.
    Intermediate = In-degree > 0 AND Out-degree > 0
    Total transactions = In-degree + Out-degree <= 3
    """
    shells = []
    # Calculate degrees
    in_degree = dict(G_multi.in_degree())
    out_degree = dict(G_multi.out_degree())
    
    for node in G_multi.nodes():
        d_in = in_degree.get(node, 0)
        d_out = out_degree.get(node, 0)
        total = d_in + d_out
        
        if d_in > 0 and d_out > 0 and total <= 3:
            shells.append(node)
            
    return shells

def check_high_velocity(df, limit_hours=72, min_tx=5):
    """
    Accounts with high velocity: > 5 tx in < 72 hours?
    Prompt says: Score +10 for "High velocity (<72 hrs)".
    We'll interpret this as: Any account involved in a burst of 5+ transactions in 72h.
    """
    velocity_suspects = set()
    
    # Combine senders and receivers
    # Just counting involvement
    involved = pd.concat([
        df[['sender_id', 'timestamp']].rename(columns={'sender_id': 'account'}),
        df[['receiver_id', 'timestamp']].rename(columns={'receiver_id': 'account'})
    ])
    
    involved = involved.sort_values('timestamp')
    
    for account, group in involved.groupby('account'):
        if len(group) < min_tx:
            continue
            
        txs = group['timestamp'].tolist()
        for i in range(len(txs) - min_tx + 1):
            t_start = txs[i]
            t_end = txs[i + min_tx - 1]
            if (t_end - t_start) <= timedelta(hours=limit_hours):
                velocity_suspects.add(account)
                break
                
    return list(velocity_suspects)

# --------------------------------------------------------------------------------
# ROUTES
# --------------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    start_time = datetime.now()
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        df = parse_csv(file.stream)
        G = build_graph(df) # MultiDiGraph
        
        # 1. Detect Patterns
        # Cycles
        cycles = detect_cycles(G) # List of lists
        
        # Rings Identification
        # All accounts in a cycle belong to a ring.
        # We can group connected cycles into rings? 
        # Prompt: "All accounts in cycle belong to same ring_id".
        # We will create a ring for each unique cycle found, or merge overlapping ones?
        # Overlapping cycles usually constitute a larger fraud ring.
        # Let's merge overlapping cycles into components.
        
        ring_map = {} # node -> ring_id
        rings_info = []
        
        if cycles:
            # Build a graph of cycle connections to merge them
            # Accounts in cycles
            cycle_nodes = set()
            for c in cycles:
                for n in c:
                    cycle_nodes.add(n)
            
            # Subgraph of only cycle nodes
            # We want to find Connected Components of these cycle nodes?
            # Actually, simply: If node A is in Cycle 1 and Cycle 2, then Cycle 1 and 2 are same Ring.
            # Use Union-Find or NetworkX connected components on the undirected visualization of these nodes, 
            # restricted to edges participating in cycles? 
            # Simpler: Just map nodes to rings based on connected components of the cycle subgraph.
            
            # But wait, finding ALL cycles is hard. We have `cycles` list.
            # Just group these sets.
            
            cycle_sets = [set(c) for c in cycles]
            # Merge sets
            merged_rings = []
            while cycle_sets:
                current = cycle_sets.pop(0)
                # Try to merge with others
                merged = True
                while merged:
                    merged = False
                    rest = []
                    for other in cycle_sets:
                        if not current.isdisjoint(other):
                            current |= other
                            merged = True
                        else:
                            rest.append(other)
                    cycle_sets = rest
                merged_rings.append(current)
            
            for idx, ring_nodes in enumerate(merged_rings):
                ring_id = f"RING_{idx+1:03d}"
                # Dynamic Score: Base 80 + size * 2, max 99.9
                r_score = min(99.9, 80 + (len(ring_nodes) * 2))
                
                rings_info.append({
                    "ring_id": ring_id,
                    "member_accounts": list(ring_nodes),
                    "pattern_type": "cycle",
                    "risk_score": round(r_score, 1)
                })
                for node in ring_nodes:
                    ring_map[node] = ring_id

        # Smurfing
        smurfing = analyze_smurfing(df)
        
        # Shells
        shells = detect_layered_shell(G)
        
        # Velocity
        velocity_suspects = check_high_velocity(df)
        
        # 2. Scoring
        suspicious_accounts = []
        all_suspects = set(ring_map.keys()) | set(smurfing['fan_in']) | set(smurfing['fan_out']) | set(shells) | set(velocity_suspects)
        
        for account in all_suspects:
            score = 0
            patterns = []
            
            # Legitimacy Filter (High Volume Merchants/Payroll)
            # Threshold: > 20 tx AND (>90% Fan-In OR >90% Fan-Out)
            # This prevents flagging merchants (High Fan-In) or Payroll (High Fan-Out)
            d_in = G.in_degree(account) if G.has_node(account) else 0
            d_out = G.out_degree(account) if G.has_node(account) else 0
            total_tx = d_in + d_out
            
            is_likely_legit = False
            if total_tx > 20: 
                ratio_in = d_in / total_tx 
                ratio_out = d_out / total_tx
                # If mostly receiving (Merchant) or mostly sending (Payroll), ignore unless cycling
                if ratio_in > 0.9 or ratio_out > 0.9:
                    is_likely_legit = True
            
            # Cycle check (Critical - overrides legit check)
            if account in ring_map:
                score += FRAUD_SCORES['cycle']
                account_cycle_lengths = set()
                for c in cycles:
                    if account in c:
                        account_cycle_lengths.add(len(c))
                
                if account_cycle_lengths:
                    for length in sorted(account_cycle_lengths):
                        patterns.append(f"cycle_length_{length}")
                else:
                    patterns.append("cycle") 
            
            if account in smurfing['fan_in']:
                if not is_likely_legit:
                    score += FRAUD_SCORES['fan_in']
                    patterns.append("fan_in")
                
            if account in smurfing['fan_out']:
                if not is_likely_legit:
                    score += FRAUD_SCORES['fan_out']
                    patterns.append("fan_out")
                
            if account in shells:
                # Shells are low volume by definition
                score += FRAUD_SCORES['shell']
                patterns.append("shell_account")
                
            if account in velocity_suspects:
                if not is_likely_legit:
                    score += FRAUD_SCORES['high_velocity']
                    patterns.append("high_velocity")
            
            # Cap at 100
            score = min(score, 100)
            
            if score > 0:
                suspicious_accounts.append({
                    "account_id": account,
                    "suspicion_score": float(score),
                    "detected_patterns": patterns,
                    "ring_id": ring_map.get(account, None)
                })
        
        # Sort by score descending
        suspicious_accounts.sort(key=lambda x: x['suspicion_score'], reverse=True)
        
        # Prepare Graph Data for Vis.js
        nodes = []
        edges = []
        
        suspect_ids = {s['account_id'] for s in suspicious_accounts}
        
        # Identify edges that form cycles (for highlighting)
        cycle_edges = set()
        if cycles:
            for cycle in cycles:
                for i in range(len(cycle)):
                    u, v = cycle[i], cycle[(i + 1) % len(cycle)]
                    cycle_edges.add((u, v))

        for node in G.nodes():
            is_suspicious = node in suspect_ids
            is_in_ring = node in ring_map
            
            # Visual Distinction Requirement
            # Highlight Cycles: Amber, Suspicious: Red, Normal: Blue
            if is_in_ring:
                color = "#f59e0b" # Amber for Rings (Priority)
                size = 35 
            elif is_suspicious:
                color = "#ef4444" 
                size = 25
            else:
                color = "#3b82f6" 
                size = 15
            
            suspicion_data = next((item for item in suspicious_accounts if item["account_id"] == node), None)
            
            title_html = f"<b>{node}</b><br>"
            if suspicion_data:
                title_html += f"Score: {suspicion_data['suspicion_score']}<br>"
                title_html += f"Patterns: {', '.join(suspicion_data['detected_patterns'])}"
            else:
                title_html += "Status: Normal"
                
            nodes.append({
                "id": node,
                "label": node,
                "color": color,
                "size": size, 
                "title": title_html
            })
            
        # Edges
        # Vis.js allows multiple edges if needed
        # We emphasize edges that are part of a detected cycle
        for u, v, data in G.edges(data=True):
            edge_color = "rgba(255, 255, 255, 0.2)" # Default faint
            width = 1
            opacity = 0.4
            
            # Check if this edge direction is part of a cycle
            if (u, v) in cycle_edges:
                edge_color = "#f59e0b" # Highlight Cycle Edge
                width = 3
                opacity = 1.0
            
            edges.append({
                "from": u,
                "to": v,
                "arrows": "to",
                "color": {"color": edge_color, "highlight": "#f59e0b", "opacity": opacity},
                "width": width,
                "title": f"Tx: {data.get('transaction_id')}<br>Amount: ${data.get('amount')}<br>Time: {data.get('timestamp')}",
                "label": f"${data.get('amount')}"
            })

        processing_time = (datetime.now() - start_time).total_seconds()
        
        output = {
            "suspicious_accounts": suspicious_accounts,
            "fraud_rings": rings_info,
            "summary": {
                "total_accounts_analyzed": G.number_of_nodes(),
                "suspicious_accounts_flagged": len(suspicious_accounts),
                "fraud_rings_detected": len(rings_info),
                "processing_time_seconds": round(processing_time, 2)
            },
            "graph_visualization": {
                "nodes": nodes,
                "edges": edges
            }
        }
        
        return jsonify(output)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
