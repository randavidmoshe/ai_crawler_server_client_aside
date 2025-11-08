// terms-handler.js - External JavaScript for Terms Checkbox

console.log('✓ External terms-handler.js loaded');

// Terms checkbox handler
function initTermsCheckbox() {
    const termsCheckbox = document.getElementById('terms');
    if (!termsCheckbox) return;
    
    // Track state in data attribute
    termsCheckbox.addEventListener('change', function() {
        const isChecked = this.checked;
        this.setAttribute('data-agreed', isChecked ? 'true' : 'false');
        console.log('Terms checkbox:', isChecked ? 'AGREED' : 'NOT AGREED');
        
        // Update visual feedback
        const label = document.querySelector('label[for="terms"]');
        if (label) {
            if (isChecked) {
                label.style.color = '#28a745';
            } else {
                label.style.color = '#333';
            }
        }
    });
    
    // Initialize state
    termsCheckbox.setAttribute('data-agreed', termsCheckbox.checked ? 'true' : 'false');
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTermsCheckbox);
} else {
    initTermsCheckbox();
}
