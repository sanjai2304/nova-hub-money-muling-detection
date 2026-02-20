<<<<<<< HEAD
# nova-hub-money-muling-detection
Graph-based financial crime detection system that uncovers money muling rings using cycle detection, temporal analysis, and network-based anomaly scoring.
=======
# Money Muling Detection Engine - Nova Hub

**Team Name:** Nova Hub  
**Project:** Graph-Based Financial Crime Detection  
**Event:** 24-Hour Hackathon

## 🚀 Overview
The Money Muling Detection Engine is a production-ready web application designed to identify financial fraud patterns, specifically money muling rings. It processes transaction data (CSV), constructs a directed graph, and applies graph theory algorithms to detect suspicious activities like Circular Routing, Smurfing, and Layered Shell Accounts.
TEAM MEMBERS
Mahesh Rajan MD
Sree Akshya S
Priya Dharshini B

## 🛠 Tech Stack
- **Backend:** Python, Flask, NetworkX, Pandas
- **Frontend:** HTML5, CSS3 (Glassmorphism), Vanilla JS
- **Visualization:** Vis.js
- **Deployment:** Render-compatible (Gunicorn)

## 📂 Project Structure
```
money muling 2.0/
├── app.py              # Flask Backend & Logic
├── requirements.txt    # Python Dependencies
├── templates/
│   └── index.html      # Frontend HTML
├── static/
│   ├── css/
│   │   └── styles.css  # Custom Styling
│   └── js/
│       └── main.js     # Frontend Logic & Graph Rendering
└── README.md           # Documentation
```

## 🧠 Fraud Detection Algorithms

### 1. Circular Fund Routing (Cycles)
- **Logic:** Detects directed cycles of length 3 to 5.
- **Algorithm:** Depth-Limited DFS.
- **Complexity:** O(V * d^k), where V is nodes, d is average degree, k is depth (5). Optimized for sparse financial graphs.
- **Scoring:** +40 Risk Score.

### 2. Smurfing (Fan-In / Fan-Out)
- **Fan-In:** 10+ distinct senders to 1 receiver within 72 hours.
- **Fan-Out:** 1 sender to 10+ distinct receivers within 72 hours.
- **Algorithm:** Temporal grouping and sliding window check.
- **Complexity:** O(N log N) for sorting transactions.
- **Scoring:** +25 Risk Score each.

### 3. Layered Shell Accounts
- **Logic:** Intermediate accounts (In-degree > 0, Out-degree > 0) with low total activity (Total degree ≤ 3).
- **Complexity:** O(V).
- **Scoring:** +20 Risk Score.

### 4. High Velocity
- **Logic:** Accounts involved in bursts of 5+ transactions within 72 hours.
- **Scoring:** +10 Risk Score.

## 📊 Suspicion Scoring Model
Accounts are scored from 0-100 based on the detected patterns.
- **Risk Score** = min(100, Σ Pattern Scores)
- Accounts are sorted by descending risk score.

## ⚡ Setup & Run

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Application:**
   ```bash
   python app.py
   ```

3. **Access:**
   Open `http://localhost:5000` in your browser.

## 📝 Input Format (CSV)
Required columns:
- `transaction_id`, `sender_id`, `receiver_id`, `amount`, `timestamp`

## 🔮 Future Improvements
- Real-time stream processing with Kafka.
- GNN (Graph Neural Networks) for anomaly detection.
- Louvain Community Detection for larger rings.
>>>>>>> 698e3a9 (feat: Initialize money muling detection application with core Flask structure, static assets, templates, and sample transaction data.)
