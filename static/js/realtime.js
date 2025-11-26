/**
 * JARM Real-Time WebSocket - Optimized
 */

class RealTimeManager {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.listeners = {};
        this.init();
    }
    
    init() {
        this.connect();
    }
    
    connect() {
        try {
            this.socket = io({ transports: ['websocket', 'polling'] });
            this.setupHandlers();
        } catch (error) {
            console.error('WebSocket failed:', error);
        }
    }
    
    setupHandlers() {
        this.socket.on('connect', () => {
            this.connected = true;
            this.socket.emit('join_monitoring');
            this.emit('connected');
        });
        
        this.socket.on('disconnect', () => {
            this.connected = false;
            this.emit('disconnected');
        });
        
        this.socket.on('system_status', (data) => this.emit('system_status', data));
        this.socket.on('metrics_update', (data) => this.emit('metrics_update', data));
        this.socket.on('alert_notification', (data) => this.emit('alert_notification', data));
    }
    
    on(event, callback) {
        if (!this.listeners[event]) this.listeners[event] = [];
        this.listeners[event].push(callback);
    }
    
    emit(event, data) {
        (this.listeners[event] || []).forEach(cb => cb(data));
    }
}
