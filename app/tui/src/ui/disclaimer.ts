/**
 * First-run disclaimer -- shown once in plain terminal mode before the
 * TUI launches. Persists acceptance to disk so it only shows once.
 */

import { DISCLAIMER_FLAG } from "../config/constants.js";

const RED = "\x1b[31m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";
const YELLOW = "\x1b[33m";
const RESET = "\x1b[0m";
const WHITE = "\x1b[97m";

const DISCLAIMER_LINES = [
  "",
  `${RED}${BOLD}  ============================================================${RESET}`,
  `${RED}${BOLD}   TECHNOLOGY DEMONSTRATOR -- RISK DISCLAIMER${RESET}`,
  `${RED}${BOLD}  ============================================================${RESET}`,
  "",
  `${WHITE}  This software is a technology demonstrator and is${RESET}`,
  `${WHITE}  ${BOLD}not intended for continuous or production use.${RESET}`,
  "",
  `${YELLOW}  By proceeding, you acknowledge the following:${RESET}`,
  "",
  `${RED}  *${RESET} ${BOLD}High-autonomy agent.${RESET}${DIM} This system deploys an AI agent with${RESET}`,
  `${DIM}    high autonomy and elevated authorization levels. The agent${RESET}`,
  `${DIM}    can execute code, create and delete cloud resources, send${RESET}`,
  `${DIM}    messages, access APIs, push code to repositories, and make${RESET}`,
  `${DIM}    consequential decisions on your behalf -- without further${RESET}`,
  `${DIM}    confirmation.${RESET}`,
  "",
  `${RED}  *${RESET} ${BOLD}Sandbox environments only.${RESET}${DIM} This system should only be run${RESET}`,
  `${DIM}    against sandbox Azure subscriptions and disposable GitHub${RESET}`,
  `${DIM}    accounts. Never connect production accounts, billing-sensitive${RESET}`,
  `${DIM}    subscriptions, or repositories you care about.${RESET}`,
  "",
  `${RED}  *${RESET} ${BOLD}Potential for damage.${RESET}${DIM} The agent may take destructive or${RESET}`,
  `${DIM}    irreversible actions including: deleting resources, sending${RESET}`,
  `${DIM}    unintended messages, pushing code, incurring cloud costs,${RESET}`,
  `${DIM}    exhausting API quotas, or exposing credentials. You accept${RESET}`,
  `${DIM}    full responsibility for any and all consequences.${RESET}`,
  "",
  `${RED}  *${RESET} ${BOLD}No warranty.${RESET}${DIM} This software is provided under the MIT License,${RESET}`,
  `${DIM}    "as is", without warranty of any kind. The authors and${RESET}`,
  `${DIM}    contributors are not liable for any damages, costs, data${RESET}`,
  `${DIM}    loss, or any other harm arising from the use of this system.${RESET}`,
  "",
  `${RED}  *${RESET} ${BOLD}Not a supported product.${RESET}${DIM} This is an experimental technology${RESET}`,
  `${DIM}    demonstration. There are no SLAs, no guarantees of correctness,${RESET}`,
  `${DIM}    safety, or availability.${RESET}`,
  "",
  `${RED}${BOLD}  ============================================================${RESET}`,
  "",
];

/**
 * Show the disclaimer and block until the user types "accept".
 * No-ops if the disclaimer was already accepted previously.
 */
export async function showDisclaimer(): Promise<void> {
  try {
    if (await Bun.file(DISCLAIMER_FLAG).exists()) return;
  } catch {
    // File doesn't exist -- continue to show disclaimer
  }

  process.stdout.write("\x1b[2J\x1b[H"); // clear screen

  for (const line of DISCLAIMER_LINES) {
    process.stdout.write(line + "\n");
  }

  process.stdout.write(
    `${YELLOW}  Type ${WHITE}${BOLD}accept${RESET}${YELLOW} to acknowledge the risks and continue: ${RESET}`,
  );

  const response = await new Promise<string>((resolve) => {
    const onData = (data: Buffer) => {
      const input = data.toString().trim().toLowerCase();
      if (input) {
        process.stdin.removeListener("data", onData);
        process.stdin.setRawMode?.(false);
        process.stdin.pause();
        resolve(input);
      }
    };
    process.stdin.resume();
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", onData);
  });

  if (response !== "accept") {
    process.stdout.write(`\n${RED}  Disclaimer not accepted. Exiting.${RESET}\n\n`);
    process.exit(1);
  }

  await Bun.write(DISCLAIMER_FLAG, new Date().toISOString());
  process.stdout.write(`\n${DIM}  Disclaimer accepted.${RESET}\n\n`);
}
