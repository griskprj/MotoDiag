document.addEventListener('DOMContentLoaded', function() {
    const burgerMenu = document.querySelector('.burger-menu');
    const mobileMenu = document.querySelector('.mobile-menu');
    const overlay = document.querySelector('.overlay');
    const mobileMenuLinks = document.querySelectorAll('.mobile-menu a');
    
    // Toggle mobile menu
    burgerMenu.addEventListener('click', function() {
        this.classList.toggle('active');
        mobileMenu.classList.toggle('active');
        overlay.classList.toggle('active');
    });
    
    // Close menu when clicking on overlay
    overlay.addEventListener('click', function() {
        burgerMenu.classList.remove('active');
        mobileMenu.classList.remove('active');
        this.classList.remove('active');
    });
    
    // Close menu when clicking on a link
    mobileMenuLinks.forEach(link => {
        link.addEventListener('click', function() {
            burgerMenu.classList.remove('active');
            mobileMenu.classList.remove('active');
            overlay.classList.remove('active');
        });
    });
});