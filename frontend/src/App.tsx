import { useEffect, useState } from "react";
import { Activity, ArrowUpRight, Bot, BriefcaseBusiness, Building2, ChartNoAxesCombined, ChevronRight, CircleHelp, CreditCard, FileText, LayoutDashboard, LockKeyhole, Package, Settings2, ShieldCheck, Users } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
type ApiStatus = "checking" | "online" | "offline";
const modules = [
  { icon: ChartNoAxesCombined, title: "Financial Intelligence", detail: "Understand your business finances", tag: "Coming next" },
  { icon: FileText, title: "Invoices & Quotes", detail: "Create and manage business documents", tag: "Planned" },
  { icon: Users, title: "Customers & CRM", detail: "Build stronger customer relationships", tag: "Planned" },
  { icon: Package, title: "Inventory & Procurement", detail: "Keep stock and suppliers in view", tag: "Planned" },
  { icon: BriefcaseBusiness, title: "People & Recruitment", detail: "Manage your team and hiring pipeline", tag: "Planned" },
  { icon: Bot, title: "AI Business Manager", detail: "Ask questions grounded in your records", tag: "Planned" },
];

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/health`, { signal: controller.signal }).then((response) => {
      if (!response.ok) throw new Error("API unavailable");
      return response.json();
    }).then(() => setApiStatus("online")).catch(() => {
      if (!controller.signal.aborted) setApiStatus("offline");
    });
    return () => controller.abort();
  }, []);

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="BusinessBrain home"><div className="brand-mark"><Activity size={22}/></div><span>Business<span className="brand-accent">Brain</span></span></a>
      <div className="workspace-label">WORKSPACE</div>
      <button className="workspace-switch"><span className="workspace-icon"><Building2 size={17}/></span><span><strong>Your business</strong><small>Workspace setup pending</small></span><ChevronRight size={16}/></button>
      <nav className="navigation" aria-label="Main navigation">
        <a className="nav-item active" href="#overview"><LayoutDashboard size={18}/>Overview</a>
        <a className="nav-item" href="#finance"><CreditCard size={18}/>Finance</a>
        <a className="nav-item" href="#customers"><Users size={18}/>Customers</a>
        <a className="nav-item" href="#operations"><Package size={18}/>Operations</a>
        <a className="nav-item" href="#people"><BriefcaseBusiness size={18}/>People & HR</a>
        <a className="nav-item" href="#network"><Building2 size={18}/>Business Network</a>
      </nav>
      <div className="sidebar-bottom"><a className="nav-item" href="#settings"><Settings2 size={18}/>Settings</a><a className="nav-item" href="#help"><CircleHelp size={18}/>Help & support</a><div className="security-note"><ShieldCheck size={17}/><span>Designed with business data security at its core.</span></div></div>
    </aside>
    <main className="main-content" id="overview">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14}/> <strong>Overview</strong></div><div className="topbar-actions"><span className={`api-indicator ${apiStatus}`}><i/>{apiStatus === "online" ? "API connected" : apiStatus === "checking" ? "Connecting…" : "API offline"}</span><button className="icon-button" aria-label="Security status"><LockKeyhole size={18}/></button><div className="avatar">BB</div></div></header>
      <section className="welcome-section"><div><div className="eyebrow">YOUR BUSINESS. ONE INTELLIGENT BRAIN.</div><h1>Good business starts<br/><span>with clarity.</span></h1><p>Your business workspace is taking shape. Soon, your essential operations, intelligence and team will work together in one place.</p><button className="primary-button" disabled>Set up your business <ArrowUpRight size={17}/></button></div><div className="welcome-visual" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="brain-core"><Bot size={52} strokeWidth={1.25}/></div><div className="orbit-dot dot-one"/><div className="orbit-dot dot-two"/><div className="orbit-dot dot-three"/><div className="visual-caption">BUSINESS INTELLIGENCE</div></div></section>
      <section className="stats-grid" aria-label="Workspace summary"><div className="stat-card"><span className="stat-icon"><Building2 size={18}/></span><span className="stat-label">Business profile</span><strong>Not set up</strong><small>Complete onboarding to begin</small></div><div className="stat-card"><span className="stat-icon"><Users size={18}/></span><span className="stat-label">Team members</span><strong>—</strong><small>Invite your team later</small></div><div className="stat-card"><span className="stat-icon"><CreditCard size={18}/></span><span className="stat-label">Financial overview</span><strong>—</strong><small>Connect your records</small></div><div className="stat-card"><span className="stat-icon"><Activity size={18}/></span><span className="stat-label">System status</span><strong>{apiStatus === "online" ? "Operational" : apiStatus === "checking" ? "Checking" : "Offline"}</strong><small>{apiStatus === "online" ? "Backend health check passed" : "Waiting for backend connection"}</small></div></section>
      <section className="modules-section"><div className="section-heading"><div><div className="eyebrow">THE BUSINESS OPERATING SYSTEM</div><h2>Your business, connected.</h2><p>One workspace for the work that moves your business forward.</p></div><span className="module-count">06 CORE MODULES</span></div><div className="module-grid">{modules.map(({icon: Icon,title,detail,tag}) => <article className="module-card" key={title}><div className="module-icon"><Icon size={20}/></div><span className="module-tag">{tag}</span><h3>{title}</h3><p>{detail}</p><span className="module-footer">Part of BusinessBrain <ArrowUpRight size={14}/></span></article>)}</div></section>
      <footer className="footer"><span>BusinessBrain © 2026</span><span>BUILD THE INTELLIGENCE THAT RUNS BUSINESSES.</span></footer>
    </main>
  </div>;
}
