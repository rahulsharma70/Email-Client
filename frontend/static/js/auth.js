/**
 * Authentication Helper for ANAGHA SOLUTION
 * Handles JWT token storage and axios interceptors
 */

// Token management
const AuthManager = {
    getToken: function() {
        return localStorage.getItem('jwt_token') || sessionStorage.getItem('jwt_token');
    },
    
    setToken: function(token, remember = false) {
        if (remember) {
            localStorage.setItem('jwt_token', token);
        } else {
            sessionStorage.setItem('jwt_token', token);
        }
        // Set axios default header
        if (typeof axios !== 'undefined') {
            axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        }
    },
    
    clearToken: function() {
        localStorage.removeItem('jwt_token');
        sessionStorage.removeItem('jwt_token');
        if (typeof axios !== 'undefined') {
            delete axios.defaults.headers.common['Authorization'];
        }
    },
    
    isAuthenticated: function() {
        return !!this.getToken();
    },
    
    // Auto-login if token exists
    init: function() {
        const token = this.getToken();
        if (token && typeof axios !== 'undefined') {
            axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
            // Verify token is still valid
            this.validateToken().catch(() => {
                // Token invalid, clear it
                this.clearToken();
            });
        }
    },
    
    // Validate token with backend
    validateToken: async function() {
        const token = this.getToken();
        if (!token) {
            return false;
        }
        
        try {
            // Set header first
            axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
            
            const response = await axios.get('/api/auth/me');
            
            // Check if successful
            if (response.data && response.data.success === true) {
                return true;
            }
            
            // Not authenticated
            this.clearToken();
            return false;
        } catch (error) {
            // Token invalid or expired
            console.log('Token validation failed:', error.response?.status || error.message);
            this.clearToken();
            return false;
        }
    },
    
    // Check auth and redirect if needed (for protected pages)
    requireAuth: async function(redirectTo = '/login') {
        const token = this.getToken();
        if (!token) {
            if (window.location.pathname !== redirectTo && !window.location.pathname.includes('/register')) {
                window.location.href = redirectTo;
            }
            return false;
        }
        
        // Validate token
        const isValid = await this.validateToken();
        if (!isValid) {
            if (window.location.pathname !== redirectTo && !window.location.pathname.includes('/register')) {
                window.location.href = redirectTo;
            }
            return false;
        }
        
        return true;
    }
};

// Setup axios interceptor for auth errors
if (typeof axios !== 'undefined') {
    // Request interceptor - add token to all requests
    axios.interceptors.request.use(
        function(config) {
            // Try multiple ways to get token
            let token = null;
            
            // Try AuthManager first
            if (typeof AuthManager !== 'undefined') {
                token = AuthManager.getToken();
            }
            
            // Fallback to direct storage access
            if (!token) {
                token = localStorage.getItem('jwt_token') || sessionStorage.getItem('jwt_token');
            }
            
            if (token) {
                config.headers.Authorization = `Bearer ${token}`;
                // Also set default header
                axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
            }
            return config;
        },
        function(error) {
            return Promise.reject(error);
        }
    );
    
    // Response interceptor - handle auth errors
    axios.interceptors.response.use(
        function(response) {
            return response;
        },
        function(error) {
            if (error.response && error.response.status === 401) {
                // Token expired or invalid
                AuthManager.clearToken();
                // Only redirect if not on public pages
                const publicPages = ['/login', '/register', '/terms', '/privacy', '/gdpr'];
                const isPublicPage = publicPages.some(page => window.location.pathname === page);
                if (!isPublicPage) {
                    window.location.href = '/login';
                }
            }
            return Promise.reject(error);
        }
    );
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        AuthManager.init();
    });
} else {
    AuthManager.init();
}

// Export for use in other scripts
window.AuthManager = AuthManager;

// CRITICAL: Initialize token in axios BEFORE any other scripts run
// This ensures token is available immediately on page load
(function() {
    // Get token from storage immediately
    const token = localStorage.getItem('jwt_token') || sessionStorage.getItem('jwt_token');
    if (token && typeof axios !== 'undefined') {
        // Set axios header IMMEDIATELY, before any requests
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        console.log('Token loaded from storage and set in axios');
    }
})();

