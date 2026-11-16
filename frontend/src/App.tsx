import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Activity, ArrowUpRight, Bot, BriefcaseBusiness, Building2, ChartNoAxesCombined, ChevronRight, CircleHelp, CreditCard, FileText, LayoutDashboard, LockKeyhole, LogOut, Package, Settings2, ShieldCheck, Users } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
type ApiStatus = "checking" | "online" | "offline";
type BusinessProfile = { name: string; industry: string; country: string; profile_image_data_url?: string | null; registration_number?: string | null; website?: string | null; contact_email?: string | null; phone?: string | null; address_line?: string | null; city?: string | null; province?: string | null; postal_code?: string | null; description?: string | null };
type AuthData = { access_token: string; user: { id: string; email: string; full_name: string }; business: BusinessProfile & { id: string } };
const STORAGE_KEY = "businessbrain.session";
const modules = [
  { icon: ChartNoAxesCombined, title: "Financial Intelligence", detail: "Understand your business finances", tag: "Coming next" },
  { icon: FileText, title: "Invoices & Quotes", detail: "Create and manage business documents", tag: "Planned" },
  { icon: Users, title: "Customers & CRM", detail: "Build stronger customer relationships", tag: "Planned" },
  { icon: Package, title: "Inventory & Procurement", detail: "Keep stock and suppliers in view", tag: "Planned" },
  { icon: BriefcaseBusiness, title: "People & Recruitment", detail: "Manage your team and hiring pipeline", tag: "Planned" },
  { icon: Bot, title: "AI Business Manager", detail: "Ask questions grounded in your records", tag: "Planned" },
];

