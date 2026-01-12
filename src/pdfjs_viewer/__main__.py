"""Entry point for running pdfjs_viewer.print_process as a module.

This allows the print process to be spawned via:
    python -m pdfjs_viewer.print_process <socket_name>
"""

import sys

# Check if we're being called for print_process
if len(sys.argv) > 0 and 'print_process' in sys.argv[0]:
    from .print_process import main
    main()
else:
    print("pdfjs_viewer: No default action. Use 'python -m pdfjs_viewer.print_process' for print process.", file=sys.stderr)
    sys.exit(1)
