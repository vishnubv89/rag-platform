import { useState, useCallback } from "react";
import { getConfig } from "../api/client";

const WIZARD_DONE_KEY = "rag_wizard_done";

export function needsWizard(config: Record<string, string>, role: string): boolean {
  if (role !== "superadmin") return false;
  if (localStorage.getItem(WIZARD_DONE_KEY)) return false;
  const provider = config.llm_provider;
  if (!provider) return true;
  if (provider === "anthropic" && !config.anthropic_api_key) return true;
  if (provider === "nvidia" && !config.nvidia_api_key) return true;
  return false;
}

export function useWizardCheck(orgId: number | null, role: string) {
  const [show, setShow] = useState(false);
  const [checked, setChecked] = useState(false);

  const check = useCallback(async () => {
    if (role !== "superadmin" || localStorage.getItem(WIZARD_DONE_KEY)) {
      setChecked(true);
      return;
    }
    try {
      const cfg = await getConfig(orgId);
      setShow(needsWizard(cfg, role));
    } catch {
      // If config fetch fails, don't block the app
    } finally {
      setChecked(true);
    }
  }, [orgId, role]);

  return { show, setShow, checked, check };
}