function readSession(): AuthData | null {
  try {
    const value = sessionStorage.getItem(STORAGE_KEY);
    return value ? JSON.parse(value) as AuthData : null;
  } catch { return null; }
}

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [session, setSession] = useState<AuthData | null>(readSession);
  const [mode, setMode] = useState<"register" | "login">("register");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [industry, setIndustry] = useState("");
  const [country, setCountry] = useState("ZA");
  const [profileImage, setProfileImage] = useState<string | null>(null);
  const [imageError, setImageError] = useState("");
  const [profileDraft, setProfileDraft] = useState<BusinessProfile>(() => ({
    name: session?.business.name ?? "", industry: session?.business.industry ?? "", country: session?.business.country ?? "ZA",
    registration_number: session?.business.registration_number ?? "", website: session?.business.website ?? "",
    contact_email: session?.business.contact_email ?? "", phone: session?.business.phone ?? "",
    address_line: session?.business.address_line ?? "", city: session?.business.city ?? "",
    province: session?.business.province ?? "", postal_code: session?.business.postal_code ?? "",
    description: session?.business.description ?? "", profile_image_data_url: session?.business.profile_image_data_url ?? null,
  }));
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");

  function handleProfileImage(file?: File) {
    setImageError("");
    if (!file) { setProfileImage(null); return; }
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) { setImageError("Choose a JPG, PNG or WebP image."); return; }
    if (file.size > 2 * 1024 * 1024) { setImageError("The image must be 2 MB or smaller."); return; }
    const reader = new FileReader();
    reader.onload = () => { const image = typeof reader.result === "string" ? reader.result : null; setProfileImage(image); setProfileDraft(current => ({ ...current, profile_image_data_url: image })); };
    reader.onerror = () => setImageError("Image could not be read. Please try another file.");
    reader.readAsDataURL(file);
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/health`, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("API unavailable"); return response.json(); })
      .then(() => setApiStatus("online"))
      .catch(() => { if (!controller.signal.aborted) setApiStatus("offline"); });
    return () => controller.abort();
  }, []);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const payload = mode === "register"
      ? { full_name: fullName, email, password, business_name: businessName, industry, country, profile_image_data_url: profileImage }
      : { email, password };
    try {
      const response = await fetch(`${API_BASE}/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "We couldn't complete your request. Please try again.");
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      setSession(data as AuthData);
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function updateProfileField(field: keyof BusinessProfile, value: string) {
    setProfileDraft(current => ({ ...current, [field]: value }));
  }

  async function saveBusinessProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    setProfileBusy(true);
    setProfileMessage("");
    try {
      const response = await fetch(API_BASE + "/auth/business/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + session.access_token },
        body: JSON.stringify(profileDraft),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "We couldn't save your business profile.");
      const nextSession = { ...session, business: data };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(nextSession));
      setSession(nextSession);
      setProfileDraft(data);
      setProfileImage(data.profile_image_data_url ?? null);
      setProfileMessage("Business profile saved.");
    } catch (err) {
      setProfileMessage(err instanceof Error ? err.message : "Unable to save your profile.");
    } finally {
      setProfileBusy(false);
    }
  }

  function signOut() {
    sessionStorage.removeItem(STORAGE_KEY);
    setSession(null);
    setMode("login");
  }

  if (!session) return <div className="auth-page">
    <div className="auth-brand"><div className="brand-mark"><Activity size={22}/></div><span>Business<span className="brand-accent">Brain</span></span></div>
    <div className="auth-layout">
      <section className="auth-intro">
        <div className="eyebrow">YOUR BUSINESS. ONE INTELLIGENT BRAIN.</div>
        <h1>Run your business<br/><span>with clarity.</span></h1>
        <p>Bring your operations, people and business intelligence together in one secure workspace.</p>
        <div className="auth-points"><div><ShieldCheck size={18}/> Built around your business data</div><div><Building2 size={18}/> One workspace for your team</div><div><Bot size={18}/> Intelligence that grows with you</div></div>
      </section>
      <section className="auth-card">
        <div className="auth-tabs"><button className={mode === "register" ? "selected" : ""} onClick={() => {setMode("register");setError("");}}>Create account</button><button className={mode === "login" ? "selected" : ""} onClick={() => {setMode("login");setError("");}}>Sign in</button></div>
        <div className="auth-card-heading"><h2>{mode === "register" ? "Create your workspace" : "Welcome back"}</h2><p>{mode === "register" ? "Start by setting up your owner account and business." : "Sign in to continue to your business workspace."}</p></div>
        <form onSubmit={submitAuth} className="auth-form">
          {mode === "register" && <><label>Full name<input required minLength={2} maxLength={160} autoComplete="name" value={fullName} onChange={e=>setFullName(e.target.value)} placeholder="Your full name"/></label></>}
          <label>Business email<input required type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com"/></label>
          <label>Password<input required type="password" minLength={mode === "register" ? 12 : 1} maxLength={128} autoComplete={mode === "register" ? "new-password" : "current-password"} value={password} onChange={e=>setPassword(e.target.value)} placeholder={mode === "register" ? "At least 12 characters" : "Your password"}/></label>
          {mode === "register" && <><label>Business name<input required minLength={2} maxLength={200} value={businessName} onChange={e=>setBusinessName(e.target.value)} placeholder="Your registered or trading name"/></label><div className="profile-upload"><div className="profile-upload-preview">{profileImage ? <img src={profileImage} alt="Business profile preview"/> : <Building2 size={25}/>}</div><div className="profile-upload-copy"><strong>Business profile picture</strong><span>Add your company logo or business photo. Optional.</span><label className="profile-upload-button">{profileImage ? "Change image" : "Upload image"}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>handleProfileImage(e.target.files?.[0])}/></label>{imageError && <small className="profile-upload-error">{imageError}</small>}</div></div><div className="auth-two-col"><label>Industry<input required minLength={2} maxLength={120} value={industry} onChange={e=>setIndustry(e.target.value)} placeholder="e.g. Retail"/></label><label>Country<select value={country} onChange={e=>setCountry(e.target.value)}><option value="ZA">South Africa</option><option value="NG">Nigeria</option><option value="KE">Kenya</option><option value="GH">Ghana</option><option value="BW">Botswana</option><option value="ZM">Zambia</option><option value="ZW">Zimbabwe</option><option value="OT">Other</option></select></label></div></>}
          {error && <div className="auth-error" role="alert">{error}</div>}
          {apiStatus === "offline" && <div className="auth-warning">The BusinessBrain API is not reachable yet. Check that the backend is running and try again.</div>}
          <button className="auth-submit" type="submit" disabled={busy || apiStatus !== "online"}>{busy ? "Please wait…" : mode === "register" ? "Create business workspace" : "Sign in securely"} <ArrowUpRight size={17}/></button>
        </form>
        <div className="auth-footnote"><LockKeyhole size={14}/> Your password is securely hashed. Never share it with anyone.</div>
      </section>
    </div>
    <footer className="auth-footer">BusinessBrain © 2026 <span>BUILD THE INTELLIGENCE THAT RUNS BUSINESSES.</span></footer>
  </div>;

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="BusinessBrain home"><div className="brand-mark"><Activity size={22}/></div><span>Business<span className="brand-accent">Brain</span></span></a>
      <div className="workspace-label">WORKSPACE</div>
      <div className="workspace-switch"><span className="workspace-icon">{session.business.profile_image_data_url ? <img src={session.business.profile_image_data_url} alt="Business profile"/> : <Building2 size={17}/>}</span><span><strong>{session.business.name}</strong><small>{session.business.industry}</small></span><ChevronRight size={16}/></div>
      <nav className="navigation" aria-label="Main navigation"><a className="nav-item active" href="#overview"><LayoutDashboard size={18}/>Overview</a><a className="nav-item" href="#finance"><CreditCard size={18}/>Finance</a><a className="nav-item" href="#customers"><Users size={18}/>Customers</a><a className="nav-item" href="#operations"><Package size={18}/>Operations</a><a className="nav-item" href="#people"><BriefcaseBusiness size={18}/>People & HR</a><a className="nav-item" href="#network"><Building2 size={18}/>Business Network</a></nav>
      <div className="sidebar-bottom"><a className="nav-item" href="#settings"><Settings2 size={18}/>Settings</a><a className="nav-item" href="#help"><CircleHelp size={18}/>Help & support</a><button className="nav-item signout-button" onClick={signOut}><LogOut size={18}/>Sign out</button><div className="security-note"><ShieldCheck size={17}/><span>Designed with business data security at its core.</span></div></div>
    </aside>
    <main className="main-content" id="overview">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14}/> <strong>Overview</strong></div><div className="topbar-actions"><span className={`api-indicator ${apiStatus}`}><i/>{apiStatus === "online" ? "API connected" : "API offline"}</span><button className="icon-button" aria-label="Security status"><LockKeyhole size={18}/></button><div className="avatar">{session.user.full_name.split(" ").map(x=>x[0]).slice(0,2).join("").toUpperCase()}</div></div></header>
      <section className="welcome-section"><div><div className="eyebrow">YOUR BUSINESS. ONE INTELLIGENT BRAIN.</div><h1>Welcome,<br/><span>{session.user.full_name.split(" ")[0]}.</span></h1><p>Your {session.business.name} workspace has been created. This is the foundation for bringing your business operations and intelligence together.</p><div className="workspace-created"><ShieldCheck size={16}/> Business workspace created successfully</div></div><div className="welcome-visual" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="brain-core"><Bot size={52} strokeWidth={1.25}/></div><div className="orbit-dot dot-one"/><div className="orbit-dot dot-two"/><div className="orbit-dot dot-three"/><div className="visual-caption">BUSINESS INTELLIGENCE</div></div></section>
      <section className="profile-centre" id="business-profile">
        <div className="profile-centre-heading"><div><div className="eyebrow">BUSINESS IDENTITY</div><h2>Business Profile & Onboarding</h2><p>Complete your business details. You control what information is shared publicly later.</p></div><span className="profile-status">Editable anytime</span></div>
        <form className="business-profile-form" onSubmit={saveBusinessProfile}>
          <div className="profile-identity-row"><div className="profile-upload-preview profile-large-preview">{(profileImage ?? profileDraft.profile_image_data_url) ? <img src={(profileImage ?? profileDraft.profile_image_data_url) as string} alt="Business logo"/> : <Building2 size={28}/>}</div><div><strong>Business logo or profile picture</strong><small>JPG, PNG or WebP · maximum 2 MB</small><label className="profile-upload-button">{(profileImage ?? profileDraft.profile_image_data_url) ? "Change picture" : "Upload picture"}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>handleProfileImage(e.target.files?.[0])}/></label>{imageError && <small className="profile-upload-error">{imageError}</small>}</div></div>
          <div className="profile-fields-grid">
            <label>Business name<input required maxLength={200} value={profileDraft.name} onChange={e=>updateProfileField("name",e.target.value)}/></label>
            <label>Industry<input required maxLength={120} value={profileDraft.industry} onChange={e=>updateProfileField("industry",e.target.value)}/></label>
            <label>Registration number<input maxLength={100} value={profileDraft.registration_number ?? ""} onChange={e=>updateProfileField("registration_number",e.target.value)} placeholder="e.g. CIPC number"/></label>
            <label>Website<input type="url" maxLength={255} value={profileDraft.website ?? ""} onChange={e=>updateProfileField("website",e.target.value)} placeholder="https://yourbusiness.co.za"/></label>
            <label>Business email<input type="email" value={profileDraft.contact_email ?? ""} onChange={e=>updateProfileField("contact_email",e.target.value)} placeholder="info@yourbusiness.co.za"/></label>
            <label>Business phone<input type="tel" maxLength={40} value={profileDraft.phone ?? ""} onChange={e=>updateProfileField("phone",e.target.value)} placeholder="+27..."/></label>
            <label className="profile-field-wide">Street address<input maxLength={255} value={profileDraft.address_line ?? ""} onChange={e=>updateProfileField("address_line",e.target.value)}/></label>
            <label>City / Town<input maxLength={120} value={profileDraft.city ?? ""} onChange={e=>updateProfileField("city",e.target.value)}/></label>
            <label>Province / State<input maxLength={120} value={profileDraft.province ?? ""} onChange={e=>updateProfileField("province",e.target.value)}/></label>
            <label>Postal code<input maxLength={24} value={profileDraft.postal_code ?? ""} onChange={e=>updateProfileField("postal_code",e.target.value)}/></label>
            <label>Country code<input maxLength={2} value={profileDraft.country} onChange={e=>updateProfileField("country",e.target.value.toUpperCase())}/></label>
            <label className="profile-field-wide">About the business<textarea rows={4} maxLength={2000} value={profileDraft.description ?? ""} onChange={e=>updateProfileField("description",e.target.value)} placeholder="Describe what your business does, the products or services you offer, and who you serve."/></label>
          </div>
          <div className="profile-form-footer">{profileMessage && <span className={profileMessage.includes("saved") ? "profile-success" : "profile-upload-error"} role="status">{profileMessage}</span>}<button className="auth-submit profile-save" type="submit" disabled={profileBusy}>{profileBusy ? "Saving profile…" : "Save business profile"} <ArrowUpRight size={16}/></button></div>
        </form>
      </section>
      <section className="stats-grid" aria-label="Workspace summary"><div className="stat-card"><span className="stat-icon">{session.business.profile_image_data_url ? <img src={session.business.profile_image_data_url} alt="Business profile"/> : <Building2 size={18}/>}</span><span className="stat-label">Business profile</span><strong>Created</strong><small>{session.business.country} · {session.business.industry}</small></div><div className="stat-card"><span className="stat-icon"><Users size={18}/></span><span className="stat-label">Your role</span><strong>Owner</strong><small>Workspace administrator</small></div><div className="stat-card"><span className="stat-icon"><CreditCard size={18}/></span><span className="stat-label">Financial overview</span><strong>Not connected</strong><small>Add records as you get started</small></div><div className="stat-card"><span className="stat-icon"><Activity size={18}/></span><span className="stat-label">System status</span><strong>{apiStatus === "online" ? "Connected" : "Offline"}</strong><small>Backend health check</small></div></section>
      <section className="modules-section"><div className="section-heading"><div><div className="eyebrow">THE BUSINESS OPERATING SYSTEM</div><h2>Your business, connected.</h2><p>One workspace for the work that moves your business forward.</p></div><span className="module-count">06 CORE MODULES</span></div><div className="module-grid">{modules.map(({icon: Icon,title,detail,tag}) => <article className="module-card" key={title}><div className="module-icon"><Icon size={20}/></div><span className="module-tag">{tag}</span><h3>{title}</h3><p>{detail}</p><span className="module-footer">Part of BusinessBrain <ArrowUpRight size={14}/></span></article>)}</div></section>
      <footer className="footer"><span>BusinessBrain © 2026</span><span>BUILD THE INTELLIGENCE THAT RUNS BUSINESSES.</span></footer>
    </main>
  </div>;
}
