/**
 * Terminal lifecycle helpers.
 *
 * Provides ANSI escape sequences to restore the terminal to a clean
 * state after the TUI exits (or crashes).
 */

/** Disable mouse tracking and reset all ANSI attributes. */
export function resetTerminal(): void {
  process.stdout.write(
    "\x1b[?1000l" + // disable mouse click tracking
    "\x1b[?1002l" + // disable mouse button-event tracking
    "\x1b[?1003l" + // disable mouse motion tracking
    "\x1b[?1006l" + // disable SGR mouse mode
    "\x1b[?25h"  +  // show cursor
    "\x1b[0m"       // reset all attributes
  );
}

/** Clear the screen and reset cursor to the top-left corner. */
export function clearScreen(): void {
  process.stdout.write("\x1b[2J\x1b[H");
}
