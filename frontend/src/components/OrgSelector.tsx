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
  }, [orgs, user?.org_id, isSuperadmin]);

  // Non-superadmin: show static label if they have an org, nothing otherwise
  if (!isSuperadmin) {
    if (!activeOrg) return null;
    return (
      <span
        className="text-xs px-2.5 py-1.5 rounded-lg"
        style={{ background: "#f3f4f6", color: "#374151", border: "1px solid #e8e8ea" }}
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
        background: "#f7f7f8",
        border: "1px solid #e8e8ea",
        color: "#374151",
        fontFamily: "inherit",
      }}
      value={activeOrg?.id ?? ""}
      onChange={(e) => {
        const org = orgs.find((o) => o.id === Number(e.target.value)) ?? null;
        setOrg(org);
      }}
      onFocus={(e) => { (e.currentTarget as HTMLSelectElement).style.borderColor = "#2563eb"; }}
      onBlur={(e) => { (e.currentTarget as HTMLSelectElement).style.borderColor = "#e8e8ea"; }}
    >
      <option value="">Default org</option>
      {orgs.map((o) => (
        <option key={o.id} value={o.id}>{o.name}</option>
      ))}
    </select>
  );
}
