/**
 * Terms Handler - External JavaScript
 * Handles the terms and conditions checkbox functionality
 */

(function() {
    'use strict';

    // Wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', function() {
        initTermsHandler();
    });

    function initTermsHandler() {
        const termsCheckbox = document.getElementById('terms');
        
        if (!termsCheckbox) {
            console.log('Terms checkbox not found - may not be on this page');
            return;
        }

        // Add change event listener
        termsCheckbox.addEventListener('change', function() {
            const isChecked = this.checked;
            this.setAttribute('data-terms-accepted', isChecked ? 'yes' : 'no');
            
            console.log('Terms acceptance:', isChecked ? 'ACCEPTED' : 'NOT ACCEPTED');
            
            // Visual feedback
            const label = document.querySelector('label[for="terms"]');
            if (label) {
                if (isChecked) {
                    label.style.color = '#28a745';
                    label.style.fontWeight = '600';
                } else {
                    label.style.color = '#333';
                    label.style.fontWeight = 'normal';
                }
            }

            // Dispatch custom event for other scripts to listen to
            const event = new CustomEvent('termsChanged', {
                detail: { accepted: isChecked }
            });
            document.dispatchEvent(event);
        });

        // Initialize state
        termsCheckbox.setAttribute('data-terms-accepted', 'no');
        
        console.log('✓ Terms handler initialized (external JS)');
    }

    // Expose function globally if needed
    window.TermsHandler = {
        isAccepted: function() {
            const checkbox = document.getElementById('terms');
            return checkbox ? checkbox.checked : false;
        },
        reset: function() {
            const checkbox = document.getElementById('terms');
            if (checkbox) {
                checkbox.checked = false;
                checkbox.dispatchEvent(new Event('change'));
            }
        }
    };
})();
