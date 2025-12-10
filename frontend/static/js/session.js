/**
 * Session Management for ANAGHA SOLUTION
 * Handles session persistence and validation
 */

// Session manager
const SessionManager = {
    // Check if user should be redirected
    checkAuth: async function() {
        if (typeof AuthManager === 'undefined') {
            return false;
        }
        
        const token = AuthManager.getToken();
        if (!token) {
            return false;
        }
        
        // Validate token with backend
        try {
            const response = await axios.get('/api/auth/me', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            return response.data.success === true;
        } catch (error) {
            // Token invalid
            if (typeof AuthManager !== 'undefined') {
                AuthManager.clearToken();
            }
            return false;
        }
    },
    
    // Protect a page - redirect if not authenticated
    protectPage: async function(redirectTo = '/login') {
        const publicPages = ['/login', '/register', '/terms', '/privacy', '/gdpr', '/health'];
        const currentPath = window.location.pathname;
        
        if (publicPages.includes(currentPath)) {
            return true; // Public page, no protection needed
        }
        
        const isAuthenticated = await this.checkAuth();
        if (!isAuthenticated) {
            window.location.href = redirectTo;
            return false;
        }
        
        return true;
    }
};

// Export
window.SessionManager = SessionManager;


