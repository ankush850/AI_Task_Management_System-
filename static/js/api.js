/**
 * JARM API Client - Optimized
 */

class APIClient {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
    }

    async request(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                headers: { 'Content-Type': 'application/json', ...options.headers },
                cache: 'no-store',
                ...options
            });
            
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
            return data;
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    }

    // System
    getStatus() { return this.request('/api/status'); }
    startMonitoring() { return this.request('/api/start_monitoring', { method: 'POST' }); }
    stopMonitoring() { return this.request('/api/stop_monitoring', { method: 'POST' }); }

    // Tasks
    getTasks(limit = 50) { return this.request(`/api/tasks?limit=${limit}`); }
    createTask(data) { return this.request('/api/tasks', { method: 'POST', body: JSON.stringify(data) }); }

    // Metrics & Analytics
    getMetrics(hours = 24) { return this.request(`/api/metrics?hours=${hours}`); }
    getAlerts() { return this.request('/api/alerts'); }
    getAnalytics(days = 30) { return this.request(`/api/analytics?days=${days}`); }
}

const api = new APIClient();
window.api = api;
