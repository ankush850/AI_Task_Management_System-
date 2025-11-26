/**
 * JARM Chart Management System
 * Advanced chart visualization for process monitoring and system analytics
 * 
 * Features:
 * - Real-time bar charts for top processes
 * - Gauge charts for system metrics
 * - Pie charts for process distribution
 * - Historical trend line charts
 * - Auto-refresh and manual control
 * 
 * Dependencies: Chart.js, chartjs-adapter-date-fns
 * 
 * @author JARM Development Team
 * @version 2.0.0
 */

class ChartManager {
    constructor() {
        this.charts = {};
        this.currentChartType = 'bar';
        this.autoRefresh = true;
        this.refreshInterval = 5000; // 5 seconds
        this.refreshTimer = null;
        
        this.init();
    }

    init() {
        // Bind event listeners
        this.bindEventListeners();
        
        // Initialize charts after a short delay to ensure DOM is ready
        setTimeout(() => {
            this.initializeCharts();
            this.startAutoRefresh();
        }, 500);
    }

    bindEventListeners() {
        // Chart type buttons
        document.querySelectorAll('.btn-chart').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const chartType = e.target.closest('.btn-chart').dataset.chartType;
                this.switchChart(chartType);
            });
        });

        // Auto refresh toggle
        const autoRefreshToggle = document.getElementById('auto-refresh-charts');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                this.autoRefresh = e.target.checked;
                if (this.autoRefresh) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }

        // Manual refresh button
        const refreshBtn = document.getElementById('refresh-charts-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshCurrentChart();
            });
        }

        // Time range selector for historical chart
        const timeRangeSelector = document.getElementById('time-range-selector');
        if (timeRangeSelector) {
            timeRangeSelector.addEventListener('change', (e) => {
                if (this.currentChartType === 'line') {
                    this.refreshHistoricalChart();
                }
            });
        }
    }

    initializeCharts() {
        this.createBarChart();
        this.createGaugeCharts();
        this.createPieCharts();
        this.createLineChart();
        
        // Load initial data
        this.refreshCurrentChart();
    }

    createBarChart() {
        const ctx = document.getElementById('processes-bar-chart');
        if (!ctx) return;

        this.charts.bar = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Memory Usage (%)',
                    data: [],
                    backgroundColor: 'rgba(59, 130, 246, 0.6)',
                    borderColor: 'rgba(59, 130, 246, 1)',
                    borderWidth: 1,
                    yAxisID: 'y'
                }, {
                    label: 'CPU Usage (%)',
                    data: [],
                    backgroundColor: 'rgba(16, 185, 129, 0.6)',
                    borderColor: 'rgba(16, 185, 129, 1)',
                    borderWidth: 1,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Top Processes Resource Usage'
                    },
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Memory Usage (%)'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'CPU Usage (%)'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                }
            }
        });
    }

    createGaugeCharts() {
        // CPU Gauge
        const cpuCtx = document.getElementById('cpu-gauge-chart');
        if (cpuCtx) {
            this.charts.cpuGauge = new Chart(cpuCtx, {
                type: 'doughnut',
                data: {
                    datasets: [{
                        data: [0, 100],
                        backgroundColor: ['#10b981', '#e5e7eb'],
                        borderWidth: 0,
                        cutout: '85%'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: false }
                    }
                }
            });
        }

        // Memory Gauge
        const memCtx = document.getElementById('memory-gauge-chart');
        if (memCtx) {
            this.charts.memoryGauge = new Chart(memCtx, {
                type: 'doughnut',
                data: {
                    datasets: [{
                        data: [0, 100],
                        backgroundColor: ['#3b82f6', '#e5e7eb'],
                        borderWidth: 0,
                        cutout: '85%'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: false }
                    }
                }
            });
        }

        // Processes Gauge
        const procCtx = document.getElementById('processes-gauge-chart');
        if (procCtx) {
            this.charts.processesGauge = new Chart(procCtx, {
                type: 'doughnut',
                data: {
                    datasets: [{
                        data: [0, 500],
                        backgroundColor: ['#f59e0b', '#e5e7eb'],
                        borderWidth: 0,
                        cutout: '85%'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: false }
                    }
                }
            });
        }
    }

    createPieCharts() {
        // Memory Distribution Pie Chart
        const memPieCtx = document.getElementById('memory-pie-chart');
        if (memPieCtx) {
            this.charts.memoryPie = new Chart(memPieCtx, {
                type: 'pie',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: ['#ef4444', '#f59e0b', '#10b981'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Process Memory Distribution'
                        },
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }

        // CPU Distribution Pie Chart
        const cpuPieCtx = document.getElementById('cpu-pie-chart');
        if (cpuPieCtx) {
            this.charts.cpuPie = new Chart(cpuPieCtx, {
                type: 'pie',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: ['#dc2626', '#ea580c', '#059669'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Process CPU Distribution'
                        },
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }
    }

    createLineChart() {
        const ctx = document.getElementById('metrics-line-chart');
        if (!ctx) return;

        this.charts.line = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'CPU Usage (%)',
                    data: [],
                    borderColor: 'rgba(239, 68, 68, 1)',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    tension: 0.4,
                    fill: false
                }, {
                    label: 'Memory Usage (%)',
                    data: [],
                    borderColor: 'rgba(59, 130, 246, 1)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4,
                    fill: false
                }, {
                    label: 'Active Processes',
                    data: [],
                    borderColor: 'rgba(245, 158, 11, 1)',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Historical System Metrics'
                    },
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                hour: 'HH:mm',
                                day: 'MMM dd'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Time'
                        },
                        ticks: {
                            display: false
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Usage (%)'
                        },
                        min: 0,
                        max: 100
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Process Count'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                }
            }
        });
    }

    switchChart(chartType) {
        // Update button states
        document.querySelectorAll('.btn-chart').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-chart-type="${chartType}"]`).classList.add('active');

        // Hide all chart containers
        document.querySelectorAll('.chart-container').forEach(container => {
            container.classList.remove('active');
        });

        // Show selected chart container
        const targetContainer = document.getElementById(`${chartType}-chart-container`);
        if (targetContainer) {
            targetContainer.classList.add('active');
        }

        this.currentChartType = chartType;
        this.refreshCurrentChart();
    }

    refreshCurrentChart() {
        switch (this.currentChartType) {
            case 'bar':
                this.refreshBarChart();
                break;
            case 'gauge':
                this.refreshGaugeCharts();
                break;
            case 'pie':
                this.refreshPieCharts();
                break;
            case 'line':
                this.refreshHistoricalChart();
                break;
        }
    }

    async refreshBarChart() {
        try {
            const response = await fetch('/api/processes/chart-data?limit=10');
            const data = await response.json();
            
            if (data.success && this.charts.bar) {
                const barData = data.bar_chart;
                this.charts.bar.data.labels = barData.labels;
                this.charts.bar.data.datasets[0].data = barData.memory_data;
                this.charts.bar.data.datasets[1].data = barData.cpu_data;
                this.charts.bar.update();
                
                // Update timestamp
                this.updateLastUpdated('bar-chart-last-updated', data.timestamp);
            }
        } catch (error) {
            console.error('Error refreshing bar chart:', error);
        }
    }

    async refreshGaugeCharts() {
        try {
            const response = await fetch('/api/system/gauge-data');
            const data = await response.json();
            
            if (data.success) {
                // Update CPU gauge
                if (this.charts.cpuGauge) {
                    const cpuValue = data.cpu.value;
                    this.charts.cpuGauge.data.datasets[0].data = [cpuValue, 100 - cpuValue];
                    this.charts.cpuGauge.data.datasets[0].backgroundColor = [data.cpu.color, '#e5e7eb'];
                    this.charts.cpuGauge.update();
                    
                    const cpuValueElement = document.getElementById('cpu-gauge-value');
                    if (cpuValueElement) {
                        cpuValueElement.innerHTML = `${cpuValue.toFixed(1)}%<span>CPU</span>`;
                    }
                }

                // Update Memory gauge
                if (this.charts.memoryGauge) {
                    const memValue = data.memory.value;
                    this.charts.memoryGauge.data.datasets[0].data = [memValue, 100 - memValue];
                    this.charts.memoryGauge.data.datasets[0].backgroundColor = [data.memory.color, '#e5e7eb'];
                    this.charts.memoryGauge.update();
                    
                    const memValueElement = document.getElementById('memory-gauge-value');
                    if (memValueElement) {
                        memValueElement.innerHTML = `${memValue.toFixed(1)}%<span>Memory</span>`;
                    }
                }

                // Update Processes gauge
                if (this.charts.processesGauge) {
                    const procValue = data.processes.value;
                    const procMax = data.processes.max;
                    this.charts.processesGauge.data.datasets[0].data = [procValue, procMax - procValue];
                    this.charts.processesGauge.data.datasets[0].backgroundColor = [data.processes.color, '#e5e7eb'];
                    this.charts.processesGauge.update();
                    
                    const procValueElement = document.getElementById('processes-gauge-value');
                    if (procValueElement) {
                        procValueElement.innerHTML = `${procValue}<span>Processes</span>`;
                    }
                }

                // Update timestamp
                this.updateLastUpdated('gauge-chart-last-updated', data.timestamp);
            }
        } catch (error) {
            console.error('Error refreshing gauge charts:', error);
        }
    }

    async refreshPieCharts() {
        try {
            const response = await fetch('/api/processes/chart-data?limit=20');
            const data = await response.json();
            
            if (data.success && data.pie_chart) {
                // Update Memory pie chart
                if (this.charts.memoryPie) {
                    const memDist = data.pie_chart.memory_distribution;
                    this.charts.memoryPie.data.labels = memDist.labels;
                    this.charts.memoryPie.data.datasets[0].data = memDist.data;
                    this.charts.memoryPie.data.datasets[0].backgroundColor = memDist.colors;
                    this.charts.memoryPie.update();
                }

                // Update CPU pie chart
                if (this.charts.cpuPie) {
                    const cpuDist = data.pie_chart.cpu_distribution;
                    this.charts.cpuPie.data.labels = cpuDist.labels;
                    this.charts.cpuPie.data.datasets[0].data = cpuDist.data;
                    this.charts.cpuPie.data.datasets[0].backgroundColor = cpuDist.colors;
                    this.charts.cpuPie.update();
                }

                // Update timestamp
                this.updateLastUpdated('pie-chart-last-updated', data.timestamp);
            }
        } catch (error) {
            console.error('Error refreshing pie charts:', error);
        }
    }

    async refreshHistoricalChart() {
        try {
            const timeRangeSelector = document.getElementById('time-range-selector');
            const hours = timeRangeSelector ? parseInt(timeRangeSelector.value) : 24;
            
            const response = await fetch(`/api/metrics/historical?hours=${hours}`);
            const data = await response.json();
            
            if (data.success && this.charts.line) {
                const timestamps = data.data.map(item => new Date(item.timestamp));
                
                this.charts.line.data.labels = timestamps;
                this.charts.line.data.datasets[0].data = data.data.map(item => item.cpu);
                this.charts.line.data.datasets[1].data = data.data.map(item => item.memory);
                this.charts.line.data.datasets[2].data = data.data.map(item => item.processes);
                this.charts.line.update();
                
                // Update timestamp
                const now = new Date().toLocaleString();
                this.updateLastUpdated('line-chart-last-updated', now);
            }
        } catch (error) {
            console.error('Error refreshing historical chart:', error);
        }
    }

    updateLastUpdated(elementId, timestamp) {
        const element = document.getElementById(elementId);
        if (element) {
            const date = new Date(timestamp);
            element.textContent = `Last updated: ${date.toLocaleTimeString()}`;
        }
    }

    startAutoRefresh() {
        this.stopAutoRefresh();
        this.refreshTimer = setInterval(() => {
            if (this.autoRefresh) {
                this.refreshCurrentChart();
            }
        }, this.refreshInterval);
    }

    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    destroy() {
        this.stopAutoRefresh();
        Object.values(this.charts).forEach(chart => {
            if (chart && chart.destroy) {
                chart.destroy();
            }
        });
        this.charts = {};
    }
}

// Initialize chart manager when DOM is loaded
let chartManager;
document.addEventListener('DOMContentLoaded', function() {
    chartManager = new ChartManager();
});

// Export for global access
window.ChartManager = ChartManager;