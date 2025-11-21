# Third-Party Licenses

## Botany by jifunks

Certain structural patterns and UI layout concepts in this project were inspired by the open-source game **Botany** by jifunks.

**Repository**: https://github.com/jifunks/botany  
**License**: ISC License (very permissive)

### What was adapted

The following elements from Botany's curses UI structure were adapted for Lost Hiker:

- **Four-window layout pattern**: Status bar, narrative window, side panel, and input bar
- **Dynamic window sizing**: Layout that scales based on terminal dimensions
- **Text wrapping utilities**: Generic helpers for safely drawing wrapped text
- **Scrolling menu system**: Multi-option scrolling menus with proper navigation

### Attribution

Botany-inspired code is located in:
- `src/lost_hiker/ui_curses.py` - Contains comments noting Botany inspiration

All adapted code has been rewritten specifically for Lost Hiker's needs and does not contain direct code from Botany. Only structural patterns and concepts were borrowed.

