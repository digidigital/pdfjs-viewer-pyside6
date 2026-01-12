// Custom context menu handler for text selection
(function() {
    'use strict';


    let bridgeReady = false;
    let pdfBridge = null;

    // Listen for bridge ready event (dispatched by bridge.js)
    window.addEventListener('pdfBridgeReady', function() {
        if (window.pdfBridge) {
            bridgeReady = true;
            pdfBridge = window.pdfBridge;
        }
    });

    // Also check if bridge is already ready (in case event already fired)
    if (window.bridgeReady && window.pdfBridge) {
        bridgeReady = true;
        pdfBridge = window.pdfBridge;
    }

    // Add context menu listener - always prevent default Qt menu
    document.addEventListener('contextmenu', function(event) {
        // Always prevent the default Qt context menu
        event.preventDefault();
        event.stopPropagation();

        // Get selected text
        const selectedText = window.getSelection().toString().trim();

        if (selectedText) {
            // Copy to clipboard via PDF bridge
            if (bridgeReady && pdfBridge && pdfBridge.copyToClipboard) {
                pdfBridge.copyToClipboard(selectedText);
            } else {
                console.warn('PDF bridge not ready yet, using fallback');
                // Fallback: use browser clipboard API
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(selectedText).then(function() {
                    }).catch(function(err) {
                        console.error('Failed to copy text:', err);
                    });
                } else {
                    console.error('No clipboard method available');
                }
            }
        } else {
        }
    }, true); // Use capture phase to intercept early

})();
