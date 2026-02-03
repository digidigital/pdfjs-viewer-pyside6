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

    // Download logic — used by download button clicks
    async function performDownload(app) {
        try {
            const pdfDoc = app.pdfDocument;
            if (!pdfDoc) return;

            // Acknowledge to Python that we received the download request
            // Python uses this to distinguish 'JS is working' from 'JS is dead'
            if (window.pdfBridge && typeof window.pdfBridge.notify_save_started === 'function') {
                window.pdfBridge.notify_save_started();
            }

            // Exit annotation edit mode to commit any in-progress annotations
            if (app.pdfViewer) {
                const currentMode = app.pdfViewer.annotationEditorMode;
                if (currentMode && currentMode > 0) {
                    if (app.eventBus) {
                        app.eventBus.dispatch('switchannotationeditormode', {
                            source: app,
                            mode: 0  // NONE
                        });
                    }
                    // Give PDF.js time to commit
                    await new Promise(resolve => setTimeout(resolve, 150));
                }
            }

            let data;
            // Always try to use saveDocument if available (includes annotations)
            if (typeof pdfDoc.saveDocument === 'function') {
                try {
                    data = await pdfDoc.saveDocument();
                } catch (e) {
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
            }
        } catch (e) {
            console.error('Save error:', e);
            if (window.pdfBridge && typeof window.pdfBridge.notify_error === 'function') {
                window.pdfBridge.notify_error('Save error: ' + e.message);
            }
        }
    }

    // Setup load interception for ALL PDF.js open file mechanisms
    function setupLoadInterception(app) {
        try {
            // Get all open file elements
            const openFile = document.getElementById('openFile');           // Primary toolbar button
            const secondaryOpenFile = document.getElementById('secondaryOpenFile');  // Secondary toolbar button
            const fileInput = document.getElementById('fileInput');         // Hidden file input element

            const handleOpenFile = async (e) => {
                e.preventDefault();
                e.stopPropagation();

                // Simply request Qt to handle the entire open PDF flow
                // Qt will: check unsaved changes, show file dialog, load PDF
                // This ensures consistent behavior with Qt "Open PDF" buttons
                if (window.pdfBridge && typeof window.pdfBridge.request_open_pdf === 'function') {
                    window.pdfBridge.request_open_pdf();
                } else {
                    console.warn('request_open_pdf bridge method not available');
                }
            };

            let intercepted = false;

            // Intercept primary toolbar button
            if (openFile) {
                openFile.addEventListener('click', handleOpenFile, true);
                intercepted = true;
            }

            // Intercept secondary toolbar button
            if (secondaryOpenFile) {
                secondaryOpenFile.addEventListener('click', handleOpenFile, true);
                intercepted = true;
            }

            // Intercept file input element (handles native file dialog)
            if (fileInput) {
                fileInput.addEventListener('change', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    // Clear the input value to prevent PDF.js from using it
                    fileInput.value = '';
                    // Use Qt file dialog instead
                    handleOpenFile(e);
                }, true);
                intercepted = true;
            }

            // Also intercept PDFViewerApplication.open() for programmatic loads
            if (typeof app.open === 'function') {
                const originalOpen = app.open.bind(app);
                app.open = async function(args) {
                    // For programmatic opens, we can't easily intercept with a dialog
                    // The unsaved changes check happens at the Python level when load_pdf is called
                    // This is mainly for drag-and-drop which is handled by PDF.js
                    return originalOpen(args);
                };
            }

            return intercepted;
        } catch (e) {
            console.error('Failed to setup load interception:', e);
            return false;
        }
    }

    // Setup print interception - just call Qt to handle everything
    function setupPrintInterception(app) {
        try {
            const printButton = document.getElementById('printButton');
            const secondaryPrint = document.getElementById('secondaryPrint');

            const handlePrint = (e) => {
                e.preventDefault();
                e.stopPropagation();

                // Simply request Qt to handle the entire print flow
                // Qt will: get PDF with annotations, show print dialog, print
                // This ensures consistent behavior with Qt "Print" buttons
                if (window.pdfBridge && typeof window.pdfBridge.request_print_pdf === 'function') {
                    window.pdfBridge.request_print_pdf();
                } else {
                    console.warn('request_print_pdf bridge method not available');
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

    // NOTE: Unsaved changes detection is now handled by Qt-side AnnotationStateTracker
    // which monitors annotation changes through the bridge's notify_annotation_changed signal.
    // This is more reliable than querying PDF.js internal state.

    // Get current filename (called from Python)
    window.getCurrentFilename = function() {
        return window.PDFViewerApplication._docFilename || 'document.pdf';
    };

    // Suppress PDF.js beforeunload handler when we're handling unsaved changes
    // This prevents the browser "are you sure you want to leave" dialog
    window.suppressBeforeUnload = function() {
        // Remove any beforeunload handlers
        window.onbeforeunload = null;

        // Clear PDF.js internal flags that trigger the dialog
        const app = window.PDFViewerApplication;
        if (app) {
            // Reset AcroForm unsaved changes flag
            app._hasAcroFormUnsavedChanges = false;

            // Reset annotation storage modified flag
            app._annotationStorageModified = false;

            // Use the public resetModified() API to properly clear the private
            // #modified flag. Direct assignment (storage._modified = false) does NOT
            // work because #modified is a true JS private field.
            // resetModified() also triggers onResetModified callback if set.
            if (app.pdfDocument && app.pdfDocument.annotationStorage) {
                app.pdfDocument.annotationStorage.resetModified();
            }
        }
    };

    // Mark annotations as saved (called after successful save)
    window.markAnnotationsSaved = function() {
        const app = window.PDFViewerApplication;
        if (app) {
            app._annotationStorageModified = false;
            app._hasAcroFormUnsavedChanges = false;
            // Use the public resetModified() API (see suppressBeforeUnload comment)
            if (app.pdfDocument && app.pdfDocument.annotationStorage) {
                app.pdfDocument.annotationStorage.resetModified();
            }
        }
    };

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

                // Hook into AnnotationStorage.onSetModified for reliable change detection.
                // onSetModified only fires when actual annotation data is written to
                // storage (i.e. real content changes), unlike annotationeditorstateschanged
                // which fires on any UI state change. This is the same mechanism PDF.js
                // itself uses for its beforeunload warning.
                //
                // We use defineProperty to make our hook resilient: PDF.js's
                // _initializeAnnotationStorageCallbacks also sets onSetModified, and
                // depending on Promise resolution order it could overwrite ours.
                // By intercepting the property setter, we ensure our bridge notification
                // always runs regardless of who sets the callback.
                const storage = app.pdfDocument && app.pdfDocument.annotationStorage;
                if (storage) {
                    let _originalOnSetModified = storage.onSetModified;
                    Object.defineProperty(storage, 'onSetModified', {
                        get: function() { return _originalOnSetModified; },
                        set: function(fn) {
                            // Wrap any callback set by PDF.js (or anyone) to also
                            // notify the Qt bridge
                            _originalOnSetModified = () => {
                                if (typeof fn === 'function') fn();
                                if (window.pdfBridge && typeof window.pdfBridge.notify_annotation_changed === 'function') {
                                    window.pdfBridge.notify_annotation_changed();
                                }
                            };
                        },
                        configurable: true
                    });
                    // Trigger the setter to wrap the current value
                    storage.onSetModified = _originalOnSetModified;
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

    // Setup beforeunload interception - belt-and-suspenders approach
    // The PRIMARY mechanism is Qt's javaScriptConfirm() override in PDFWebEnginePage
    // which always returns true, completely blocking the browser's beforeunload dialog.
    // This JS-side interception provides additional protection.
    function setupBeforeUnloadInterception() {
        // Intercept any attempts to set onbeforeunload
        Object.defineProperty(window, 'onbeforeunload', {
            get: function() { return null; },
            set: function(handler) {
                // Silently ignore - Qt handles unsaved changes via AnnotationStateTracker
                return;
            },
            configurable: true
        });

        // Add highest-priority handler that prevents browser dialog
        window.addEventListener('beforeunload', function(e) {
            e.stopImmediatePropagation();
            e.preventDefault();
            e.returnValue = '';
            delete e.returnValue;
            return undefined;
        }, true);  // Use capture phase
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

            // Setup beforeunload interception first
            setupBeforeUnloadInterception();

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
