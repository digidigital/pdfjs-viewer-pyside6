// Feature control script - shows/hides UI elements based on configuration
// Configuration is passed via window.pdfjsFeatureConfig

(function() {
    'use strict';

    // UI element mappings
    const FEATURE_ELEMENTS = {
        print: ['printButton', 'secondaryPrint'],
        save: ['downloadButton', 'secondaryDownload'],
        load: ['secondaryOpenFile'],
        presentation: ['presentationMode', 'secondaryPresentationMode'],
        highlight: ['editorHighlightButton'],
        freetext: ['editorFreeTextButton'],
        ink: ['editorInkButton'],
        stamp: ['editorStampButton'],
        signature: ['editorSignatureButton'],
        comment: ['editorCommentButton'],
        bookmark: ['viewBookmark'],
        scrollMode: ['scrollModeButtons'],
        spreadMode: ['spreadModeButtons'],
    };

    // Function to disable stamp alt-text feature
    function disableStampAltText() {

        // Use CSS to hide alt-text buttons while keeping delete buttons visible
        const style = document.createElement('style');
        style.id = 'pdfjs-disable-alttext-style';
        style.textContent = `
            /* Hide alt-text button for stamp annotations */
            .stampEditor button[data-l10n-id="pdfjs-editor-alt-text-button-label"],
            .stampEditor button[aria-label="Alt text"],
            button[data-l10n-id="pdfjs-editor-alt-text-edit-button"],
            button.altText {
                display: none !important;
            }

            /* Hide the divider in the toolbar */
            .stampEditor .editorParamsToolbar .divider,
            .stampEditor .divider {
                display: none !important;
            }

            /* Hide the vertical separator bar between alt-text and delete button */
            .stampEditor .visuallyHidden + button[data-l10n-id="pdfjs-editor-remove-stamp-button"]::before,
            .stampEditor button.altText + .visuallyHidden,
            .stampEditor .editorParamsToolbar > .visuallyHidden {
                display: none !important;
            }

            /* Ensure delete button remains visible */
            .stampEditor button[data-l10n-id="pdfjs-editor-remove-stamp-button"],
            .stampEditor button.delete {
                display: inline-block !important;
            }

            /* Hide the "Alt text" badge indicators */
            button[data-l10n-id="pdfjs-editor-new-alt-text-missing-button-label"],
            button[data-l10n-id="pdfjs-editor-new-alt-text-added-button-label"],
            button[data-l10n-id="pdfjs-editor-new-alt-text-to-review-button-label"] {
                display: none !important;
            }
        `;
        document.head.appendChild(style);

        // Also prevent alt-text dialog from opening
        if (window.PDFViewerApplication && window.PDFViewerApplication.externalServices) {
            const originalML = window.PDFViewerApplication.externalServices.ml;
            if (originalML) {
                // Disable ML alt-text generation
                window.PDFViewerApplication.externalServices.ml = null;
            }
        }

    }

    // Separator management - maps features to their associated separators
    const FEATURE_SEPARATORS = {
        // When both print and save are hidden, hide editorModeSeparator
        save: {
            separator: 'editorModeSeparator',
            hideWhen: (config) => !config.print && !config.save
        },
        // When both presentation and bookmark are hidden, hide viewBookmarkSeparator
        bookmark: {
            separator: 'viewBookmarkSeparator',
            hideWhen: (config) => !config.presentation && !config.bookmark
        },
        // When scrollMode is hidden, hide the separator before it
        scrollMode: {
            // Separator is the one before scrollModeButtons (can't easily ID it without modifying HTML)
            // We'll handle this by finding the previous sibling separator
            findSeparator: (element) => {
                let prev = element.previousElementSibling;
                while (prev) {
                    if (prev.classList.contains('horizontalToolbarSeparator')) {
                        return prev;
                    }
                    prev = prev.previousElementSibling;
                }
                return null;
            }
        },
        // When spreadMode is hidden, hide the separator before it
        spreadMode: {
            findSeparator: (element) => {
                let prev = element.previousElementSibling;
                while (prev) {
                    if (prev.classList.contains('horizontalToolbarSeparator')) {
                        return prev;
                    }
                    prev = prev.previousElementSibling;
                }
                return null;
            }
        }
    };

    function applyFeatureConfig(config) {
        if (!config) {
            return;
        }

        // Force presentation mode to be visible if enabled
        // PDF.js may hide it automatically when fullscreen API is not available in WebEngine
        if (config.presentation !== false) {
            const style = document.createElement('style');
            style.id = 'pdfjs-force-presentation-style';
            style.textContent = `
                /* Force presentation mode button to be visible */
                #presentationMode,
                #secondaryPresentationMode {
                    display: inline-block !important;
                    visibility: visible !important;
                }
            `;
            // Remove existing style if present (for dynamic updates)
            const existingStyle = document.getElementById('pdfjs-force-presentation-style');
            if (existingStyle) {
                existingStyle.remove();
            }
            document.head.appendChild(style);
        } else {
            // Remove the style if presentation mode is disabled
            const existingStyle = document.getElementById('pdfjs-force-presentation-style');
            if (existingStyle) {
                existingStyle.remove();
            }
        }

        // Handle stamp alt-text disabling
        if (config.stampAltText === false) {
            disableStampAltText();
        }

        // Apply feature visibility
        for (const [feature, elementIds] of Object.entries(FEATURE_ELEMENTS)) {
            const enabled = config[feature] !== false;

            elementIds.forEach(id => {
                const element = document.getElementById(id);
                if (element) {
                    if (enabled) {
                        // Remove display override to restore default visibility
                        element.style.removeProperty('display');
                        element.style.removeProperty('visibility');
                        element.disabled = false;
                    } else {
                        element.style.display = 'none';
                        element.style.visibility = 'hidden';
                        element.disabled = true;
                    }
                }
            });
        }

        // Handle separators
        for (const [feature, separatorConfig] of Object.entries(FEATURE_SEPARATORS)) {
            const enabled = config[feature] !== false;
            let separator = null;

            // Get the separator element
            if (separatorConfig.separator) {
                separator = document.getElementById(separatorConfig.separator);
            } else if (separatorConfig.findSeparator) {
                const featureElements = FEATURE_ELEMENTS[feature];
                if (featureElements && featureElements.length > 0) {
                    const firstElement = document.getElementById(featureElements[0]);
                    if (firstElement) {
                        separator = separatorConfig.findSeparator(firstElement);
                    }
                }
            }

            // Hide separator if needed
            if (separator) {
                let hideSeparator = !enabled;

                // Check custom hide condition if provided
                if (separatorConfig.hideWhen) {
                    hideSeparator = separatorConfig.hideWhen(config);
                }

                if (hideSeparator) {
                    separator.style.display = 'none';
                } else {
                    // Remove display override to restore default visibility
                    separator.style.removeProperty('display');
                }
            }
        }

    }

    // Wait for PDF.js to be fully loaded
    function waitForPDFJS() {
        return new Promise((resolve) => {
            const check = () => {
                if (window.PDFViewerApplication && window.PDFViewerApplication.initialized) {
                    resolve();
                } else {
                    setTimeout(check, 100);
                }
            };
            check();
        });
    }

    async function initialize() {
        // Wait for PDF.js
        await waitForPDFJS();

        // Apply configuration if available
        if (window.pdfjsFeatureConfig) {
            applyFeatureConfig(window.pdfjsFeatureConfig);
        }
    }

    // Initialize when ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }

    // Expose function for dynamic updates
    window.updateFeatureConfig = applyFeatureConfig;
})();
