// QWebChannel bridge initialization
// This script establishes the Python-JavaScript communication channel

(function() {
    'use strict';

    // Wait for qt.webChannelTransport to be available
    function initializeBridge() {
        if (typeof qt !== 'undefined' && qt.webChannelTransport) {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                window.pdfBridge = channel.objects.pdfBridge;

                // Mark bridge as ready
                window.bridgeReady = true;

                // Dispatch custom event for other scripts
                window.dispatchEvent(new Event('pdfBridgeReady'));
            });
        } else {
            // Retry after a short delay
            setTimeout(initializeBridge, 100);
        }
    }

    // Start initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeBridge);
    } else {
        initializeBridge();
    }
})();
