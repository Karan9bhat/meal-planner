import "server-only";

import { Mastra } from "@mastra/core/mastra";
import { chatAgent } from "./agents/chat";
import { intakeAgent } from "./agents/intake";
import { pantryAgent } from "./agents/pantry";

export const mastra = new Mastra({
  agents: { "intake-agent": intakeAgent, "pantry-agent": pantryAgent, "chat-agent": chatAgent },
});
