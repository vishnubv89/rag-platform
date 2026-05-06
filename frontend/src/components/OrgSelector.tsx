import { useQuery } from "@tanstack/react-query";
import { listOrgs } from "../api/client";
import { useChatStore } from "../store/chatStore";

export function OrgSelector() {
  const { activeOrg, setOrg } = useChatStore();
  const { data: orgs = [] } = useQuery({ queryKey: ["orgs"], queryFn: listOrgs, retry: false });

  if (orgs.length === 0) return null;

  return (
    <select
      className="text-xs border border-gray-200 rounded-lg px-2 py-1 bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-200"
      value={activeOrg?.id ?? ""}
      onChange={(e) => {
        const org = orgs.find((o) => o.id === Number(e.target.value)) ?? null;
        setOrg(org);
      }}
    >
      <option value="">Default org</option>
      {orgs.map((o) => (
        <option key={o.id} value={o.id}>{o.name}</option>
      ))}
    </select>
  );
}
