"use client";

import {
  Search,
  Folder as FolderIcon,
  Sparkles,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";

export type ActivityView = "explorer" | "search" | "run" | "cirqAssistant";

export default function ActivityBar({
  active,
  assistantOpen,
  sidebarCollapsed,
  onChange,
  onToggleSidebar,
}: Readonly<{
  active: ActivityView;
  assistantOpen?: boolean;
  sidebarCollapsed?: boolean;
  onChange: (v: ActivityView) => void;
  onToggleSidebar?: () => void;
}>) {
  const items: Array<{ id: ActivityView; label: string; Icon: any }> = [
    { id: "explorer", label: "Explorer", Icon: FolderIcon },
    { id: "search", label: "Search", Icon: Search },
    { id: "cirqAssistant", label: "Cirq AI", Icon: Sparkles },
  ];

  const ToggleIcon = sidebarCollapsed ? PanelLeftOpen : PanelLeftClose;

  return (
    <nav
      aria-label="Activity bar"
      className="w-12 shrink-0 bg-editor-sidebar flex flex-col items-center py-2 gap-1.5"
    >
      {items.map(({ id, label, Icon }) => {
        const isActive =
          id === "cirqAssistant"
            ? !!assistantOpen
            : !sidebarCollapsed && active === id;
        return (
          <button
            key={id}
            type="button"
            title={label}
            aria-label={label}
            aria-pressed={isActive}
            onClick={() => onChange(id)}
            className={`relative w-10 h-10 rounded-md flex items-center justify-center transition-all ${
              isActive
                ? "bg-gray-600/20 text-white shadow-[0_0_18px_rgba(70,234,237,0.14)]"
                : "text-editor-text hover:bg-gray-400/50 hover:text-white"
            }`}
          >
            {isActive && (
              <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-r bg-framework-cirq" />
            )}
            <Icon className="w-5 h-5" />
          </button>
        );
      })}

      {onToggleSidebar && (
        <button
          type="button"
          title={`${sidebarCollapsed ? "Show" : "Hide"} sidebar (Ctrl+B)`}
          aria-label={`${sidebarCollapsed ? "Show" : "Hide"} sidebar`}
          aria-expanded={!sidebarCollapsed}
          onClick={onToggleSidebar}
          className="mt-auto w-10 h-10 rounded-md flex items-center justify-center text-editor-text hover:bg-gray-400/50 hover:text-white transition-all"
        >
          <ToggleIcon className="w-5 h-5" />
        </button>
      )}
    </nav>
  );
}
