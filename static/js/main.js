document.addEventListener('DOMContentLoaded', () => {
    // Safety check for Vis.js library
    if (typeof vis === 'undefined') {
        alert("CRITICAL ERROR: 'vis-network' library failed to load.\n\nPossible fixes:\n1. Check internet connection.\n2. Disable AdBlock/extensions.\n3. Hard Refresh (Ctrl+F5).");
        return;
    }

    // Splash Screen Logic
    setTimeout(() => {
        const splash = document.getElementById('splash-screen');
        if (splash) {
            splash.style.opacity = '0';
            splash.style.visibility = 'hidden';
            setTimeout(() => splash.remove(), 800);
        }
    }, 2500);
    // -------------------------------------------------------------
    // ELEMENTS
    // -------------------------------------------------------------
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('csvFile');
    const analyzeBtn = document.getElementById('analyzeBtn');

    // Panels & Views
    const statsPanel = document.getElementById('statsPanel');
    const resultsPanel = document.getElementById('resultsPanel');
    const loader = document.getElementById('loader');
    const emptyState = document.getElementById('emptyState');

    // Stats Fields
    const totalAccountsEl = document.getElementById('totalAccounts');
    const suspiciousFlaggedEl = document.getElementById('suspiciousFlagged');
    const ringsDetectedEl = document.getElementById('ringsDetected');
    const procTimeEl = document.getElementById('procTime');

    // Tables
    const suspiciousTable = document.querySelector('#suspiciousTable tbody');
    const fraudRingsTable = document.querySelector('#fraudRingsTable tbody');

    // State
    let network = null;
    let analysisData = null;

    // -------------------------------------------------------------
    // 1. UPLOAD HANDLING
    // -------------------------------------------------------------
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

    dropArea.addEventListener('drop', handleDrop, false);
    dropArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFiles);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles({ target: { files: files } });
    }

    function handleFiles(e) {
        const file = e.target.files[0];
        if (file && file.name.endsWith('.csv')) {
            document.querySelector('.file-msg').textContent = file.name;
            analyzeBtn.disabled = false;
        } else {
            alert('Please upload a valid CSV file.');
        }
    }

    // -------------------------------------------------------------
    // 2. ANALYZE ACTION
    // -------------------------------------------------------------
    analyzeBtn.addEventListener('click', async () => {
        const file = fileInput.files[0];
        if (!file) return;

        // UI Reset
        loader.classList.remove('hidden');
        analyzeBtn.disabled = true;
        emptyState.classList.add('hidden');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Analysis failed');
            }

            analysisData = await response.json();
            renderDashboard(analysisData);

        } catch (error) {
            console.error(error);
            alert('Error: ' + error.message);
        } finally {
            loader.classList.add('hidden');
            analyzeBtn.disabled = false;
        }
    });

    // -------------------------------------------------------------
    // 3. RENDER DASHBOARD
    // -------------------------------------------------------------
    function renderDashboard(data) {
        // Stats
        totalAccountsEl.textContent = data.summary.total_accounts_analyzed;
        suspiciousFlaggedEl.textContent = data.summary.suspicious_accounts_flagged;
        ringsDetectedEl.textContent = data.summary.fraud_rings_detected;
        procTimeEl.textContent = data.summary.processing_time_seconds;

        // Show Panels
        statsPanel.classList.remove('hidden');
        resultsPanel.classList.remove('hidden');

        // Render Tables
        renderSuspiciousTable(data.suspicious_accounts);
        renderRingsTable(data.fraud_rings);

        // Render Graph
        renderGraph(data.graph_visualization);
    }

    function renderSuspiciousTable(accounts) {
        suspiciousTable.innerHTML = '';
        accounts.forEach(acc => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span class="mono-font">${acc.account_id}</span></td>
                <td style="color: ${getScoreColor(acc.suspicion_score)}">${acc.suspicion_score}</td>
                <td>${acc.detected_patterns.join(', ')}</td>
                <td>${acc.ring_id || '-'}</td>
            `;
            // Click to iterate focus
            tr.addEventListener('click', () => {
                focusNode(acc.account_id);
            });
            tr.style.cursor = "pointer";
            suspiciousTable.appendChild(tr);
        });
    }

    function renderRingsTable(rings) {
        fraudRingsTable.innerHTML = '';
        if (rings && rings.length > 0) {
            rings.forEach(ring => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${ring.ring_id}</td>
                    <td>${ring.pattern_type}</td>
                    <td>${ring.member_accounts.length}</td>
                    <td style="color: ${getScoreColor(ring.risk_score)}">${ring.risk_score}</td>
                    <td class="small-text">${ring.member_accounts.join(', ')}</td>
                `;
                tr.addEventListener('click', () => {
                    if (network) {
                        network.selectNodes(ring.member_accounts);
                        network.fit({ nodes: ring.member_accounts, animation: { duration: 1000 } });
                    }
                });
                tr.style.cursor = "pointer";
                fraudRingsTable.appendChild(tr);
            });
        }
    }

    function getScoreColor(score) {
        if (score >= 80) return '#ef4444'; // Red
        if (score >= 50) return '#06b6d4'; // Cyan/Blue
        return '#94a3b8'; // Grey
    }

    // -------------------------------------------------------------
    // 4. VIS.JS GRAPH
    // -------------------------------------------------------------
    function renderGraph(graphData) {
        const container = document.getElementById('networkGraph');
        const nodes = new vis.DataSet(graphData.nodes);
        const edges = new vis.DataSet(graphData.edges);
        const data = { nodes, edges };

        const options = {
            nodes: {
                shape: 'dot',
                size: 20,
                font: { color: '#ffffff', size: 14, face: 'Roboto' },
                borderWidth: 2,
                shadow: true,
                color: {
                    border: '#ffffff',
                    background: '#64748b',
                    highlight: { border: '#06b6d4', background: '#06b6d4' }
                }
            },
            edges: {
                width: 1,
                color: { color: 'rgba(255,255,255,0.2)', highlight: '#06b6d4' },
                arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                smooth: { type: 'continuous' }
            },
            physics: {
                forceAtlas2Based: {
                    gravitationalConstant: -26,
                    centralGravity: 0.005,
                    springLength: 230,
                    springConstant: 0.18
                },
                maxVelocity: 146,
                solver: 'forceAtlas2Based',
                timestep: 0.35,
                stabilization: { iterations: 20 }
            },
            interaction: {
                hover: true,
                hoverConnectedEdges: true,
                selectConnectedEdges: true,
                tooltipDelay: 100,
                keyboard: true,
                zoomView: true
            }
        };

        if (network) network.destroy();
        network = new vis.Network(container, data, options);

        // Initial Zoom Animation
        // Initial Zoom & Professional Float Animation
        network.once("stabilizationIterationsDone", function () {
            network.fit({
                animation: { duration: 1500, easingFunction: "easeOutQuart" }
            });

            // Start Float & Flow Effects
            setTimeout(() => {
                network.setOptions({ physics: { enabled: false } });
                const ids = network.body.nodeIndices;
                ids.forEach(id => { const n = network.body.nodes[id]; if (n) n.baseY = n.y; });

                // Node Float Animation
                network.on("beforeDrawing", (ctx) => {
                    const t = Date.now() / 1000;
                    ids.forEach(id => {
                        const n = network.body.nodes[id];
                        if (!n) return;
                        if (n.selected || n.options.fixed.y) { n.baseY = n.y; return; }
                        const offset = (id.length + (id.charCodeAt(0) || 0)) % 10;
                        n.y = n.baseY + Math.sin(t * 2 + offset) * 3;
                    });
                });

                // Edge Flow Animation (Money moving)
                network.on("afterDrawing", (ctx) => {
                    const t = Date.now() / 1000;
                    const edges = network.body.edges;
                    const nodePos = network.getPositions();

                    ctx.save();
                    for (const edgeId in edges) {
                        const edge = edges[edgeId];
                        const start = nodePos[edge.fromId];
                        const end = nodePos[edge.toId];
                        if (!start || !end) continue;

                        // Particle moving from source to target
                        const speed = 1.0;
                        const offset = (t * speed + (edgeId.length * 0.1)) % 1;

                        const x = start.x + (end.x - start.x) * offset;
                        const y = start.y + (end.y - start.y) * offset;

                        // Draw glowing particle
                        ctx.beginPath();
                        ctx.arc(x, y, 3, 0, 2 * Math.PI);
                        ctx.fillStyle = '#facc15'; // Gold
                        ctx.shadowColor = '#facc15';
                        ctx.shadowBlur = 6;
                        ctx.fill();
                    }
                    ctx.restore();
                });

                function animationLoop() {
                    if (network) network.redraw();
                    requestAnimationFrame(animationLoop);
                }
                animationLoop();

            }, 1800);
        });

        // Events: Click & Hover
        network.on("click", function (params) {
            if (params.nodes.length > 0) {
                showNodeTooltip(params.nodes[0]);
            } else {
                const selected = network.getSelectedNodes();
                if (selected.length === 0) {
                    hideNodeTooltip();
                }
            }
        });

        // Interactive Hover Effects
        network.on("hoverNode", function (params) {
            document.body.style.cursor = 'pointer';
            showNodeTooltip(params.node);
        });

        network.on("blurNode", function (params) {
            document.body.style.cursor = 'default';
            const selected = network.getSelectedNodes();
            if (selected.length > 0) {
                // Revert to selected node details if moved away
                showNodeTooltip(selected[0]);
            } else {
                hideNodeTooltip();
            }
        });
    }

    function focusNode(nodeId) {
        if (network) {
            network.focus(nodeId, {
                scale: 1.2,
                animation: { duration: 1000, easingFunction: "easeInOutQuad" }
            });
            network.selectNodes([nodeId]);
            showNodeTooltip(nodeId);
        }
    }

    // -------------------------------------------------------------
    // 5. TOOLTIP & EXPORT
    // -------------------------------------------------------------
    const tooltip = document.getElementById('nodeTooltip');
    const tooltipId = document.getElementById('tooltipId');
    const tooltipContent = document.getElementById('tooltipContent');

    function showNodeTooltip(nodeId) {
        // Find data
        if (!analysisData) return;

        let acc = analysisData.suspicious_accounts.find(a => a.account_id === nodeId);
        let html = '';

        tooltipId.textContent = nodeId;

        if (acc) {
            html += `
                <div class="tooltip-row"><span class="lbl">Score</span><span class="tooltip-val" style="color:#ef4444">${acc.suspicion_score}</span></div>
                <div class="tooltip-row"><span class="lbl">Patterns</span><span class="tooltip-val">${acc.detected_patterns.join(', ')}</span></div>
                <div class="tooltip-row"><span class="lbl">Ring</span><span class="tooltip-val">${acc.ring_id || 'N/A'}</span></div>
             `;
        } else {
            html += `<div class="tooltip-row"><span class="lbl">Status</span><span class="tooltip-val" style="color:#10b981">Normal</span></div>`;
        }

        tooltipContent.innerHTML = html;
        tooltip.classList.remove('hidden');
    }

    function hideNodeTooltip() {
        tooltip.classList.add('hidden');
    }

    // Export
    document.getElementById('downloadBtn').addEventListener('click', () => {
        if (!analysisData) return;

        // Create filtered object strictly matching the requested format
        const exportData = {
            suspicious_accounts: analysisData.suspicious_accounts,
            fraud_rings: analysisData.fraud_rings,
            summary: analysisData.summary
        };

        const jsonStr = JSON.stringify(exportData, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `fraud_report.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });

    // Panel Toggle
    const toggleBtn = document.getElementById('togglePanelBtn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const panel = document.getElementById('resultsPanel');
            panel.classList.toggle('collapsed');
            const icon = toggleBtn.querySelector('i');
            if (panel.classList.contains('collapsed')) icon.className = 'fa-solid fa-chevron-up';
            else icon.className = 'fa-solid fa-chevron-down';
        });
    }

    // Tabs
    const tabs = document.querySelectorAll('.tab-btn');
    const views = document.querySelectorAll('.view-content');

    tabs.forEach(btn => {
        btn.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            views.forEach(v => v.classList.remove('active'));

            btn.classList.add('active');
            const target = btn.getAttribute('data-target');
            document.getElementById(target).classList.add('active');
        });
    });

    // -------------------------------------------------------------
    // SEARCH FUNCTIONALITY
    // -------------------------------------------------------------
    const searchInput = document.getElementById('searchNode');
    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const term = searchInput.value.trim();
                if (!term) return;

                if (!network) {
                    alert('Please upload a file first.');
                    return;
                }

                const allIds = network.body.data.nodes.getIds();
                let targetId = null;

                // Exact match
                if (allIds.includes(term)) {
                    targetId = term;
                } else {
                    // Case-insensitive
                    const lower = term.toLowerCase();
                    targetId = allIds.find(id => String(id).toLowerCase() === lower);
                }

                if (targetId) {
                    focusNode(targetId);
                    searchInput.value = ''; // Clear or keep?
                    searchInput.blur();
                } else {
                    alert(`Account "${term}" not found.`);
                }
            }
        });
    }

    // -------------------------------------------------------------
    // CUSTOM ZOOM CONTROLS (ANIMATED)
    // -------------------------------------------------------------
    const zIn = document.getElementById('zoomInBtn');
    const zOut = document.getElementById('zoomOutBtn');
    const fit = document.getElementById('fitBtn');

    if (zIn) {
        zIn.addEventListener('click', () => {
            if (network) network.moveTo({ scale: network.getScale() * 1.4, animation: { duration: 400, easingFunction: "easeInOutQuad" } });
        });
    }

    if (zOut) {
        zOut.addEventListener('click', () => {
            if (network) network.moveTo({ scale: network.getScale() * 0.7, animation: { duration: 400, easingFunction: "easeInOutQuad" } });
        });
    }

    if (fit) {
        fit.addEventListener('click', () => {
            if (network) network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
        });
    }

    // -------------------------------------------------------------
    // FULLSCREEN TOGGLE
    // -------------------------------------------------------------
    const fsBtn = document.getElementById('fullscreenBtn');
    if (fsBtn) {
        fsBtn.addEventListener('click', () => {
            const elem = document.querySelector('.graph-wrapper');
            if (!elem) return;

            if (!document.fullscreenElement) {
                elem.requestFullscreen().then(() => {
                    // Wait just a moment for the resize to happen, then animate fit
                    setTimeout(() => {
                        if (network) network.fit({ animation: { duration: 1000, easingFunction: "easeInOutQuad" } });
                    }, 200);
                }).catch(err => {
                    console.error(`Error attempting to enable full-screen mode: ${err.message}`);
                });
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                }
            }
        });

        // Handle resizing on exit
        document.addEventListener('fullscreenchange', () => {
            if (!document.fullscreenElement && network) {
                setTimeout(() => {
                    network.fit({ animation: { duration: 800, easingFunction: "easeInOutQuad" } });
                }, 200);
            }
        });
    }

});
