/* DëvSec Design Lab — root. Mistglass Grey desktop product.
   Every section is a real screen rendered inside the shared MistShell.
   Add a screen: build screens/<id>.jsx (window.<Name>), load it in index.html,
   then register it in MIST_SCREENS and add its nav item below. */

const MIST_NAV = [
  { label: "posture", items: [
    { id: "overview", label: "Overview", icon: "layout-dashboard" },
    { id: "activity", label: "Activity", icon: "activity" },
  ]},
  { label: "findings", items: [
    { id: "cases", label: "Cases", icon: "inbox" },
    { id: "honey-keys", label: "Honey keys", icon: "key-round" },
    { id: "verification", label: "Verification", icon: "circle-check" },
  ]},
  { label: "act", items: [
    { id: "fix-proposals", label: "Code fixes", icon: "wrench" },
    { id: "playbooks", label: "Recovery playbooks", icon: "book-open" },
  ]},
  { label: "catalog", items: [
    { id: "scanners", label: "Tool catalog", icon: "package" },
    { id: "agent-lab", label: "Agent lab", icon: "flask" },
  ]},
  { label: "system", items: [
    { id: "reports", label: "Reports", icon: "file-text" },
    { id: "settings", label: "Settings", icon: "settings" },
  ]},
];

const MIST_SCREENS = {
  overview: MOverview,
  activity: MActivity,
  cases: MCases,
  "honey-keys": MHoneyKeys,
  verification: MVerification,
  "fix-proposals": MFixes,
  playbooks: MPlaybooks,
  scanners: MCatalog,
  "agent-lab": MAgentLab,
  reports: MReports,
  settings: MSettings,
};

const ALL_ITEMS = MIST_NAV.flatMap((g) => g.items);

// Repos for the workspace switcher. "all" (default) aggregates the portfolio;
// picking one scopes the view. Fake — the real app derives these from disk.
const MIST_REPOS = ["payments-api", "web-dashboard", "infra-terraform"];

function App() {
  const initial = (window.location.hash || "").replace(/^#/, "");
  const [activeId, setActiveId] = React.useState(
    ALL_ITEMS.some((i) => i.id === initial) ? initial : "overview"
  );
  const [target, setTarget] = React.useState("all");
  const onTarget = (v) => { if (v === "__add__") return; setTarget(v); };

  React.useEffect(() => {
    const onHash = () => {
      const id = (window.location.hash || "").replace(/^#/, "");
      if (ALL_ITEMS.some((i) => i.id === id)) setActiveId(id);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (id) => {
    setActiveId(id);
    window.location.hash = id;
    window.requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  };

  const active = ALL_ITEMS.find((i) => i.id === activeId) || ALL_ITEMS[0];
  const Screen = MIST_SCREENS[activeId] || MOverview;

  return (
    <MistShell groups={MIST_NAV} active={active} activeId={activeId} onNavigate={navigate}
      target={target} onTarget={onTarget} repos={MIST_REPOS}>
      <Screen target={target} />
    </MistShell>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
