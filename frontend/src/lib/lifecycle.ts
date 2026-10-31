import type { LifecycleAction, Role, Subscription } from "./types";

export const statuses = [
  "draft",
  "quotation",
  "confirmed",
  "active",
  "closed",
] as const;
export const actionLabels: Record<LifecycleAction, string> = {
  quotation: "Create quotation",
  confirm: "Confirm subscription",
  activate: "Activate subscription",
  pause: "Pause subscription",
  resume: "Resume subscription",
  renew: "Renew subscription",
  close: "Close subscription",
};
export function isOperator(role: Role): boolean {
  return role === "admin" || role === "staff";
}
export function allowedActions(
  subscription: Subscription,
  role: Role,
): LifecycleAction[] {
  if (!isOperator(role)) return [];
  if (subscription.status === "draft") return ["quotation"];
  if (subscription.status === "quotation") return ["confirm"];
  if (subscription.status === "confirmed") return ["activate"];
  if (subscription.status !== "active") return [];
  const terms = subscription.commercial_snapshot?.plan;
  const actions: LifecycleAction[] = [];
  if (subscription.is_paused) actions.push("resume");
  else if (terms?.pausable) actions.push("pause");
  if (terms?.renewable) actions.push("renew");
  if (terms?.closable) actions.push("close");
  return actions;
}
