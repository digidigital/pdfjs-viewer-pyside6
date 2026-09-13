// Feature control script - shows/hides UI elements based on configuration
// Configuration is passed via window.pdfjsFeatureConfig

(function() {
    'use strict';

    // ---------------------------------------------------------------
    // Stylesheet injection
    //
    // PDF.js >= 6.x ships a Content-Security-Policy in viewer.html with
    // `style-src 'self'` (no 'unsafe-inline'). That blocks the classic
    // `<style>` element + textContent approach: Chromium refuses to apply
    // the sheet and the rules silently never take effect.
    //
    // Constructable stylesheets (new CSSStyleSheet() + adoptedStyleSheets)
    // go through the CSSOM rather than inline style, so CSP does not apply.
    // ---------------------------------------------------------------
    const injectedSheets = new Map();

    function injectCSS(id, cssText) {
        try {
            let sheet = injectedSheets.get(id);
            if (!sheet) {
                sheet = new CSSStyleSheet();
                injectedSheets.set(id, sheet);
                document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
            }
            sheet.replaceSync(cssText);
            return true;
        } catch (e) {
            // Fallback for engines without constructable stylesheet support.
            // CSP blocks this on PDF.js >= 6.x, but it is harmless where it does not.
            try {
                let style = document.getElementById(id);
                if (!style) {
                    style = document.createElement('style');
                    style.id = id;
                    document.head.appendChild(style);
                }
                style.textContent = cssText;
                return true;
            } catch (e2) {
                console.error('Failed to inject stylesheet ' + id + ':', e2);
                return false;
            }
        }
    }

    function removeCSS(id) {
        const sheet = injectedSheets.get(id);
        if (sheet) {
            document.adoptedStyleSheets =
                document.adoptedStyleSheets.filter(s => s !== sheet);
            injectedSheets.delete(id);
        }
        const style = document.getElementById(id);
        if (style) {
            style.remove();
        }
    }


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
        injectCSS('pdfjs-disable-alttext-style', `
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
        `);

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
            // PDF.js hides this button with the `.hidden` class when the
            // Fullscreen API is unavailable, and `.hidden` is
            // `display: none !important`, so the override needs !important too.
            // `flex` is the natural .toolbarButton display value.
            injectCSS('pdfjs-force-presentation-style', `
                /* Force presentation mode button to be visible */
                #presentationMode,
                #secondaryPresentationMode {
                    display: flex !important;
                    visibility: visible !important;
                }
            `);
        } else {
            // Remove the style if presentation mode is disabled
            removeCSS('pdfjs-force-presentation-style');
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
