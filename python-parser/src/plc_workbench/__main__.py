"""Support ``python -m plc_workbench`` as well as the installed ``plc`` script."""

from .cli import main

raise SystemExit(main())
