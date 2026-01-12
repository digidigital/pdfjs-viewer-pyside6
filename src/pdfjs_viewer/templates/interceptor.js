// PDF.js event interceptors for save, print, load, and annotation tracking
// This script intercepts PDF.js operations and communicates with Python
// Enhanced with comprehensive error handling for custom/modified PDF.js versions

(function() {
    'use strict';

    // Configuration
    const PDFJS_TIMEOUT = 10000;  // 10 seconds
    const BRIDGE_TIMEOUT = 5000;   // 5 seconds

    // Wait for PDF.js to initialize (with timeout)
    function waitForPDFJS(timeout = PDFJS_TIMEOUT) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            const check = () => {
                if (window.PDFViewerApplication && window.PDFViewerApplication.initialized) {
                    resolve();
                } else if (Date.now() - startTime > timeout) {
                    reject(new Error('Timeout waiting for PDF.js to initialize'));
                } else {
                    setTimeout(check, 100);
                }
            };
            check();
        });
    }

    // Wait for bridge to be ready (with timeout)
    function waitForBridge(timeout = BRIDGE_TIMEOUT) {
        return new Promise((resolve, reject) => {
            if (window.bridgeReady && window.pdfBridge) {
                resolve();
            } else {
                const startTime = Date.now();
                const checkBridge = () => {
                    if (window.bridgeReady && window.pdfBridge) {
                        resolve();
                    } else if (Date.now() - startTime > timeout) {
                        reject(new Error('Timeout waiting for bridge'));
                    } else {
                        setTimeout(checkBridge, 100);
                    }
                };
                window.addEventListener('pdfBridgeReady', () => resolve(), { once: true });
                setTimeout(checkBridge, 100);
            }
        });
    }

    // Validate PDF.js availability and required methods
    function validatePDFJS() {
        const errors = [];

        if (!window.PDFViewerApplication) {
            errors.push('PDFViewerApplication not found');
            return errors;
        }

        const app = window.PDFViewerApplication;

        // Check for required methods (may not exist in custom versions)
        if (typeof app.download !== 'function') {
            errors.push('PDFViewerApplication.download method not found');
        }
        if (typeof app.beforePrint !== 'function') {
            errors.push('PDFViewerApplication.beforePrint method not found');
        }
        if (typeof app.open !== 'function') {
            errors.push('PDFViewerApplication.open method not found');
        }
        if (!app.eventBus) {
            errors.push('PDFViewerApplication.eventBus not found');
        }

        return errors;
    }


    // Convert large Uint8Array to base64 in chunks to avoid stack overflow
    function arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        const chunkSize = 0x8000; // 32KB chunks
        let binary = '';
        
        for (let i = 0; i < bytes.length; i += chunkSize) {
            const chunk = bytes.subarray(i, Math.min(i + chunkSize, bytes.length));
            binary += String.fromCharCode.apply(null, chunk);
        }
        
        return btoa(binary);
    }

    // Setup save interception with fallback
    function setupSaveInterception(app) {
        if (typeof app.download !== 'function') {
            console.warn('Save interception skipped: app.download not available');
            return false;
        }

        try {
            // Intercept the download button directly as well
            const downloadButton = document.getElementById('downloadButton');  // Main download button
            const secondaryDownload = document.getElementById('secondaryDownload');

            const handleDownload = async (e) => {
                e.preventDefault();
                e.stopPropagation();

                // Call our custom download logic directly
                await performDownload(app);
            };

            if (downloadButton) {
                downloadButton.addEventListener('click', handleDownload, true);
            }
            if (secondaryDownload) {
                secondaryDownload.addEventListener('click', handleDownload, true);
            }

            // Also intercept the app.download method as backup
            const originalDownload = app.download.bind(app);
            app.download = async function() {
                await performDownload(this);
            };

            // Intercept downloadOrSave as well (used when annotations present)
            if (typeof app.downloadOrSave === 'function') {
                const originalDownloadOrSave = app.downloadOrSave.bind(app);
                app.downloadOrSave = async function() {
                    await performDownload(this);
                };
            }

            return true;
        } catch (e) {
            console.error('Failed to setup save interception:', e);
            return false;
        }
    }

    // Shared download logic
    async function performDownload(app) {
        try {
            const pdfDoc = app.pdfDocument;
            if (!pdfDoc) {
                console.error('No PDF document loaded');
                return;
            }

            // Check annotation storage - try multiple ways to detect annotations
            let hasAnnotations = false;
            if (pdfDoc.annotationStorage) {
                // Try different ways to check for annotations
                if (typeof pdfDoc.annotationStorage.size !== 'undefined') {
                    hasAnnotations = pdfDoc.annotationStorage.size > 0;
                } else if (typeof pdfDoc.annotationStorage.getAll === 'function') {
                    const allAnnotations = pdfDoc.annotationStorage.getAll();
                    hasAnnotations = Object.keys(allAnnotations).length > 0;
                }
            }

            // Check if editor has unsaved changes
            if (!hasAnnotations && app.pdfDocument && app.pdfDocument.annotationStorage) {
                const storage = app.pdfDocument.annotationStorage;
                if (storage.serializable && typeof storage.serializable.size !== 'undefined') {
                    hasAnnotations = storage.serializable.size > 0;
                }
            }

            // Check if saveDocument method exists
            const hasSaveDocument = typeof pdfDoc.saveDocument === 'function';

            let data;
            // Always try to use saveDocument if available and we think there might be annotations
            if (hasSaveDocument && hasAnnotations) {
                try {
                    data = await pdfDoc.saveDocument();
                } catch (e) {
                    console.error('saveDocument() failed:', e);
                    data = await pdfDoc.getData();
                }
            } else if (typeof pdfDoc.getData === 'function') {
                data = await pdfDoc.getData();
            } else {
                throw new Error('No method available to get PDF data');
            }

            const base64 = arrayBufferToBase64(data);
            const filename = app._docFilename || 'document.pdf';

            if (window.pdfBridge && typeof window.pdfBridge.save_pdf === 'function') {
                window.pdfBridge.save_pdf(base64, filename);
            } else {
                console.error('Bridge not available for save');
            }
        } catch (e) {
            console.error('Save error:', e);
            if (window.pdfBridge && typeof window.pdfBridge.notify_error === 'function') {
                window.pdfBridge.notify_error('Save error: ' + e.message);
            }
        }
    }

    // Setup load interception
    function setupLoadInterception(app) {
        try {
            // Intercept the "Open File" button in secondary toolbar
            const secondaryOpenFile = document.getElementById('secondaryOpenFile');

            const handleOpenFile = async (e) => {
                e.preventDefault();
                e.stopPropagation();

                try {
                    if (window.pdfBridge && typeof window.pdfBridge.load_pdf_dialog === 'function') {
                        // QWebChannel returns a Promise, so we need to await it
                        const filePath = await window.pdfBridge.load_pdf_dialog();

                        // If user selected a file, load it via backend
                        if (filePath && filePath.length > 0) {
                            // Call backend load method instead of app.open
                            // The backend will handle creating proper URLs and loading the PDF
                            if (window.pdfBridge && typeof window.pdfBridge.load_pdf_from_dialog === 'function') {
                                window.pdfBridge.load_pdf_from_dialog(filePath);
                            } else {
                                console.error('load_pdf_from_dialog method not available');
                            }
                        } else {
                        }
                    } else {
                        console.warn('Load bridge method not available');
                    }
                } catch (e) {
                    console.error('Load error:', e);
                    if (window.pdfBridge && typeof window.pdfBridge.notify_error === 'function') {
                        window.pdfBridge.notify_error('Load error: ' + e.message);
                    }
                }
            };

            if (secondaryOpenFile) {
                secondaryOpenFile.addEventListener('click', handleOpenFile, true);
                return true;
            }

            return false;
        } catch (e) {
            console.error('Failed to setup load interception:', e);
            return false;
        }
    }

    // Setup print interception with fallback
    function setupPrintInterception(app) {
        try {
            // Intercept print button clicks instead of beforePrint to avoid browser dialog
            const printButton = document.getElementById('printButton');
            const secondaryPrint = document.getElementById('secondaryPrint');

            const handlePrint = async (e) => {
                e.preventDefault();
                e.stopPropagation();

                try {
                    const pdfDoc = app.pdfDocument;
                    if (!pdfDoc) {
                        console.error('No PDF document loaded');
                        return;
                    }

                    const hasAnnotations = pdfDoc.annotationStorage && pdfDoc.annotationStorage.size > 0;

                    if (hasAnnotations && window.pdfBridge && typeof pdfDoc.saveDocument === 'function') {
                        const data = await pdfDoc.saveDocument();
                        const base64 = arrayBufferToBase64(data);

                        if (typeof window.pdfBridge.print_pdf === 'function') {
                            window.pdfBridge.print_pdf(base64);
                        }
                    } else if (window.pdfBridge && typeof pdfDoc.getData === 'function') {
                        const data = await pdfDoc.getData();
                        const base64 = arrayBufferToBase64(data);

                        if (typeof window.pdfBridge.print_pdf === 'function') {
                            window.pdfBridge.print_pdf(base64);
                        }
                    } else {
                        console.warn('Print bridge not available, using browser print');
                        window.print();
                    }
                } catch (e) {
                    console.error('Print error:', e);
                    if (window.pdfBridge && typeof window.pdfBridge.notify_error === 'function') {
                        window.pdfBridge.notify_error('Print error: ' + e.message);
                    }
                }
            };

            if (printButton) {
                printButton.addEventListener('click', handlePrint, true);
            }
            if (secondaryPrint) {
                secondaryPrint.addEventListener('click', handlePrint, true);
            }

            return (printButton !== null || secondaryPrint !== null);
        } catch (e) {
            console.error('Failed to setup print interception:', e);
            return false;
        }
    }

    // Setup event listeners
    function setupEventListeners(app) {
        if (!app.eventBus) {
            console.warn('Event listeners skipped: eventBus not available');
            return;
        }

        try {
            // PDF loaded event
            app.eventBus.on('documentloaded', () => {
                if (window.pdfBridge && typeof window.pdfBridge.notify_pdf_loaded === 'function') {
                    const metadata = {
                        numPages: app.pdfDocument ? app.pdfDocument.numPages : 0,
                        title: app.metadata ? (app.metadata.get('dc:title') || '') : '',
                        filename: app._docFilename || ''
                    };
                    window.pdfBridge.notify_pdf_loaded(JSON.stringify(metadata));
                }
            });

            // Annotation change event
            app.eventBus.on('annotationeditorstateschanged', () => {
                if (window.pdfBridge && typeof window.pdfBridge.notify_annotation_changed === 'function') {
                    window.pdfBridge.notify_annotation_changed();
                }
            });

            // Page change event
            app.eventBus.on('pagechanging', (evt) => {
                if (window.pdfBridge && typeof window.pdfBridge.notify_page_changed === 'function' && app.pdfDocument) {
                    window.pdfBridge.notify_page_changed(
                        evt.pageNumber,
                        app.pdfDocument.numPages
                    );
                }
            });
        } catch (e) {
            console.error('Failed to setup event listeners:', e);
        }
    }

    // Setup all interceptors
    async function setupInterceptors() {
        try {
            await Promise.all([waitForPDFJS(), waitForBridge()]);

            // Validate PDF.js
            const validationErrors = validatePDFJS();
            if (validationErrors.length > 0) {
                console.warn('PDF.js validation warnings:', validationErrors);
                if (window.pdfBridge && typeof window.pdfBridge.notify_error === 'function') {
                    window.pdfBridge.notify_error('PDF.js validation warnings: ' + validationErrors.join(', '));
                }
                // Continue anyway, some features may still work
            }

            const app = window.PDFViewerApplication;

            // Setup each interception independently with error handling
            const results = {
                save: setupSaveInterception(app),
                print: setupPrintInterception(app),
                load: setupLoadInterception(app),
            };

            // Setup event listeners
            setupEventListeners(app);


            // Notify if any critical features failed
            if (!results.save && !results.print && !results.load) {
                const message = 'Warning: Save, print, and load interception unavailable. Using default PDF.js behavior.';
                console.warn(message);
                if (window.pdfBridge && typeof window.pdfBridge.notify_error === 'function') {
                    window.pdfBridge.notify_error(message);
                }
            }

        } catch (e) {
            console.error('Fatal error setting up interceptors:', e);
            if (window.pdfBridge && typeof window.pdfBridge.notify_error === 'function') {
                window.pdfBridge.notify_error('Failed to setup PDF.js interceptors: ' + e.message);
            }
        }
    }

    // Initialize when document is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupInterceptors);
    } else {
        setupInterceptors();
    }
})();
