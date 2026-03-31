// Mobile menu toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.querySelector('.sidebar');
    const container = document.querySelector('.container-fluid');
    const sidebarScrollKey = 'sidebarScrollTop';

    if (sidebar) {
        // Restore last sidebar scroll position on each page load.
        const savedSidebarScroll = sessionStorage.getItem(sidebarScrollKey);
        if (savedSidebarScroll !== null) {
            sidebar.scrollTop = parseInt(savedSidebarScroll, 10) || 0;
        }

        // Persist sidebar scroll as the user scrolls.
        sidebar.addEventListener('scroll', function() {
            sessionStorage.setItem(sidebarScrollKey, String(sidebar.scrollTop));
        });
    }
    
    // Create overlay for mobile
    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    container.appendChild(overlay);
    
    if (menuToggle) {
        menuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        });
        
        // Close sidebar when clicking overlay
        overlay.addEventListener('click', function() {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        });
        
        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 900) {
                if (!sidebar.contains(e.target) && !menuToggle.contains(e.target)) {
                    sidebar.classList.remove('open');
                    overlay.classList.remove('active');
                }
            }
        });
    }
    
    // Add active class to current page link
    const normalizePath = function(path) {
        if (!path) {
            return '/';
        }
        return path.length > 1 ? path.replace(/\/$/, '') : path;
    };

    const currentPath = normalizePath(window.location.pathname);
    const sidebarLinks = document.querySelectorAll('.sidebar-link');

    // Save current sidebar position right before navigating via sidebar links.
    sidebarLinks.forEach(link => {
        link.addEventListener('click', function() {
            if (sidebar) {
                sessionStorage.setItem(sidebarScrollKey, String(sidebar.scrollTop));
            }
        });
    });
    
    sidebarLinks.forEach(link => {
        const linkPath = normalizePath(link.getAttribute('href'));
        const isExactMatch = linkPath === currentPath;
        const isAdminDashboardAlias = linkPath === '/admin/dashboard' && currentPath === '/dashboard';
        const isAdminCompaniesSubRoute = linkPath === '/admin/companies' && (currentPath === '/admin/companies' || currentPath.startsWith('/admin/company/'));

        if (isExactMatch || isAdminDashboardAlias || isAdminCompaniesSubRoute) {
            link.classList.add('active');
        }
    });
    
    // Smooth animations for sidebar links
    sidebarLinks.forEach(link => {
        link.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(6px)';
        });
        
        link.addEventListener('mouseleave', function() {
            if (!this.classList.contains('active')) {
                this.style.transform = 'translateX(0)';
            }
        });
    });
});

// Add some nice hover effects and animations
document.addEventListener('DOMContentLoaded', function() {
    // Animate cards on page load
    const cards = document.querySelectorAll('.panel, .stat-card, .table-card, .quick-link-card');
    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
    });
    
    // Add ripple effect to buttons
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
});