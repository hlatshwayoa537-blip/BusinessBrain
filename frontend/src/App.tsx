import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Activity, ArrowUpRight, Bot, BriefcaseBusiness, Building2, ChartNoAxesCombined, ChevronRight, CircleHelp, CreditCard, FileText, LayoutDashboard, LockKeyhole, LogOut, Package, Settings2, ShieldCheck, Users } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
type ApiStatus = "checking" | "online" | "offline";
type BusinessProfile = { name: string; industry: string; country: string; profile_image_data_url?: string | null; registration_number?: string | null; website?: string | null; contact_email?: string | null; phone?: string | null; address_line?: string | null; city?: string | null; province?: string | null; postal_code?: string | null; description?: string | null; directory_listed?: boolean; public_email?: boolean; public_phone?: boolean; public_website?: boolean; public_location?: boolean };
type PublicBusiness = { id: string; name: string; industry: string; country: string; profile_image_data_url?: string | null; website?: string | null; contact_email?: string | null; phone?: string | null; city?: string | null; province?: string | null; description?: string | null };
type NetworkInvitation = { id: string; host_business_id: string; host_business_name: string; invited_business_id: string; invited_business_name: string; invitation_message?: string | null; status: string; expires_at: string; created_at: string };
type NetworkConversation = { id: string; host_business_id: string; host_business_name: string; invited_business_id: string; invited_business_name: string; status: string; created_at: string; deal_room_id?: string | null; deal_room_status?: string | null };
type NetworkMessage = { id: string; sender_business_id: string; sender_business_name: string; sender_user_name: string; body: string; created_at: string };
type DealRoom = { id: string; conversation_id: string; status: string; created_at: string; updated_at: string };
type Quotation = { id: string; deal_room_id: string; issuer_business_id: string; issuer_business_name: string; reference: string; title: string; currency: string; line_items: {description:string;quantity:string;unit_price:string;tax_rate:string;line_subtotal:string;line_tax:string;line_total:string}[]; subtotal: string; tax_total: string; total: string; notes?: string | null; valid_until?: string | null; status: string; response_note?: string | null; created_at: string };
type QuoteLineDraft = { description: string; quantity: string; unit_price: string; tax_rate: string };
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
    directory_listed: session?.business.directory_listed ?? false, public_email: session?.business.public_email ?? false,
    public_phone: session?.business.public_phone ?? false, public_website: session?.business.public_website ?? false,
    public_location: session?.business.public_location ?? false,
  }));
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");
  const [directoryResults, setDirectoryResults] = useState<PublicBusiness[]>([]);
  const [directoryQuery, setDirectoryQuery] = useState("");
  const [directoryBusy, setDirectoryBusy] = useState(false);
  const [directoryMessage, setDirectoryMessage] = useState("");
  const [incomingInvitations, setIncomingInvitations] = useState<NetworkInvitation[]>([]);
  const [conversations, setConversations] = useState<NetworkConversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<NetworkConversation | null>(null);
  const [conversationMessages, setConversationMessages] = useState<NetworkMessage[]>([]);
  const [dealRoomMessages, setDealRoomMessages] = useState<NetworkMessage[]>([]);
  const [dealRoom, setDealRoom] = useState<DealRoom | null>(null);
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [quoteTitle, setQuoteTitle] = useState("");
  const [quoteCurrency, setQuoteCurrency] = useState("ZAR");
  const [quoteValidUntil, setQuoteValidUntil] = useState("");
  const [quoteNotes, setQuoteNotes] = useState("");
  const [quoteLines, setQuoteLines] = useState<QuoteLineDraft[]>([{description:"",quantity:"1",unit_price:"",tax_rate:"15"}]);
  const [inviteTarget, setInviteTarget] = useState<PublicBusiness | null>(null);
  const [invitePassword, setInvitePassword] = useState("");
  const [inviteMessage, setInviteMessage] = useState("");
  const [acceptPassword, setAcceptPassword] = useState("");
  const [conversationDraft, setConversationDraft] = useState("");
  const [dealDraft, setDealDraft] = useState("");
  const [networkActionBusy, setNetworkActionBusy] = useState(false);
  const [networkActionMessage, setNetworkActionMessage] = useState("");

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

  async function networkRequest(path: string, method = "GET", body?: unknown) {
    if (!session) throw new Error("Please sign in again.");
    const response = await fetch(API_BASE + path, {
      method, headers: { Authorization: "Bearer " + session.access_token, ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The Business Network request failed.");
    return data;
  }

  async function refreshNetwork() {
    if (!session) return;
    try {
      const [invites, chats] = await Promise.all([
        networkRequest("/network/invitations?direction=incoming"),
        networkRequest("/network/conversations"),
      ]);
      setIncomingInvitations(invites as NetworkInvitation[]);
      setConversations(chats as NetworkConversation[]);
    } catch (err) {
      setNetworkActionMessage(err instanceof Error ? err.message : "Could not refresh conversations.");
    }
  }

  useEffect(() => { if (session) void refreshNetwork(); }, [session?.access_token]);

  useEffect(() => {
    if (!session || !selectedConversation) { setConversationMessages([]); setDealRoomMessages([]); setDealRoom(null); return; }
    let cancelled = false;
    async function loadMessages() {
      try {
        const messages = await networkRequest("/network/conversations/" + selectedConversation!.id + "/messages");
        if (!cancelled) setConversationMessages(messages as NetworkMessage[]);
        if (selectedConversation!.deal_room_id) {
          const room = { id: selectedConversation!.deal_room_id, conversation_id: selectedConversation!.id, status: selectedConversation!.deal_room_status ?? "discussion", created_at: "", updated_at: "" };
          const dealMessages = await networkRequest("/network/deal-rooms/" + room.id + "/messages");
          const dealQuotes = await networkRequest("/network/deal-rooms/" + room.id + "/quotations");
          if (!cancelled) { setDealRoom(room); setDealRoomMessages(dealMessages as NetworkMessage[]); setQuotations(dealQuotes as Quotation[]); }
        } else if (!cancelled) { setDealRoom(null); setDealRoomMessages([]); setQuotations([]); }
      } catch (err) { if (!cancelled) setNetworkActionMessage(err instanceof Error ? err.message : "Could not load messages."); }
    }
    void loadMessages();
    return () => { cancelled = true; };
  }, [session?.access_token, selectedConversation?.id, selectedConversation?.deal_room_id]);

  async function sendBusinessInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!inviteTarget) return;
    setNetworkActionBusy(true); setNetworkActionMessage("");
    try {
      await networkRequest("/network/invitations", "POST", { invited_business_id: inviteTarget.id, invitation_message: inviteMessage, access_password: invitePassword });
      setNetworkActionMessage("Invitation sent. Share the password separately with the invited business contact.");
      setInviteTarget(null); setInvitePassword(""); setInviteMessage(""); await refreshNetwork();
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Could not send invitation."); }
    finally { setNetworkActionBusy(false); }
  }

  async function acceptBusinessInvitation(invitationId: string) {
    setNetworkActionBusy(true); setNetworkActionMessage("");
    try {
      const conversation = await networkRequest("/network/invitations/" + invitationId + "/accept", "POST", { access_password: acceptPassword }) as NetworkConversation;
      setAcceptPassword(""); setSelectedConversation(conversation);
      setNetworkActionMessage("Invitation accepted. Your private conversation is ready."); await refreshNetwork();
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Could not accept invitation."); }
    finally { setNetworkActionBusy(false); }
  }

  async function rejectBusinessInvitation(invitationId: string) {
    setNetworkActionBusy(true); setNetworkActionMessage("");
    try { await networkRequest("/network/invitations/" + invitationId + "/reject", "POST"); await refreshNetwork(); setNetworkActionMessage("Invitation declined."); }
    catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Could not decline invitation."); }
    finally { setNetworkActionBusy(false); }
  }

  async function sendConversationMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedConversation || !conversationDraft.trim()) return;
    try {
      await networkRequest("/network/conversations/" + selectedConversation.id + "/messages", "POST", { body: conversationDraft });
      setConversationDraft("");
      const messages = await networkRequest("/network/conversations/" + selectedConversation.id + "/messages");
      setConversationMessages(messages as NetworkMessage[]);
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Message could not be sent."); }
  }

  async function openDealRoom() {
    if (!selectedConversation) return;
    try {
      const room = await networkRequest("/network/conversations/" + selectedConversation.id + "/deal-room", "POST") as DealRoom;
      setDealRoom(room);
      const updated = { ...selectedConversation, deal_room_id: room.id, deal_room_status: room.status };
      setSelectedConversation(updated);
      setConversations(current => current.map(item => item.id === updated.id ? updated : item));
      setDealRoomMessages([]);
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Deal Room could not be opened."); }
  }

  async function sendDealRoomMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dealRoom || !dealDraft.trim()) return;
    try {
      await networkRequest("/network/deal-rooms/" + dealRoom.id + "/messages", "POST", { body: dealDraft });
      setDealDraft("");
      const messages = await networkRequest("/network/deal-rooms/" + dealRoom.id + "/messages");
      setDealRoomMessages(messages as NetworkMessage[]);
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Deal Room message could not be sent."); }
  }


  async function sendQuotation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dealRoom) return;
    try {
      const quote = await networkRequest("/network/deal-rooms/" + dealRoom.id + "/quotations", "POST", {
        title: quoteTitle, currency: quoteCurrency, valid_until: quoteValidUntil || null, notes: quoteNotes || null,
        line_items: quoteLines.map(line => ({...line, quantity: Number(line.quantity), unit_price: Number(line.unit_price), tax_rate: Number(line.tax_rate)}))
      }) as Quotation;
      setQuotations(current => [quote, ...current]);
      setQuoteTitle(""); setQuoteValidUntil(""); setQuoteNotes("");
      setQuoteLines([{description:"",quantity:"1",unit_price:"",tax_rate:"15"}]);
      setNetworkActionMessage("Quotation " + quote.reference + " shared in this Deal Room.");
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Quotation could not be shared."); }
  }

  async function decideQuotation(quotationId: string, decision: "accepted" | "declined") {
    try {
      const updated = await networkRequest("/network/quotations/" + quotationId + "/decision", "POST", {decision}) as Quotation;
      setQuotations(current => current.map(item => item.id === quotationId ? updated : item));
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Quotation response could not be saved."); }
  }

  async function updateDealStatus(status: string) {
    if (!dealRoom) return;
    try {
      const updated = await networkRequest("/network/deal-rooms/" + dealRoom.id, "PATCH", { status }) as DealRoom;
      setDealRoom(updated);
      if (selectedConversation) {
        const next = { ...selectedConversation, deal_room_status: updated.status };
        setSelectedConversation(next);
        setConversations(current => current.map(item => item.id === next.id ? next : item));
      }
    } catch (err) { setNetworkActionMessage(err instanceof Error ? err.message : "Deal status could not be updated."); }
  }

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
      setProfileDraft({
        name: data.business.name, industry: data.business.industry, country: data.business.country,
        registration_number: data.business.registration_number ?? "", website: data.business.website ?? "",
        contact_email: data.business.contact_email ?? "", phone: data.business.phone ?? "",
        address_line: data.business.address_line ?? "", city: data.business.city ?? "",
        province: data.business.province ?? "", postal_code: data.business.postal_code ?? "",
        description: data.business.description ?? "", profile_image_data_url: data.business.profile_image_data_url ?? null,
        directory_listed: data.business.directory_listed ?? false, public_email: data.business.public_email ?? false,
        public_phone: data.business.public_phone ?? false, public_website: data.business.public_website ?? false,
        public_location: data.business.public_location ?? false,
      });
      setProfileImage(data.business.profile_image_data_url ?? null);
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

  async function searchBusinessDirectory(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!session) return;
    setDirectoryBusy(true);
    setDirectoryMessage("");
    try {
      const params = new URLSearchParams();
      if (directoryQuery.trim()) params.set("q", directoryQuery.trim());
      const response = await fetch(API_BASE + "/network/businesses?" + params.toString(), {
        headers: { Authorization: "Bearer " + session.access_token },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to load the Business Network.");
      setDirectoryResults(data as PublicBusiness[]);
      if (!data.length) setDirectoryMessage("No listed businesses found yet. Try another search or invite a business to join.");
    } catch (err) {
      setDirectoryMessage(err instanceof Error ? err.message : "Unable to load the directory.");
    } finally {
      setDirectoryBusy(false);
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
      <nav className="navigation" aria-label="Main navigation"><a className="nav-item active" href="#overview"><LayoutDashboard size={18}/>Overview</a><a className="nav-item" href="#finance"><CreditCard size={18}/>Finance</a><a className="nav-item" href="#customers"><Users size={18}/>Customers</a><a className="nav-item" href="#operations"><Package size={18}/>Operations</a><a className="nav-item" href="#people"><BriefcaseBusiness size={18}/>People & HR</a><a className="nav-item" href="#business-profile"><Building2 size={18}/>Business Profile</a><a className="nav-item" href="#network"><Building2 size={18}/>Business Network</a><a className="nav-item" href="#private-conversations"><LockKeyhole size={18}/>Private Conversations</a></nav>
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
          <div className="network-visibility">
            <div><strong>Business Network visibility</strong><p>Your business is private until you turn directory listing on. You can change these settings at any time.</p></div>
            <label className="visibility-main"><input type="checkbox" checked={!!profileDraft.directory_listed} onChange={e=>setProfileDraft(current=>({...current,directory_listed:e.target.checked}))}/> Show my business in the Business Network directory</label>
            <div className="visibility-options">
              <label><input type="checkbox" checked={!!profileDraft.public_email} disabled={!profileDraft.directory_listed} onChange={e=>setProfileDraft(current=>({...current,public_email:e.target.checked}))}/> Show business email</label>
              <label><input type="checkbox" checked={!!profileDraft.public_phone} disabled={!profileDraft.directory_listed} onChange={e=>setProfileDraft(current=>({...current,public_phone:e.target.checked}))}/> Show business phone</label>
              <label><input type="checkbox" checked={!!profileDraft.public_website} disabled={!profileDraft.directory_listed} onChange={e=>setProfileDraft(current=>({...current,public_website:e.target.checked}))}/> Show website</label>
              <label><input type="checkbox" checked={!!profileDraft.public_location} disabled={!profileDraft.directory_listed} onChange={e=>setProfileDraft(current=>({...current,public_location:e.target.checked}))}/> Show city and province</label>
            </div>
          </div>
          <div className="profile-form-footer">{profileMessage && <span className={profileMessage.includes("saved") ? "profile-success" : "profile-upload-error"} role="status">{profileMessage}</span>}<button className="auth-submit profile-save" type="submit" disabled={profileBusy}>{profileBusy ? "Saving profile…" : "Save business profile & privacy"} <ArrowUpRight size={16}/></button></div>
        </form>
      </section>
      <section className="network-centre" id="network">
        <div className="profile-centre-heading"><div><div className="eyebrow">BUSINESS NETWORK</div><h2>Discover businesses</h2><p>Find companies that have chosen to make their profiles visible to the network.</p></div><span className="profile-status">Opt-in directory</span></div>
        <form className="directory-search" onSubmit={searchBusinessDirectory}><input aria-label="Search businesses" value={directoryQuery} onChange={e=>setDirectoryQuery(e.target.value)} placeholder="Search by business, industry, service or city"/><button className="auth-submit" type="submit" disabled={directoryBusy}>{directoryBusy ? "Searching…" : "Search businesses"} <ArrowUpRight size={16}/></button></form>
        {directoryMessage && <p className="directory-message" role="status">{directoryMessage}</p>}
        <div className="directory-grid">{directoryResults.map(business=><article className="directory-card" key={business.id}>
          <div className="directory-card-head"><div className="directory-logo">{business.profile_image_data_url ? <img src={business.profile_image_data_url} alt="Business logo"/> : <Building2 size={22}/>}</div><div><h3>{business.name}</h3><span>{business.industry} · {business.country}</span></div></div>
          {business.description && <p className="directory-description">{business.description}</p>}
          {(business.city || business.province) && <p className="directory-meta">{[business.city,business.province].filter(Boolean).join(", ")}</p>}
          <div className="directory-contacts">{business.contact_email && <a href={"mailto:"+business.contact_email}>Email business</a>}{business.phone && <a href={"tel:"+business.phone}>Call business</a>}{business.website && <a href={business.website} target="_blank" rel="noreferrer">Website</a>}</div>
          <button className="network-invite-button" type="button" onClick={()=>{setInviteTarget(business);setNetworkActionMessage("");}}>Invite to private conversation</button>
        </article>)}</div>
      </section>
      {inviteTarget && <section className="network-panel invite-panel">
        <div className="profile-centre-heading"><div><div className="eyebrow">PRIVATE INVITATION</div><h2>Invite {inviteTarget.name}</h2><p>Create a password for the private conversation. Share it separately with your contact, not in this invitation.</p></div><button className="network-close" type="button" onClick={()=>setInviteTarget(null)}>Cancel</button></div>
        <form className="network-invite-form" onSubmit={sendBusinessInvitation}>
          <label>Conversation password<input required minLength={8} maxLength={128} type="password" value={invitePassword} onChange={e=>setInvitePassword(e.target.value)} placeholder="At least 8 characters"/></label>
          <label>Invitation message (optional)<textarea rows={3} maxLength={1000} value={inviteMessage} onChange={e=>setInviteMessage(e.target.value)} placeholder="Tell the business why you would like to connect."/></label>
          <button className="auth-submit" type="submit" disabled={networkActionBusy}>{networkActionBusy ? "Sending invitation…" : "Send private invitation"} <ArrowUpRight size={16}/></button>
        </form>
      </section>}
      <section className="network-panel" id="private-conversations">
        <div className="profile-centre-heading"><div><div className="eyebrow">SECURE BUSINESS COMMUNICATION</div><h2>Private conversations & Deal Rooms</h2><p>Invite another business, agree on a separate password, discuss privately and move into a Deal Room when you are ready.</p></div><span className="profile-status">Invite-only</span></div>
        {networkActionMessage && <p className="directory-message" role="status">{networkActionMessage}</p>}
        <div className="network-workspace-grid">
          <div className="network-list-column">
            <div className="network-subheading"><h3>Invitations</h3><span>{incomingInvitations.filter(item=>item.status==="pending").length} pending</span></div>
            {incomingInvitations.filter(item=>item.status==="pending").length===0 && <p className="network-empty">No pending invitations.</p>}
            {incomingInvitations.filter(item=>item.status==="pending").map(invite=><article className="invitation-card" key={invite.id}>
              <strong>{invite.host_business_name}</strong><p>{invite.invitation_message || "This business has invited you to a private conversation."}</p>
              <label>Conversation password<input type="password" minLength={8} value={acceptPassword} onChange={e=>setAcceptPassword(e.target.value)} placeholder="Enter password shared separately"/></label>
              <div className="invitation-actions"><button type="button" className="network-primary-button" disabled={networkActionBusy || acceptPassword.length<8} onClick={()=>acceptBusinessInvitation(invite.id)}>Accept</button><button type="button" className="network-secondary-button" disabled={networkActionBusy} onClick={()=>rejectBusinessInvitation(invite.id)}>Reject</button></div>
            </article>)}
            <div className="network-subheading conversation-list-heading"><h3>Conversations</h3><button type="button" onClick={()=>void refreshNetwork()}>Refresh</button></div>
            {conversations.length===0 && <p className="network-empty">Accepted private conversations will appear here.</p>}
            {conversations.map(chat=><button type="button" className={"conversation-select "+(selectedConversation?.id===chat.id?"selected":"")} key={chat.id} onClick={()=>setSelectedConversation(chat)}>
              <strong>{chat.host_business_id===session.business.id?chat.invited_business_name:chat.host_business_name}</strong>
              <span>{chat.deal_room_id ? "Deal Room · "+(chat.deal_room_status || "discussion").replaceAll("_"," ") : "Private conversation"}</span>
            </button>)}
          </div>
          <div className="network-chat-column">
            {!selectedConversation ? <div className="network-empty-state"><LockKeyhole size={30}/><strong>Your private workspace</strong><p>Select an accepted conversation to start messaging. Either business can open the Deal Room.</p></div> : <>
              <div className="chat-heading"><div><strong>{selectedConversation.host_business_id===session.business.id?selectedConversation.invited_business_name:selectedConversation.host_business_name}</strong><span>Private business conversation</span></div>{!selectedConversation.deal_room_id && <button type="button" className="network-primary-button" onClick={openDealRoom}>Open Deal Room</button>}</div>
              <div className="message-list">{conversationMessages.map(message=><article className={"message-bubble "+(message.sender_business_id===session.business.id?"own":"")} key={message.id}><strong>{message.sender_business_name} · {message.sender_user_name}</strong><p>{message.body}</p><time>{new Date(message.created_at).toLocaleString()}</time></article>)}{conversationMessages.length===0 && <p className="network-empty">No messages yet. Start the conversation.</p>}</div>
              <form className="message-compose" onSubmit={sendConversationMessage}><input value={conversationDraft} onChange={e=>setConversationDraft(e.target.value)} maxLength={5000} placeholder="Write a private message…" required/><button type="submit" disabled={!conversationDraft.trim()}>Send</button></form>
              {dealRoom && <div className="deal-room-panel">
                <div className="chat-heading"><div><strong>Deal Room</strong><span>Private negotiation space</span></div><select aria-label="Deal status" value={dealRoom.status} onChange={e=>updateDealStatus(e.target.value)}><option value="discussion">Discussion</option><option value="negotiation">Negotiation</option><option value="proposal_submitted">Proposal submitted</option><option value="agreement_reached">Agreement reached</option><option value="deal_completed">Deal completed</option><option value="deal_cancelled">Deal cancelled</option></select></div>
                <div className="message-list deal-messages">{dealRoomMessages.map(message=><article className={"message-bubble "+(message.sender_business_id===session.business.id?"own":"")} key={message.id}><strong>{message.sender_business_name}</strong><p>{message.body}</p><time>{new Date(message.created_at).toLocaleString()}</time></article>)}{dealRoomMessages.length===0 && <p className="network-empty">Use this room for proposals, commercial terms and closing discussions.</p>}</div>
                <form className="message-compose" onSubmit={sendDealRoomMessage}><input value={dealDraft} onChange={e=>setDealDraft(e.target.value)} maxLength={5000} placeholder="Write a Deal Room message…" required/><button type="submit" disabled={!dealDraft.trim()}>Send</button></form>
                <div className="quotation-section">
                  <div className="network-subheading"><h3>Shared quotations</h3><span>{quotations.length} quotations</span></div>
                  {quotations.map(quote=><article className="quotation-card" key={quote.id}>
                    <div className="quotation-card-head"><div><strong>{quote.title}</strong><small>{quote.reference} · from {quote.issuer_business_name}</small></div><span className={"quotation-status status-"+quote.status}>{quote.status.replaceAll("_"," ")}</span></div>
                    <div className="quotation-lines">{quote.line_items.map((line,index)=><div key={index}><span>{line.description} × {line.quantity}</span><strong>{quote.currency} {Number(line.line_total).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</strong></div>)}</div>
                    <div className="quotation-totals"><span>Subtotal {quote.currency} {Number(quote.subtotal).toLocaleString(undefined,{minimumFractionDigits:2})}</span><span>Tax {quote.currency} {Number(quote.tax_total).toLocaleString(undefined,{minimumFractionDigits:2})}</span><strong>Total {quote.currency} {Number(quote.total).toLocaleString(undefined,{minimumFractionDigits:2})}</strong></div>
                    {quote.notes && <p>{quote.notes}</p>}
                    {quote.response_note && <p className="directory-meta">Response: {quote.response_note}</p>}
                    {quote.status==="sent" && quote.issuer_business_id!==session.business.id && <div className="invitation-actions"><button type="button" className="network-primary-button" onClick={()=>decideQuotation(quote.id,"accepted")}>Accept quotation</button><button type="button" className="network-secondary-button" onClick={()=>decideQuotation(quote.id,"declined")}>Decline</button></div>}
                  </article>)}
                  {quotations.length===0 && <p className="network-empty">No quotations have been shared in this Deal Room yet.</p>}
                  <form className="quotation-form" onSubmit={sendQuotation}>
                    <div className="network-subheading"><h3>Create and share a quotation</h3><span>Visible to both businesses</span></div>
                    <div className="quotation-form-grid">
                      <label>Quotation title<input required maxLength={180} value={quoteTitle} onChange={e=>setQuoteTitle(e.target.value)} placeholder="e.g. Supply of products"/></label>
                      <label>Currency<select value={quoteCurrency} onChange={e=>setQuoteCurrency(e.target.value)}><option value="ZAR">ZAR · South African rand</option><option value="USD">USD · US dollar</option><option value="EUR">EUR · Euro</option><option value="GBP">GBP · Pound sterling</option><option value="KES">KES · Kenyan shilling</option><option value="NGN">NGN · Nigerian naira</option></select></label>
                      <label>Valid until<input type="date" value={quoteValidUntil} onChange={e=>setQuoteValidUntil(e.target.value)}/></label>
                    </div>
                    <div className="quotation-line-editor">{quoteLines.map((line,index)=><div className="quotation-line-row" key={index}>
                      <input aria-label="Item description" required maxLength={240} placeholder="Item or service" value={line.description} onChange={e=>setQuoteLines(current=>current.map((item,i)=>i===index?{...item,description:e.target.value}:item))}/>
                      <input aria-label="Quantity" required type="number" min="0.001" step="0.001" placeholder="Qty" value={line.quantity} onChange={e=>setQuoteLines(current=>current.map((item,i)=>i===index?{...item,quantity:e.target.value}:item))}/>
                      <input aria-label="Unit price" required type="number" min="0" step="0.01" placeholder="Unit price" value={line.unit_price} onChange={e=>setQuoteLines(current=>current.map((item,i)=>i===index?{...item,unit_price:e.target.value}:item))}/>
                      <input aria-label="Tax rate percent" required type="number" min="0" max="100" step="0.01" placeholder="Tax %" value={line.tax_rate} onChange={e=>setQuoteLines(current=>current.map((item,i)=>i===index?{...item,tax_rate:e.target.value}:item))}/>
                      {quoteLines.length>1 && <button type="button" className="network-secondary-button" onClick={()=>setQuoteLines(current=>current.filter((_,i)=>i!==index))}>Remove</button>}
                    </div>)}</div>
                    <button type="button" className="network-secondary-button" onClick={()=>setQuoteLines(current=>[...current,{description:"",quantity:"1",unit_price:"",tax_rate:"15"}])}>+ Add line item</button>
                    <label className="quotation-notes">Notes<textarea rows={2} maxLength={3000} value={quoteNotes} onChange={e=>setQuoteNotes(e.target.value)} placeholder="Payment terms, delivery details or conditions…"/></label>
                    <button className="auth-submit quotation-submit" type="submit">Share quotation in Deal Room <ArrowUpRight size={15}/></button>
                    <p className="quotation-disclaimer">A quotation response records the business's response in BusinessBrain. It is not a signed contract or legal acceptance of a binding agreement.</p>
                  </form>
                </div>

              </div>}
            </>}
          </div>
        </div>
      </section>
      <section className="stats-grid" aria-label="Workspace summary"><div className="stat-card"><span className="stat-icon">{session.business.profile_image_data_url ? <img src={session.business.profile_image_data_url} alt="Business profile"/> : <Building2 size={18}/>}</span><span className="stat-label">Business profile</span><strong>Created</strong><small>{session.business.country} · {session.business.industry}</small></div><div className="stat-card"><span className="stat-icon"><Users size={18}/></span><span className="stat-label">Your role</span><strong>Owner</strong><small>Workspace administrator</small></div><div className="stat-card"><span className="stat-icon"><CreditCard size={18}/></span><span className="stat-label">Financial overview</span><strong>Not connected</strong><small>Add records as you get started</small></div><div className="stat-card"><span className="stat-icon"><Activity size={18}/></span><span className="stat-label">System status</span><strong>{apiStatus === "online" ? "Connected" : "Offline"}</strong><small>Backend health check</small></div></section>
      <section className="modules-section"><div className="section-heading"><div><div className="eyebrow">THE BUSINESS OPERATING SYSTEM</div><h2>Your business, connected.</h2><p>One workspace for the work that moves your business forward.</p></div><span className="module-count">06 CORE MODULES</span></div><div className="module-grid">{modules.map(({icon: Icon,title,detail,tag}) => <article className="module-card" key={title}><div className="module-icon"><Icon size={20}/></div><span className="module-tag">{tag}</span><h3>{title}</h3><p>{detail}</p><span className="module-footer">Part of BusinessBrain <ArrowUpRight size={14}/></span></article>)}</div></section>
      <footer className="footer"><span>BusinessBrain © 2026</span><span>BUILD THE INTELLIGENCE THAT RUNS BUSINESSES.</span></footer>
    </main>
  </div>;
}
