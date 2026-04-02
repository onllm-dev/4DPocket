import { useState } from "react";
import { Zap, Plus, Loader2, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

interface Rule {
  id: string;
  name: string;
  condition: { type: string; pattern?: string; platform?: string; keyword?: string };
  action: { type: string; tag_name?: string; collection_name?: string };
  is_active: boolean;
}

const CONDITION_TYPES = [
  { value: "url_matches", label: "URL matches pattern" },
  { value: "source_platform", label: "Source platform is" },
  { value: "title_contains", label: "Title contains" },
  { value: "content_contains", label: "Content contains" },
];

const ACTION_TYPES = [
  { value: "add_tag", label: "Add tag" },
  { value: "add_to_collection", label: "Add to collection" },
  { value: "set_favorite", label: "Set as favorite" },
  { value: "archive", label: "Archive" },
];

export default function Rules() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [condType, setCondType] = useState("url_matches");
  const [condValue, setCondValue] = useState("");
  const [actionType, setActionType] = useState("add_tag");
  const [actionValue, setActionValue] = useState("");

  const { data: rules, isLoading } = useQuery<Rule[]>({
    queryKey: ["rules"],
    queryFn: () => api.get("/api/v1/rules"),
  });

  const createRule = useMutation({
    mutationFn: (data: { name: string; condition: object; action: object }) =>
      api.post("/api/v1/rules", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rules"] });
      setShowForm(false);
      setName("");
      setCondValue("");
      setActionValue("");
    },
  });

  const toggleRule = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.patch(`/api/v1/rules/${id}`, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });

  const deleteRule = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/rules/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });

  const handleCreate = () => {
    const condKey = condType === "url_matches" ? "pattern" : condType === "source_platform" ? "platform" : "keyword";
    const actKey = actionType === "add_tag" ? "tag_name" : actionType === "add_to_collection" ? "collection_name" : undefined;
    createRule.mutate({
      name,
      condition: { type: condType, [condKey]: condValue },
      action: actKey ? { type: actionType, [actKey]: actionValue } : { type: actionType },
    });
  };

  return (
    <div className="animate-fade-in max-w-3xl mx-auto px-4">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Zap className="w-6 h-6 text-sky-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Automation Rules</h1>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2 bg-sky-600 text-white rounded-xl text-sm font-medium hover:bg-sky-700 transition-all cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">New Rule</span>
        </button>
      </div>

      {showForm && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 mb-6 space-y-3">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Rule name" className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">When</label>
              <select value={condType} onChange={(e) => setCondType(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm cursor-pointer">
                {CONDITION_TYPES.map((ct) => <option key={ct.value} value={ct.value}>{ct.label}</option>)}
              </select>
              <input value={condValue} onChange={(e) => setCondValue(e.target.value)} placeholder="Value..." className="w-full mt-2 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">Then</label>
              <select value={actionType} onChange={(e) => setActionType(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm cursor-pointer">
                {ACTION_TYPES.map((at) => <option key={at.value} value={at.value}>{at.label}</option>)}
              </select>
              {(actionType === "add_tag" || actionType === "add_to_collection") && (
                <input value={actionValue} onChange={(e) => setActionValue(e.target.value)} placeholder={actionType === "add_tag" ? "Tag name" : "Collection name"} className="w-full mt-2 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm" />
              )}
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 cursor-pointer">Cancel</button>
            <button onClick={handleCreate} disabled={!name || !condValue} className="px-4 py-1.5 bg-sky-600 text-white rounded-lg text-sm font-medium hover:bg-sky-700 disabled:opacity-50 cursor-pointer">Create</button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-sky-600" /></div>
      ) : !rules?.length ? (
        <div className="text-center py-20">
          <Zap className="w-12 h-12 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400">No rules yet</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">Create rules to auto-tag and organize new items</p>
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <div key={rule.id} className="flex items-center gap-4 p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 hover:shadow-sm transition-all">
              <button onClick={() => toggleRule.mutate({ id: rule.id, is_active: !rule.is_active })} className="flex-shrink-0 cursor-pointer">
                {rule.is_active ? <ToggleRight className="w-6 h-6 text-sky-600" /> : <ToggleLeft className="w-6 h-6 text-gray-400" />}
              </button>
              <div className="flex-1 min-w-0">
                <p className={`font-medium text-sm ${rule.is_active ? "text-gray-900 dark:text-gray-100" : "text-gray-400"}`}>{rule.name}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  When {rule.condition.type?.replace(/_/g, " ")} → {rule.action.type?.replace(/_/g, " ")}
                  {rule.action.tag_name && ` "${rule.action.tag_name}"`}
                  {rule.action.collection_name && ` "${rule.action.collection_name}"`}
                </p>
              </div>
              <button onClick={() => deleteRule.mutate(rule.id)} className="p-2 text-gray-400 hover:text-red-500 transition-colors cursor-pointer">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
