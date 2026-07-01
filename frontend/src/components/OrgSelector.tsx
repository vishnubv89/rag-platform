import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { listOrgs } from "../api/client";
import { useChatStore } from "../store/chatStore";
import { useAuthStore } from "../store/authStore";

export function OrgSelector() {
  const { activeOrg, setOrg } = useChatStore();
  const user = useAuthStore((s) => s.user);
  const { data: orgs = [] } = useQuery({ queryKey: ["orgs"], queryFn: listOrgs, retry: false });

  const isSuperadmin = user?.role === "superadmin";

  // Auto-lock non-superadmin users to their assigned org
  useEffect(() => {
    if (isSuperadmin || orgs.length === 0) return;
    if (user?.org_id) {
      const assigned = orgs.find((o) => o.id === user.org_id) ?? null;
      setOrg(assigned);
    }
  }, [orgs, user?.org_id, isSuperadmin, setOrg]);

  // Non-superadmin: show static label if they have an org, nothing otherwise
  if (!isSuperadmin) {
    if (!activeOrg) return null;
    return (
      <span
        className="text-xs px-2.5 py-1.5 rounded-lg"
        style={{ background: "var(--cds-surface-tint)", color: "var(--cds-text-secondary)", border: "1px solid var(--cds-border)" }}
      >
        {activeOrg.name}
      </span>
    );
  }

  if (orgs.length === 0) return null;

  return (
    <select
      className="text-xs border rounded-lg px-2.5 py-1.5 focus:outline-none"
      style={{
        background: "var(--cds-surface-tint)",
        border: "1px solid var(--cds-border)",
        color: "var(--cds-text-secondary)",
        fontFamily: "inherit",
      }}
      value={activeOrg?.id ?? ""}
      onChange={(e) => {
        const org = orgs.find((o) => o.id === Number(e.target.value)) ?? null;
        setOrg(org);
      }}
      onFocus={(e) => { (e.currentTarget as HTMLSelectElement).style.borderColor = "var(--cds-accent)"; }}
      onBlur={(e) => { (e.currentTarget as HTMLSelectElement).style.borderColor = "var(--cds-border)"; }}
    >
      <option value="">Default org</option>
      {orgs.map((o) => (
        <option key={o.id} value={o.id}>{o.name}</option>
      ))}
    </select>
  );
}
