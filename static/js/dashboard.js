class DashboardManager {
    constructor() {
        this.state = {
            systemStatus: 'stopped',
            refreshInterval: null,
            refreshMs: 2000,
            monitoringActive: false,
            alertsPage: 0,
            notificationsPage: 0,
            alertsPageSize: 5,
            alertsCache: [],
            lastAlertCount: 0,
            audioEnabled: true,
            alertSoundPlayed: new Set() // Track which alerts have already played sound
        };
        this.init();
        this.initAudioContext();
    }
    
    init() {
        this.setupEventListeners();
        this.setupSidebarNavigation();
        this.initializeRealTime();
        this.startAutoRefresh();
        this.loadDashboard();
        // Set initial button states
        this.updateSystemStatus({ system_running: false });
        setTimeout(() => window.chartManager?.initialize(), 1000);
    }

    initAudioContext() {
        // Create audio context for beep sounds
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) {
            console.warn('Web Audio API not supported:', e);
            this.audioContext = null;
        }
    }

    playBeep(frequency = 800, duration = 200, type = 'sine') {
        if (!this.state.audioEnabled || !this.audioContext) return;
        
        try {
            // Resume audio context if it's suspended (browser autoplay policy)
            if (this.audioContext.state === 'suspended') {
                this.audioContext.resume();
            }

            const oscillator = this.audioContext.createOscillator();
            const gainNode = this.audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(this.audioContext.destination);
            
            oscillator.frequency.value = frequency;
            oscillator.type = type;
            
            gainNode.gain.setValueAtTime(0.3, this.audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + duration / 1000);
            
            oscillator.start(this.audioContext.currentTime);
            oscillator.stop(this.audioContext.currentTime + duration / 1000);
        } catch (e) {
            console.error('Error playing beep:', e);
        }
    }

    playAlertSound(severity = 'medium') {
        // Different beep patterns for different severity levels
        switch (severity.toLowerCase()) {
            case 'critical':
                // Three urgent beeps
                this.playBeep(1000, 150, 'square');
                setTimeout(() => this.playBeep(1000, 150, 'square'), 200);
                setTimeout(() => this.playBeep(1000, 150, 'square'), 400);
                break;
            case 'high':
                // Two warning beeps
                this.playBeep(900, 200, 'sine');
                setTimeout(() => this.playBeep(900, 200, 'sine'), 250);
                break;
            case 'medium':
                // Single medium beep
                this.playBeep(800, 250, 'sine');
                break;
            case 'low':
                // Soft single beep
                this.playBeep(600, 200, 'triangle');
                break;
            default:
                this.playBeep(800, 200, 'sine');
        }
    }

    setupEventListeners() {
        // System controls
        document.getElementById('start-btn')?.addEventListener('click', () => this.startMonitoring());
        document.getElementById('stop-btn')?.addEventListener('click', () => this.stopMonitoring());
        document.getElementById('refresh-btn')?.addEventListener('click', () => this.loadDashboard());
        
        // Settings
        document.getElementById('auto-refresh-toggle')?.addEventListener('change', (e) => {
            e.target.checked ? this.startAutoRefresh() : this.stopAutoRefresh();
        });
        
        document.getElementById('refresh-rate')?.addEventListener('change', (e) => {
            this.refreshMs = parseInt(e.target.value);
            if (this.state.refreshInterval) {
                this.stopAutoRefresh();
                this.startAutoRefresh();
            }
        });
        
        // Audio alert toggle
        document.getElementById('audio-alert-toggle')?.addEventListener('change', (e) => {
            this.state.audioEnabled = e.target.checked;
            this.showToast(
                this.state.audioEnabled ? 'Audio alerts enabled' : 'Audio alerts disabled',
                'info'
            );
        });
        
        // Mark all notifications as read
        document.getElementById('mark-all-read-btn')?.addEventListener('click', () => {
            this.markAllNotificationsAsRead();
        });
        
        // Task form
        document.getElementById('task-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleTaskSubmit();
        });
        
        // Mobile menu
        document.getElementById('mobile-menu-btn')?.addEventListener('click', () => {
            document.getElementById('sidebar')?.classList.toggle('active');
        });
        
        // MySQL Export
        document.getElementById('download-metrics-db-btn')?.addEventListener('click', () => {
            this.exportMySQL();
        });
        
        // Settings dropdown toggle
        document.getElementById('settings-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const dropdown = document.getElementById('settings-dropdown');
            dropdown?.classList.toggle('active');
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const dropdown = document.getElementById('settings-dropdown');
            const settingsBtn = document.getElementById('settings-btn');
            if (dropdown && !dropdown.contains(e.target) && e.target !== settingsBtn) {
                dropdown.classList.remove('active');
            }
        });
        
        // Sidebar section headers (Main, Tools, Settings) - scroll to top of dashboard
        document.querySelectorAll('.sidebar .nav-title').forEach(title => {
            title.style.cursor = 'pointer';
            title.addEventListener('click', (e) => {
                e.preventDefault();
                const topEl = document.getElementById('dashboard-section');
                if (topEl) topEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });
    }

    initializeRealTime() {
        if (typeof RealTimeManager !== 'undefined') {
            this.realtimeManager = new RealTimeManager();
            this.realtimeManager.on('metrics_update', (data) => this.updateMetrics(data));
            this.realtimeManager.on('system_status', (data) => this.updateSystemStatus(data));
            this.realtimeManager.on('connected', () => this.updateConnectionStatus(true));
            this.realtimeManager.on('disconnected', () => this.updateConnectionStatus(false));
        }
    }

    setupSidebarNavigation() {
        const sectionMap = {
            'dashboard': 'dashboard-section',
            'tasks': 'tasks-section',
            'analytics': 'analytics-section',
            'monitoring': 'monitoring-section',
            'alerts': 'dashboard-section',
            'processes': 'dashboard-section',
            'application-history': 'application-history-section',
            'preferences': 'dashboard-section'
        };

        const navItems = document.querySelectorAll('.sidebar .nav-item[data-section]');
        navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const sectionKey = item.getAttribute('data-section');
                const targetId = sectionMap[sectionKey];
                if (!targetId) return;

                // Update active state
                document.querySelectorAll('.sidebar .nav-item').forEach(el => el.classList.remove('active'));
                item.classList.add('active');

                // Show only the selected section
                document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
                const targetEl = document.getElementById(targetId);
                if (targetEl) targetEl.classList.add('active');

                // Update header title
                const titleMap = {
                    'dashboard': 'Dashboard',
                    'tasks': 'Task Manager',
                    'analytics': 'Analytics',
                    'monitoring': 'System Monitor',
                    'alerts': 'Alerts',
                    'processes': 'Processes',
                    'application-history': 'Application History',
                    'preferences': 'Preferences'
                };
                const subtitleMap = {
                    'dashboard': 'System overview and real-time monitoring',
                    'tasks': 'Create and manage tasks',
                    'analytics': 'Aggregated insights and trends',
                    'monitoring': 'Live system metrics and charts',
                    'alerts': 'Active alerts and statuses',
                    'processes': 'Top processes and open files',
                    'application-history': 'History of applications used during monitoring',
                    'preferences': 'Customize dashboard behavior'
                };
                const pageTitle = document.getElementById('page-title');
                const pageSubtitle = document.getElementById('page-subtitle');
                if (pageTitle) pageTitle.textContent = titleMap[sectionKey] || 'Dashboard';
                if (pageSubtitle) pageSubtitle.textContent = subtitleMap[sectionKey] || subtitleMap['dashboard'];

                // Load data for the selected section
                if (sectionKey === 'analytics') {
                    this.loadAnalyticsForAlt();
                } else if (sectionKey === 'monitoring') {
                    this.loadMonitoringForAlt();
                } else if (sectionKey === 'application-history') {
                    this.loadApplicationHistory();
                }
            });
        });
    }

    async loadAnalyticsForAlt() {
        const data = await this.fetchAPI('/api/analytics');
        if (!data?.success) return;
        const analytics = data.analytics || {};
        const html = `
            <div class="analytics-grid">
                <div class="stat-card">
                    <h4>Task Analytics</h4>
                    <div class="stat-value">${analytics.tasks?.total_tasks || 0}</div>
                    <div class="stat-label">Total Tasks</div>
                </div>
                <div class="stat-card">
                    <h4>Alert Analytics</h4>
                    <div class="stat-value">${analytics.alerts?.total_alerts || 0}</div>
                    <div class="stat-label">Total Alerts</div>
                </div>
            </div>
        `;
        this.updateElement('analytics-content-alt', html);
    }

    async loadMonitoringForAlt() {
        const metrics = await this.fetchAPI('/api/metrics');
        if (metrics?.success) {
            const m = metrics.metrics || {};
            const cpu = m.cpu_stats?.current || 0;
            const mem = m.memory_stats?.current || 0;
            this.updateElement('cpu-metric-alt', `${cpu.toFixed(1)}%`);
            this.updateElement('memory-metric-alt', `${mem.toFixed(1)}%`);
            this.updateElement('datapoints-metric-alt', (m.data_points || 0).toString());
        }
        const procs = await this.fetchAPI('/api/processes?limit=10');
        if (procs?.success) {
            const html = `
                <table class="table">
                    <thead><tr><th>PID</th><th>Name</th><th>CPU%</th><th>Memory%</th></tr></thead>
                    <tbody>
                        ${(procs.processes || []).map(p => `
                            <tr>
                                <td>${p.pid || 'N/A'}</td>
                                <td>${p.name || 'Unknown'}</td>
                                <td>${(p.cpu_percent || 0).toFixed(1)}%</td>
                                <td>${(p.memory_percent || 0).toFixed(1)}%</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            this.updateElement('processes-content-alt', html);
        }
    }

    async loadApplicationHistory() {
        const data = await this.fetchAPI('/api/application_history');
        if (data?.success) {
            const sessions = data.sessions || [];
            if (sessions.length === 0) {
                this.updateElement('application-history-content', `
                    <div class="empty-state">
                        <i class="fas fa-history fa-3x"></i>
                        <h3>No Application History</h3>
                        <p>Start monitoring to track applications used in your system.</p>
                    </div>
                `);
                return;
            }

            let html = '<div class="application-history-container">';
            
            for (const session of sessions) {
                html += `
                    <div class="session-card">
                        <div class="session-header">
                            <h4>Monitoring Session: ${session.session_id}</h4>
                            <span class="session-time">${session.start_time ? new Date(session.start_time).toLocaleString() : 'Unknown time'}</span>
                        </div>
                        <div class="session-content">
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>PID</th>
                                        <th>CPU%</th>
                                        <th>Memory%</th>
                                        <th>Start Time</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${(session.applications || []).map(app => `
                                        <tr>
                                            <td>${app.name || 'Unknown'}</td>
                                            <td>${app.pid || 'N/A'}</td>
                                            <td>${(app.cpu_usage || 0).toFixed(1)}%</td>
                                            <td>${(app.memory_usage || 0).toFixed(1)}%</td>
                                            <td>${app.start_time ? new Date(app.start_time).toLocaleTimeString() : 'Unknown'}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }
            
            html += '</div>';
            this.updateElement('application-history-content', html);
        } else {
            this.updateElement('application-history-content', `
                <div class="error-state">
                    <i class="fas fa-exclamation-circle fa-3x"></i>
                    <h3>Error Loading History</h3>
                    <p>Failed to load application history: ${data?.error || 'Unknown error'}</p>
                </div>
            `);
        }
    }

    // Dark mode methods removed

    startAutoRefresh() {
        this.stopAutoRefresh();
        this.state.refreshInterval = setInterval(() => {
            this.loadMetrics();
            this.loadAlerts();
            this.loadAnalytics();
            this.loadProcesses();
        }, this.state.refreshMs);
    }
    
    stopAutoRefresh() {
        if (this.state.refreshInterval) {
            clearInterval(this.state.refreshInterval);
            this.state.refreshInterval = null;
        }
    }

    async loadDashboard() {
        await Promise.all([
            this.loadSystemStatus(),
            this.loadMetrics(),
            this.loadAlerts(),
            this.loadNotifications(), // Add this line
            this.loadAnalytics(),
            this.loadProcesses()
        ]);
    }

    // API Calls
    async fetchAPI(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: { 'Content-Type': 'application/json' },
                cache: 'no-store',
                ...options
            });
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            return { success: false, error: error.message };
        }
    }

    async loadSystemStatus() {
        const data = await this.fetchAPI('/api/status');
        if (data) this.updateSystemStatus(data);
    }

    async loadMetrics() {
        const data = await this.fetchAPI('/api/metrics');
        if (data?.success) this.updateMetrics(data);
    }

    async loadAlerts() {
        const data = await this.fetchAPI('/api/alerts');
        if (data?.success) this.updateAlerts(data);
    }

    async loadNotifications() {
        const data = await this.fetchAPI('/api/notifications');
        if (data?.success) this.updateNotifications(data);
    }

    async loadAnalytics() {
        const data = await this.fetchAPI('/api/analytics');
        if (data?.success) this.updateAnalytics(data);
    }

    async loadProcesses() {
        const data = await this.fetchAPI('/api/processes?limit=10');
        if (data?.success) this.updateProcesses(data.processes);
    }

    // Update UI
    updateSystemStatus(data) {
        const isRunning = data?.system_running || false;
        this.state.systemStatus = isRunning ? 'running' : 'stopped';
        this.state.monitoringActive = isRunning;
        
        // Update status text
        document.querySelectorAll('[id$="-status-text"]').forEach(el => {
            el.textContent = isRunning ? 'System Running' : 'System Stopped';
        });
        
        // Update status dots
        document.querySelectorAll('.status-dot').forEach(dot => {
            dot.className = `status-dot status-${isRunning ? 'running' : 'stopped'}`;
        });
        
        // Update status pills
        document.querySelectorAll('.status-pill').forEach(pill => {
            const dot = pill.querySelector('.status-dot');
            const text = pill.querySelector('span');
            if (dot && text) {
                dot.className = `status-dot status-${isRunning ? 'running' : 'stopped'}`;
                text.textContent = isRunning ? 'System Running' : 'System Stopped';
            }
        });
        
        // Update control buttons state
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        if (startBtn && stopBtn) {
            if (isRunning) {
                startBtn.disabled = true;
                stopBtn.disabled = false;
                startBtn.classList.add('btn-disabled');
                stopBtn.classList.remove('btn-disabled');
            } else {
                startBtn.disabled = false;
                stopBtn.disabled = true;
                startBtn.classList.remove('btn-disabled');
                stopBtn.classList.add('btn-disabled');
            }
        }
    }

    updateMetrics(data) {
        const metrics = data.metrics || {};
        const cpu = metrics.cpu_stats?.current || 0;
        const memory = metrics.memory_stats?.current || 0;
        
        // Update overview cards
        this.updateElement('cpu-metric', `${cpu.toFixed(1)}%`);
        this.updateElement('memory-metric', `${memory.toFixed(1)}%`);
        this.updateElement('datapoints-metric', (metrics.data_points || 0).toString());
        
        // Update progress rings
        this.updateProgressRing('cpu-progress', cpu);
        this.updateProgressRing('memory-progress', memory);
        
        // Update detailed metrics
        const content = `
            <div class="metric-grid">
                <div class="metric-item">
                    <span>CPU: ${cpu.toFixed(1)}%</span>
                    <div class="progress-bar" style="width:${cpu}%;background:${this.getColor(cpu)}"></div>
                </div>
                <div class="metric-item">
                    <span>Memory: ${memory.toFixed(1)}%</span>
                    <div class="progress-bar" style="width:${memory}%;background:${this.getColor(memory)}"></div>
                </div>
                <div class="metric-item">
                    <span>Data Points: ${metrics.data_points || 0}</span>
                </div>
            </div>
        `;
        this.updateElement('metrics-content', content);
    }

    updateConnectionStatus(connected) {
        const dot = document.querySelector('#connection-status .connection-dot');
        const text = document.querySelector('#connection-status .connection-text');
        if (!dot || !text) return;
        if (connected) {
            dot.classList.remove('disconnected');
            dot.classList.add('connected');
            text.textContent = 'Connected';
        } else {
            dot.classList.remove('connected');
            dot.classList.add('disconnected');
            text.textContent = 'Polling';
        }
    }

    updateAlerts(data) {
        const alerts = data.alerts || [];
        // Cache and clamp page
        this.state.alertsCache = alerts;
        const total = alerts.length;
        const pageSize = this.state.alertsPageSize;
        const maxPage = Math.max(0, Math.ceil(total / pageSize) - 1);
        this.state.alertsPage = Math.min(this.state.alertsPage, maxPage);

        this.updateElement('alerts-metric', total.toString());
        this.updateElement('alerts-badge', total.toString());
        
        // Check for new alerts and play sound
        if (total > this.state.lastAlertCount && this.state.monitoringActive) {
            // New alerts detected, find new ones and play sound
            const newAlerts = alerts.filter(alert => !this.state.alertSoundPlayed.has(alert.id));
            
            if (newAlerts.length > 0) {
                // Find highest severity among new alerts
                let highestNewSeverity = 'low';
                let highestAlert = newAlerts[0];
                const severityOrder = ['low', 'medium', 'high', 'critical'];
                
                newAlerts.forEach(alert => {
                    const severity = (alert.severity || 'low').toLowerCase();
                    if (severityOrder.indexOf(severity) > severityOrder.indexOf(highestNewSeverity)) {
                        highestNewSeverity = severity;
                        highestAlert = alert;
                    }
                    this.state.alertSoundPlayed.add(alert.id);
                    
                    // Show on-screen notification for each new alert
                    this.showAlertNotification(alert);
                });
                
                // Play alert sound for the highest severity
                this.playAlertSound(highestNewSeverity);
                
                // Show browser notification if available
                this.showNotification('New Alert Detected', 
                    `${newAlerts.length} new alert(s) - Severity: ${highestNewSeverity.toUpperCase()}`);
            }
        }
        this.state.lastAlertCount = total;
        
        // Clean up old alert IDs from the sound played set
        const currentAlertIds = new Set(alerts.map(a => a.id));
        for (const id of this.state.alertSoundPlayed) {
            if (!currentAlertIds.has(id)) {
                this.state.alertSoundPlayed.delete(id);
            }
        }
        
        // Update the status badge in the metric card
        const alertsStatus = document.getElementById('alerts-status');
        const alertsMetricCard = document.getElementById('alerts-metric-card');
        
        if (alertsStatus) {
            if (alerts.length === 0) {
                alertsStatus.innerHTML = '<span class="status-badge status-success">All Clear</span>';
                // Remove active alerts styling
                if (alertsMetricCard) {
                    alertsMetricCard.classList.remove('alerts-active');
                }
            } else {
                // Add active alerts styling
                if (alertsMetricCard) {
                    alertsMetricCard.classList.add('alerts-active');
                }
                
                // Find the highest severity alert
                let highestSeverity = 'low';
                const severityOrder = ['low', 'medium', 'high', 'critical'];
                
                alerts.forEach(alert => {
                    const severity = (alert.severity || 'low').toLowerCase();
                    if (severityOrder.indexOf(severity) > severityOrder.indexOf(highestSeverity)) {
                        highestSeverity = severity;
                    }
                });
                
                const severityLabels = {
                    'low': 'Low Risk',
                    'medium': 'Medium Risk',
                    'high': 'High Risk',
                    'critical': 'Critical Risk'
                };
                
                const severityClasses = {
                    'low': 'status-success',
                    'medium': 'status-warning',
                    'high': 'status-danger',
                    'critical': 'status-danger'
                };
                
                alertsStatus.innerHTML = `<span class="status-badge ${severityClasses[highestSeverity]}">${severityLabels[highestSeverity]}</span>`;
            }
        }
        
        if (total === 0) {
            this.updateElement('alerts-content', '<div class="empty-state">No active alerts</div>');
            this.updateAlertsPagination(0, 0);
            return;
        }
        
        const start = this.state.alertsPage * pageSize;
        const slice = alerts.slice(start, start + pageSize);

        const html = slice.map(alert => `
            <div class="alert-item severity-${(alert.severity || 'low').toLowerCase()}">
                <strong>${alert.alert_type || 'Unknown Alert'}</strong>
                <p>${alert.message || 'No message provided'}</p>
                <small>${alert.created_at ? new Date(alert.created_at).toLocaleString() : 'Unknown time'}</small>
            </div>
        `).join('');
        
        this.updateElement('alerts-content', html);
        this.updateAlertsPagination(this.state.alertsPage, maxPage);
        this.bindAlertsPagination();
    }

    bindAlertsPagination() {
        const prevBtn = document.getElementById('alerts-prev');
        const nextBtn = document.getElementById('alerts-next');
        if (prevBtn && !prevBtn._bound) {
            prevBtn._bound = true;
            prevBtn.addEventListener('click', () => {
                if (this.state.alertsPage > 0) {
                    this.state.alertsPage -= 1;
                    this.updateAlerts({ alerts: this.state.alertsCache });
                }
            });
        }
        if (nextBtn && !nextBtn._bound) {
            nextBtn._bound = true;
            nextBtn.addEventListener('click', () => {
                const total = this.state.alertsCache.length;
                const maxPage = Math.max(0, Math.ceil(total / this.state.alertsPageSize) - 1);
                if (this.state.alertsPage < maxPage) {
                    this.state.alertsPage += 1;
                    this.updateAlerts({ alerts: this.state.alertsCache });
                }
            });
        }
    }

    updateAlertsPagination(currentPage, maxPage) {
        const prevBtn = document.getElementById('alerts-prev');
        const nextBtn = document.getElementById('alerts-next');
        const info = document.getElementById('alerts-page-info');
        if (prevBtn) prevBtn.disabled = currentPage <= 0;
        if (nextBtn) nextBtn.disabled = currentPage >= maxPage;
        if (info) info.textContent = `Page ${maxPage >= 0 ? (currentPage + 1) : 0}`;
    }

    updateNotifications(data) {
        const notifications = data.notifications || [];
        // For now, we'll use the same pagination approach as alerts
        const pageSize = this.state.alertsPageSize; // Reuse the same page size
        const maxPage = Math.max(0, Math.ceil(notifications.length / pageSize) - 1);
        const currentPage = this.state.notificationsPage || 0;
        
        if (notifications.length === 0) {
            this.updateElement('notifications-content', '<div class="empty-state">No notifications</div>');
            this.updateNotificationsPagination(0, 0);
            return;
        }
        
        const start = currentPage * pageSize;
        const slice = notifications.slice(start, start + pageSize);

        const html = slice.map(notification => {
            const severity = (notification.severity || 'low').toLowerCase();
            const category = notification.category || 'System';
            const timestamp = notification.timestamp ? new Date(notification.timestamp).toLocaleString() : 'Unknown time';
            const isRead = notification.isRead || false;
            
            return `
                <div class="notification-item ${severity} ${isRead ? 'read' : ''}" data-id="${notification.id}">
                    <div class="notification-item-header">
                        <h4 class="notification-item-title">${notification.message || 'No message provided'}</h4>
                        <span class="notification-item-severity ${severity}">${severity}</span>
                    </div>
                    <div class="notification-item-meta">
                        <span class="notification-item-category">
                            <i class="fas fa-tag"></i>
                            ${category}
                        </span>
                        <span class="notification-item-timestamp">
                            <i class="fas fa-clock"></i>
                            ${timestamp}
                        </span>
                    </div>
                    ${!isRead ? `
                        <div class="notification-item-actions">
                            <button class="mark-as-read-btn" data-id="${notification.id}" title="Mark as read">
                                <i class="fas fa-check"></i>
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');
        
        this.updateElement('notifications-content', html);
        this.updateNotificationsPagination(currentPage, maxPage);
        this.bindNotificationsPagination();
        this.bindMarkAsReadButtons();
    }

    bindNotificationsPagination() {
        // Store reference to 'this' for use in event handlers
        const self = this;
        
        const prevBtn = document.getElementById('notifications-prev');
        const nextBtn = document.getElementById('notifications-next');
        
        if (prevBtn && !prevBtn._bound) {
            prevBtn._bound = true;
            prevBtn.addEventListener('click', function() {
                self.state.notificationsPage = (self.state.notificationsPage || 0) - 1;
                self.loadNotifications();
            });
        }
        
        if (nextBtn && !nextBtn._bound) {
            nextBtn._bound = true;
            nextBtn.addEventListener('click', function() {
                self.state.notificationsPage = (self.state.notificationsPage || 0) + 1;
                self.loadNotifications();
            });
        }
    }

    updateNotificationsPagination(currentPage, maxPage) {
        const prevBtn = document.getElementById('notifications-prev');
        const nextBtn = document.getElementById('notifications-next');
        const info = document.getElementById('notifications-page-info');
        
        if (prevBtn) prevBtn.disabled = currentPage <= 0;
        if (nextBtn) nextBtn.disabled = currentPage >= maxPage;
        if (info) info.textContent = `Page ${maxPage >= 0 ? (currentPage + 1) : 0} of ${maxPage + 1}`;
    }

    bindMarkAsReadButtons() {
        // Store reference to 'this' for use in event handlers
        const self = this;
        
        document.querySelectorAll('.mark-as-read-btn').forEach(button => {
            if (!button._bound) {
                button._bound = true;
                button.addEventListener('click', async function(e) {
                    e.stopPropagation();
                    const id = this.getAttribute('data-id');
                    await self.markNotificationAsRead(id);
                });
            }
        });
    }

    async markNotificationAsRead(id) {
        try {
            const data = await this.fetchAPI(`/api/notifications/${id}/read`, { method: 'POST' });
            if (data.success) {
                // Reload notifications to reflect the change
                this.loadNotifications();
            } else {
                this.showToast('Failed to mark notification as read', 'danger');
            }
        } catch (error) {
            console.error('Error marking notification as read:', error);
            this.showToast('Error marking notification as read', 'danger');
        }
    }

    async markAllNotificationsAsRead() {
        try {
            const data = await this.fetchAPI('/api/notifications/mark_all_read', { method: 'POST' });
            if (data.success) {
                this.showToast('All notifications marked as read', 'success');
                // Reload notifications to reflect the change
                this.loadNotifications();
            } else {
                this.showToast('Failed to mark all notifications as read', 'danger');
            }
        } catch (error) {
            console.error('Error marking all notifications as read:', error);
            this.showToast('Error marking all notifications as read', 'danger');
        }
    }

    updateAnalytics(data) {
        const analytics = data.analytics || {};
        const tasks = analytics.tasks || {};
        const alerts = analytics.alerts || {};
        
        const html = `
            <div class="analytics-grid">
                <div class="stat-card">
                    <h4>Task Analytics</h4>
                    <div class="stat-value">${tasks.total_tasks || 0}</div>
                    <div class="stat-label">Total Tasks</div>
                </div>
                <div class="stat-card">
                    <h4>Alert Analytics</h4>
                    <div class="stat-value">${alerts.total_alerts || 0}</div>
                    <div class="stat-label">Total Alerts</div>
                </div>
            </div>
            <div class="realtime-tag">🔄 Auto-updating every ${this.refreshMs/1000}s</div>
        `;
        
        this.updateElement('analytics-content', html);
    }

    updateProcesses(processes) {
        if (!processes || processes.length === 0) {
            this.updateElement('processes-content', '<div class="empty-state">No processes found</div>');
            return;
        }
        
        const html = `
            <table class="table">
                <thead><tr><th>PID</th><th>Name</th><th>CPU%</th><th>Memory%</th></tr></thead>
                <tbody>
                    ${processes.map(p => `
                        <tr>
                            <td>${p.pid || 'N/A'}</td>
                            <td>${p.name || 'Unknown'}</td>
                            <td>${(p.cpu_percent || 0).toFixed(1)}%</td>
                            <td>${(p.memory_percent || 0).toFixed(1)}%</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        
        this.updateElement('processes-content', html);
    }

    // System Controls
    async startMonitoring() {
        // Update UI immediately to show action is in progress
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        if (startBtn) {
            startBtn.disabled = true;
            startBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
        }
        
        try {
            const data = await this.fetchAPI('/api/start_monitoring', { method: 'POST' });
            if (data.success) {
                this.showToast('Monitoring started', 'success');
                this.state.monitoringActive = true;
                // Update button states
                if (startBtn && stopBtn) {
                    startBtn.disabled = true;
                    stopBtn.disabled = false;
                    startBtn.innerHTML = '<i class="fas fa-play"></i> Start Monitoring';
                    startBtn.classList.add('btn-disabled');
                    stopBtn.classList.remove('btn-disabled');
                }
                this.loadDashboard();
            } else {
                this.showToast('Failed to start monitoring: ' + (data.message || 'Unknown error'), 'danger');
                // Reset button states on failure
                if (startBtn && stopBtn) {
                    startBtn.disabled = false;
                    stopBtn.disabled = true;
                    startBtn.innerHTML = '<i class="fas fa-play"></i> Start Monitoring';
                    startBtn.classList.remove('btn-disabled');
                    stopBtn.classList.add('btn-disabled');
                }
            }
        } catch (error) {
            this.showToast('Error starting monitoring: ' + error.message, 'danger');
            // Reset button states on error
            if (startBtn && stopBtn) {
                startBtn.disabled = false;
                stopBtn.disabled = true;
                startBtn.innerHTML = '<i class="fas fa-play"></i> Start Monitoring';
                startBtn.classList.remove('btn-disabled');
                stopBtn.classList.add('btn-disabled');
            }
        }
    }

    async stopMonitoring() {
        // Update UI immediately to show action is in progress
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        if (stopBtn) {
            stopBtn.disabled = true;
            stopBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping...';
        }
        
        try {
            const data = await this.fetchAPI('/api/stop_monitoring', { method: 'POST' });
            if (data.success) {
                this.showToast('Monitoring stopped', 'success');
                this.state.monitoringActive = false;
                // Update button states
                if (startBtn && stopBtn) {
                    startBtn.disabled = false;
                    stopBtn.disabled = true;
                    stopBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Monitoring';
                    startBtn.classList.remove('btn-disabled');
                    stopBtn.classList.add('btn-disabled');
                }
            } else {
                this.showToast('Failed to stop monitoring: ' + (data.message || 'Unknown error'), 'danger');
                // Reset button states on failure
                if (startBtn && stopBtn) {
                    startBtn.disabled = false;
                    stopBtn.disabled = true;
                    stopBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Monitoring';
                    startBtn.classList.remove('btn-disabled');
                    stopBtn.classList.add('btn-disabled');
                }
            }
        } catch (error) {
            this.showToast('Error stopping monitoring: ' + error.message, 'danger');
            // Reset button states on error
            if (startBtn && stopBtn) {
                startBtn.disabled = false;
                stopBtn.disabled = true;
                stopBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Monitoring';
                startBtn.classList.remove('btn-disabled');
                stopBtn.classList.add('btn-disabled');
            }
        }
    }

    async handleTaskSubmit() {
        const taskData = {
            name: document.getElementById('task-name')?.value || '',
            description: document.getElementById('task-desc')?.value || '',
            command: document.getElementById('task-cmd')?.value || ''
        };
        
        if (!taskData.name.trim()) {
            this.showToast('Task name required', 'warning');
            return;
        }
        
        const data = await this.fetchAPI('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });
        
        if (data.success) {
            this.showToast('Task created', 'success');
            document.getElementById('task-form')?.reset();
        }
    }

    async exportMySQL() {
        try {
            const hours = document.getElementById('mysql-export-hours')?.value || '24';
            const url = `/api/export_metrics_mysql?hours=${encodeURIComponent(hours)}&t=${Date.now()}`;
            
            // Create a temporary link to trigger download
            const link = document.createElement('a');
            link.href = url;
            link.download = `jarm_metrics_${hours}h.sql`;
            link.style.display = 'none';
            
            // Add to DOM, click and remove
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.showToast('MySQL export started', 'success');
        } catch (error) {
            console.error('Export error:', error);
            this.showToast('Export failed: ' + error.message, 'danger');
        }
    }

    getFileIcon(extension) {
        const iconMap = {
            '.py': 'code',
            '.js': 'code',
            '.html': 'code',
            '.css': 'code',
            '.json': 'code',
            '.md': 'book',
            '.txt': 'alt',
            '.pdf': 'pdf',
            '.jpg': 'image',
            '.png': 'image',
            '.gif': 'image',
            '.svg': 'image',
            '.zip': 'archive',
            '.rar': 'archive',
            '.7z': 'archive'
        };
        return iconMap[extension] || 'alt';
    }

    // Utilities
    updateElement(id, content) {
        const el = document.getElementById(id);
        if (el) el.innerHTML = content;
    }

    updateProgressRing(id, percentage) {
        const el = document.getElementById(id);
        if (!el) return;
        const offset = 163 - (percentage / 100) * 163;
        el.style.strokeDashoffset = offset;
        el.style.stroke = this.getColor(percentage);
    }

    getColor(value) {
        if (value > 80) return '#ef4444';
        if (value > 60) return '#f59e0b';
        return '#10b981';
    }

    showToast(message, type = 'info') {
        // Check if toast container exists
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }

    showNotification(title, body) {
        // Check if browser supports notifications
        if (!('Notification' in window)) {
            console.log('Browser does not support notifications');
            return;
        }

        // Check if permission is already granted
        if (Notification.permission === 'granted') {
            new Notification(title, { body, icon: '/static/favicon.ico' });
        }
        // Otherwise, request permission
        else if (Notification.permission !== 'denied') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    new Notification(title, { body, icon: '/static/favicon.ico' });
                }
            });
        }
    }

    showAlertNotification(alert) {
        // Create on-screen alert notification
        const container = document.getElementById('toast-container');
        if (!container) return;

        const severity = (alert.severity || 'medium').toLowerCase();
        const alertType = alert.alert_type || alert.type || 'System Alert';
        const message = alert.message || 'An alert has been detected';
        const source = alert.source || 'System Monitor';
        const timestamp = alert.created_at ? new Date(alert.created_at).toLocaleTimeString() : new Date().toLocaleTimeString();

        // Icon based on severity
        const icons = {
            low: '🟢',
            medium: '🟡',
            high: '🟠',
            critical: '🔴'
        };

        const icon = icons[severity] || '⚠️';

        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert-notification severity-${severity}`;
        notification.innerHTML = `
            <div class="alert-notification-icon">${icon}</div>
            <div class="alert-notification-content">
                <div class="alert-notification-header">
                    <h4 class="alert-notification-title">${alertType}</h4>
                </div>
                <span class="alert-notification-severity">${severity}</span>
                <p class="alert-notification-message">${message}</p>
                <div class="alert-notification-meta">
                    <span class="alert-notification-source">
                        <i class="fas fa-server"></i>
                        ${source}
                    </span>
                    <span class="alert-notification-time">
                        <i class="fas fa-clock"></i>
                        ${timestamp}
                    </span>
                </div>
            </div>
            <button class="alert-notification-close" aria-label="Close notification">
                <i class="fas fa-times"></i>
            </button>
        `;

        // Add to container
        container.appendChild(notification);

        // Close button handler
        const closeBtn = notification.querySelector('.alert-notification-close');
        closeBtn.addEventListener('click', () => {
            notification.style.animation = 'slideOutRight 0.3s ease-out forwards';
            setTimeout(() => notification.remove(), 300);
        });

        // Auto-remove based on severity
        const durations = {
            low: 5000,
            medium: 7000,
            high: 10000,
            critical: 15000
        };

        const duration = durations[severity] || 7000;

        setTimeout(() => {
            if (notification.parentElement) {
                notification.style.animation = 'slideOutRight 0.3s ease-out forwards';
                setTimeout(() => notification.remove(), 300);
            }
        }, duration);
    }
}

// Initialize dashboard
let dashboardManager;
document.addEventListener('DOMContentLoaded', () => {
    dashboardManager = new DashboardManager();
    document.body.classList.remove('loading');
    document.getElementById('loading-screen').style.display = 'none';
});
