"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Search,
  Upload,
  Globe,
  ArrowRight,
  Sparkles,
  ClipboardList,
  Scale,
  Activity,
  ChevronRight,
  X,
  Send,
  BookOpen,
  Loader2,
  Trash2,
  Eye,
  Sun,
  Moon,
} from "lucide-react";
import type {
  PolicyInfo,
  QueryResponse,
  ChatMessage,
  ReadingLevel,
  EligibilityResponse,
  ExclusionsResponse,
  ExclusionItem,
} from "@/lib/types";
import {
  uploadPolicy,
  listPolicies,
  deletePolicy,
  askQuestion,
  checkEligibility,
  findExclusions,
} from "@/lib/api";

// ─── Confidence Badge ─────────────────────────────────────────
function ConfidenceBadge({ level, score }: { level: string; score: number }) {
  const config = {
    high: { label: "High Confidence", icon: "🟢", className: "trust-badge high" },
    medium: { label: "Needs Review", icon: "🟡", className: "trust-badge medium" },
    low: { label: "Low Confidence", icon: "🔴", className: "trust-badge low" },
  }[level] || { label: "Unknown", icon: "⚪", className: "trust-badge" };

  return (
    <span className={config.className}>
      {config.icon} {config.label} ({Math.round(score * 100)}%)
    </span>
  );
}

// ─── Source Card ──────────────────────────────────────────────
function SourceCard({
  source,
}: {
  source: { section_title: string; page_number: number; text: string };
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="source-card" onClick={() => setExpanded(!expanded)}>
      <div className="flex items-center justify-between">
        <span className="font-medium text-blue-300">
          📄 {source.section_title || "Policy Clause"} — Page {source.page_number}
        </span>
        <ChevronRight
          className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? "rotate-90" : ""}`}
        />
      </div>
      {expanded && (
        <motion.p
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="mt-3 text-sm text-gray-300 leading-relaxed border-t border-blue-900/30 pt-3"
        >
          &ldquo;{source.text}&rdquo;
        </motion.p>
      )}
    </div>
  );
}

// ─── Language Selector ───────────────────────────────────────
function LanguageSelector({
  language,
  onChange,
}: {
  language: string;
  onChange: (l: string) => void;
}) {
  const languages = [
    { code: "en", label: "English" },
    { code: "hi", label: "हिंदी" },
    { code: "es", label: "Español" },
    { code: "fr", label: "Français" },
    { code: "ar", label: "العربية" },
    { code: "zh", label: "中文" },
  ];
  return (
    <div className="flex items-center gap-2">
      <Globe className="w-4 h-4 text-gray-400" />
      <select
        value={language}
        onChange={(e) => onChange(e.target.value)}
        className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-1.5 text-sm text-gray-900 outline-none focus:border-blue-500 cursor-pointer"
      >
        {languages.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label}
          </option>
        ))}
      </select>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN PAGE COMPONENT
// ═══════════════════════════════════════════════════════════════
export default function HomePage() {
  // State
  const [policies, setPolicies] = useState<PolicyInfo[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<string>("");
  const [activeView, setActiveView] = useState<string>("dashboard");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [isAsking, setIsAsking] = useState(false);

  const [language, setLanguage] = useState("en");
  const [eligibilityResult, setEligibilityResult] = useState<EligibilityResponse | null>(null);
  const [exclusionsResult, setExclusionsResult] = useState<ExclusionsResponse | null>(null);
  const [loadingFeature, setLoadingFeature] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  // Sync theme with document class list
  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") as "light" | "dark" | null;
    const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initialTheme = savedTheme || (systemPrefersDark ? "dark" : "light");
    setTheme(initialTheme);
    if (initialTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    localStorage.setItem("theme", nextTheme);
    if (nextTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  // Load policies on mount
  useEffect(() => {
    loadPolicies();
  }, []);

  const loadPolicies = async () => {
    try {
      const data = await listPolicies();
      setPolicies(data.policies);
      if (data.policies.length > 0 && !selectedPolicy) {
        setSelectedPolicy(data.policies[0].policy_id);
      }
    } catch {
      // Backend might not be running yet
    }
  };

  // ─── Upload Handler ──────────────────────────────────────
  const handleUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please upload a PDF file");
      return;
    }
    setUploading(true);
    setUploadProgress("Parsing PDF...");
    try {
      setUploadProgress("Analyzing document structure...");
      const result = await uploadPolicy(file);
      setUploadProgress("Indexing complete!");
      setTimeout(() => {
        setUploading(false);
        setUploadProgress("");
        setSelectedPolicy(result.policy_id);
        loadPolicies();
        setActiveView("dashboard");
      }, 1000);
    } catch (err: unknown) {
      setUploading(false);
      setUploadProgress("");
      const message = err instanceof Error ? err.message : "Upload failed";
      alert(message);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  }, []);

  // ─── Chat Handler ────────────────────────────────────────
  const handleAsk = async () => {
    if (!inputText.trim() || !selectedPolicy || isAsking) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: inputText,
      timestamp: new Date(),
    };

    const loadingMsg: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "",
      timestamp: new Date(),
      isLoading: true,
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInputText("");
    setIsAsking(true);

    try {
      const response = await askQuestion(
        userMsg.content,
        selectedPolicy,
        "standard",
        language
      );
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, content: response.answer, response, isLoading: false }
            : m
        )
      );
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Something went wrong";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, content: `Error: ${errMsg}`, isLoading: false }
            : m
        )
      );
    }
    setIsAsking(false);
  };

  // ─── Feature Handlers ────────────────────────────────────
  const handleEligibility = async () => {
    const condition = prompt(
      "Enter the condition or situation to check eligibility for:"
    );
    if (!condition || !selectedPolicy) return;
    setLoadingFeature("eligibility");
    setActiveView("eligibility");
    try {
      const result = await checkEligibility(selectedPolicy, condition, "", language);
      setEligibilityResult(result);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Check failed";
      alert(errMsg);
    }
    setLoadingFeature("");
  };

  const handleExclusions = async () => {
    if (!selectedPolicy) return;
    setLoadingFeature("exclusions");
    setActiveView("exclusions");
    try {
      const result = await findExclusions(selectedPolicy);
      setExclusionsResult(result);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Search failed";
      alert(errMsg);
    }
    setLoadingFeature("");
  };

  const handleDelete = async (policyId: string) => {
    if (!confirm("Delete this policy?")) return;
    try {
      await deletePolicy(policyId);
      if (selectedPolicy === policyId) setSelectedPolicy("");
      loadPolicies();
    } catch {
      alert("Failed to delete");
    }
  };

  // ─── Action Cards Data ───────────────────────────────────
  const actionCards = [
    {
      icon: <FileText className="w-6 h-6" />,
      title: "Explain Policy",
      desc: "Get a clear summary in plain language",
      color: "from-blue-500 to-cyan-500",
      action: () => {
        setActiveView("chat");
        setInputText("Summarize this insurance policy in simple language. What does it cover?");
      },
    },
    {
      icon: <CheckCircle2 className="w-6 h-6" />,
      title: "Check Eligibility",
      desc: "Verify coverage for your condition",
      color: "from-emerald-500 to-teal-500",
      action: handleEligibility,
    },
    {
      icon: <AlertTriangle className="w-6 h-6" />,
      title: "Find Exclusions",
      desc: "Discover hidden traps and limitations",
      color: "from-amber-500 to-orange-500",
      action: handleExclusions,
    },
    {
      icon: <ClipboardList className="w-6 h-6" />,
      title: "Claim Requirements",
      desc: "Know exactly what documents you need",
      color: "from-purple-500 to-pink-500",
      action: () => {
        setActiveView("chat");
        setInputText("What documents and steps are required to file a claim under this policy?");
      },
    },
    {
      icon: <Scale className="w-6 h-6" />,
      title: "Compare Policies",
      desc: "Side-by-side policy comparison",
      color: "from-indigo-500 to-blue-500",
      action: () => setActiveView("compare"),
    },
    {
      icon: <Search className="w-6 h-6" />,
      title: "Ask Anything",
      desc: "Free-form policy Q&A with citations",
      color: "from-rose-500 to-red-500",
      action: () => setActiveView("chat"),
    },
  ];

  const currentPolicy = policies.find((p) => p.policy_id === selectedPolicy);

  // ═══════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════
  return (
    <div className="min-h-screen" style={{ background: "var(--gradient-hero)" }}>
      {/* ─── Top Navbar ─────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-[var(--bg-primary)]/80 border-b border-[var(--border-color)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div
              className="flex items-center gap-3 cursor-pointer"
              onClick={() => setActiveView("dashboard")}
            >
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                  PolicyLens AI
                </h1>
                <p className="text-[10px] text-gray-500 -mt-1">Insurance Intelligence</p>
              </div>
            </div>

            <div className="flex items-center gap-4">

              <LanguageSelector language={language} onChange={setLanguage} />
              <button
                onClick={toggleTheme}
                className="p-2 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)] text-gray-500 hover:text-gray-900 transition-all cursor-pointer flex items-center justify-center"
                title={theme === "light" ? "Switch to Dark Mode" : "Switch to Light Mode"}
              >
                {theme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
              </button>
              <button
                onClick={() => setActiveView("upload")}
                className="btn-primary text-sm !py-2 !px-4"
              >
                <Upload className="w-4 h-4" /> Upload PDF
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* ─── Policy Selector Bar ─────────────────────────── */}
        {policies.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8 flex flex-wrap items-center gap-3"
          >
            <span className="text-sm text-gray-400">Active Policy:</span>
            {policies.map((p) => (
              <button
                key={p.policy_id}
                onClick={() => setSelectedPolicy(p.policy_id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  selectedPolicy === p.policy_id
                    ? "bg-blue-600/20 text-blue-300 border border-blue-500/30"
                    : "bg-[var(--bg-card)] text-gray-400 border border-transparent hover:border-gray-700"
                }`}
              >
                <FileText className="w-4 h-4" />
                {p.filename}
                <span className="text-xs text-gray-500">({p.page_count}p)</span>
                <Trash2
                  className="w-3.5 h-3.5 text-gray-600 hover:text-red-400 transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(p.policy_id);
                  }}
                />
              </button>
            ))}
          </motion.div>
        )}

        <AnimatePresence mode="wait">
          {/* ═══ DASHBOARD VIEW ═══ */}
          {activeView === "dashboard" && (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
            >
              {/* Hero */}
              {policies.length === 0 ? (
                <div className="text-center py-20">
                  <motion.div
                    initial={{ scale: 0.8 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 0.1, type: "spring" }}
                  >
                    <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mb-6">
                      <Sparkles className="w-10 h-10 text-white" />
                    </div>
                  </motion.div>
                  <h2 className="text-3xl font-bold mb-3">
                    Welcome to{" "}
                    <span className="bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                      PolicyLens AI
                    </span>
                  </h2>
                  <p className="text-gray-400 text-lg mb-8 max-w-xl mx-auto">
                    Upload your insurance policy PDF and get instant, trustworthy
                    intelligence — powered by AI with clause-grounded accuracy.
                  </p>
                  <button
                    onClick={() => setActiveView("upload")}
                    className="btn-primary text-base"
                  >
                    <Upload className="w-5 h-5" /> Upload Your First Policy
                  </button>
                </div>
              ) : (
                <>
                  {/* Policy Summary Card */}
                  {currentPolicy && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="glass-card p-6 mb-8"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-3 mb-2">
                            <div className="w-10 h-10 rounded-xl bg-blue-600/20 flex items-center justify-center">
                              <FileText className="w-5 h-5 text-blue-400" />
                            </div>
                            <div>
                              <h3 className="font-bold text-lg">{currentPolicy.filename}</h3>
                              <p className="text-sm text-gray-400">
                                {currentPolicy.page_count} pages · {currentPolicy.chunk_count}{" "}
                                analyzed sections
                              </p>
                            </div>
                          </div>
                          {currentPolicy.summary && (
                            <p className="text-gray-300 mt-3 pl-[52px]">
                              {currentPolicy.summary}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Activity className="w-4 h-4 text-green-400" />
                          <span className="text-xs text-green-400 font-medium">Indexed</span>
                        </div>
                      </div>
                    </motion.div>
                  )}

                  {/* Action Cards Grid */}
                  <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-blue-400" />
                    What would you like to know?
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
                    {actionCards.map((card, i) => (
                      <motion.div
                        key={card.title}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                        onClick={card.action}
                        className="glass-card action-card group"
                      >
                        <div
                          className={`w-12 h-12 rounded-xl bg-gradient-to-br ${card.color} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}
                        >
                          {card.icon}
                        </div>
                        <h4 className="font-bold text-base mb-1">{card.title}</h4>
                        <p className="text-sm text-gray-400">{card.desc}</p>
                        <ArrowRight className="w-4 h-4 text-gray-600 absolute top-6 right-6 group-hover:text-white group-hover:translate-x-1 transition-all" />
                      </motion.div>
                    ))}
                  </div>
                </>
              )}
            </motion.div>
          )}

          {/* ═══ UPLOAD VIEW ═══ */}
          {activeView === "upload" && (
            <motion.div
              key="upload"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="max-w-2xl mx-auto"
            >
              <button
                onClick={() => setActiveView("dashboard")}
                className="text-gray-400 hover:text-white mb-6 flex items-center gap-1 text-sm"
              >
                ← Back to Dashboard
              </button>
              <h2 className="text-2xl font-bold mb-2">Upload Insurance Policy</h2>
              <p className="text-gray-400 mb-8">
                Upload a PDF and our AI will analyze every clause, coverage detail,
                and exclusion in seconds.
              </p>

              <div
                className={`upload-zone ${dragActive ? "active" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
                onClick={() => document.getElementById("file-input")?.click()}
              >
                {uploading ? (
                  <div className="space-y-4">
                    <Loader2 className="w-12 h-12 text-blue-400 mx-auto animate-spin" />
                    <p className="text-blue-300 font-medium">{uploadProgress}</p>
                    <div className="w-64 h-2 bg-gray-800 rounded-full mx-auto overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"
                        initial={{ width: "0%" }}
                        animate={{ width: "85%" }}
                        transition={{ duration: 8, ease: "easeOut" }}
                      />
                    </div>
                  </div>
                ) : (
                  <>
                    <Upload className="w-12 h-12 text-blue-400 mx-auto mb-4" />
                    <p className="text-lg font-medium mb-2">
                      Drop your insurance PDF here
                    </p>
                    <p className="text-gray-500 text-sm">
                      or click to browse · PDF files up to 20MB
                    </p>
                  </>
                )}
              </div>
              <input
                id="file-input"
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleUpload(file);
                }}
              />
            </motion.div>
          )}

          {/* ═══ CHAT VIEW ═══ */}
          {activeView === "chat" && (
            <motion.div
              key="chat"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="max-w-4xl mx-auto"
            >
              <button
                onClick={() => setActiveView("dashboard")}
                className="text-gray-400 hover:text-white mb-4 flex items-center gap-1 text-sm"
              >
                ← Back to Dashboard
              </button>

              {/* Messages */}
              <div className="space-y-6 mb-6 min-h-[300px] max-h-[60vh] overflow-y-auto pr-2">
                {messages.length === 0 && (
                  <div className="text-center py-16 text-gray-500">
                    <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>Ask any question about your policy</p>
                    <p className="text-sm mt-1">Every answer is grounded in your actual policy clauses</p>
                  </div>
                )}
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    {msg.role === "user" ? (
                      <div className="chat-bubble-user">{msg.content}</div>
                    ) : (
                      <div className="chat-bubble-ai">
                        {msg.isLoading ? (
                          <div className="flex items-center gap-3">
                            <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                            <span className="text-gray-400">Analyzing policy clauses...</span>
                          </div>
                        ) : (
                          <div>
                            <p className="text-gray-900 leading-relaxed whitespace-pre-wrap">
                              {msg.content}
                            </p>

                            {/* Trust & Source UI */}
                            {msg.response && (
                              <div className="mt-4 space-y-3 pt-4 border-t border-gray-800">
                                <div className="flex flex-wrap items-center gap-3">
                                  <ConfidenceBadge
                                    level={msg.response.confidence.level}
                                    score={msg.response.confidence.overall}
                                  />
                                  {msg.response.verification_status && (
                                    <span className="text-xs bg-purple-900/30 text-purple-300 px-2 py-1 rounded-lg border border-purple-800/30">
                                      ✓ {msg.response.verification_status}
                                    </span>
                                  )}
                                  <span className="text-xs text-gray-500">
                                    {msg.response.latency_ms}ms · Tier: {msg.response.tier}
                                  </span>
                                </div>

                                {/* Ambiguity Warning */}
                                {msg.response.ambiguity?.found && (
                                  <div className="bg-amber-900/15 border border-amber-800/30 rounded-xl p-3">
                                    <div className="flex items-center gap-2 text-amber-300 text-sm font-medium mb-1">
                                      <AlertTriangle className="w-4 h-4" /> Ambiguity
                                      Detected
                                    </div>
                                    {msg.response.ambiguity.details.map((d, i) => (
                                      <p key={i} className="text-xs text-amber-200/70 ml-6">
                                        • {d}
                                      </p>
                                    ))}
                                  </div>
                                )}

                                {/* Source Citations */}
                                {msg.response.sources.length > 0 && (
                                  <div className="space-y-2">
                                    <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">
                                      📎 Evidence Sources
                                    </p>
                                    {msg.response.sources.slice(0, 3).map((src, i) => (
                                      <SourceCard key={i} source={src} />
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>

              {/* Input */}
              <div className="sticky bottom-4 glass-card !rounded-2xl p-3 flex items-center gap-3">
                <input
                  type="text"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAsk()}
                  placeholder="Ask about your policy... (e.g., Is maternity covered?)"
                  className="flex-1 bg-transparent outline-none text-gray-900 placeholder-gray-500 px-3 py-2"
                  disabled={isAsking || !selectedPolicy}
                />
                <button
                  onClick={handleAsk}
                  disabled={isAsking || !selectedPolicy || !inputText.trim()}
                  className="btn-primary !py-2.5 !px-5 disabled:opacity-40"
                >
                  {isAsking ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </button>
              </div>
            </motion.div>
          )}

          {/* ═══ ELIGIBILITY VIEW ═══ */}
          {activeView === "eligibility" && (
            <motion.div
              key="eligibility"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="max-w-3xl mx-auto"
            >
              <button
                onClick={() => setActiveView("dashboard")}
                className="text-gray-400 hover:text-white mb-6 flex items-center gap-1 text-sm"
              >
                ← Back to Dashboard
              </button>
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                <CheckCircle2 className="w-7 h-7 text-emerald-400" /> Eligibility Check
              </h2>

              {loadingFeature === "eligibility" ? (
                <div className="glass-card p-12 text-center">
                  <Loader2 className="w-10 h-10 text-blue-400 mx-auto animate-spin mb-4" />
                  <p className="text-gray-400">Analyzing policy clauses for eligibility...</p>
                </div>
              ) : eligibilityResult ? (
                <div className="space-y-4">
                  <div className="glass-card p-6">
                    <div className="flex items-center gap-3 mb-4">
                      {eligibilityResult.eligible === true && (
                        <div className="w-12 h-12 rounded-xl bg-emerald-900/30 flex items-center justify-center">
                          <CheckCircle2 className="w-7 h-7 text-emerald-400" />
                        </div>
                      )}
                      {eligibilityResult.eligible === false && (
                        <div className="w-12 h-12 rounded-xl bg-red-900/30 flex items-center justify-center">
                          <X className="w-7 h-7 text-red-400" />
                        </div>
                      )}
                      {eligibilityResult.eligible === null && (
                        <div className="w-12 h-12 rounded-xl bg-amber-900/30 flex items-center justify-center">
                          <AlertTriangle className="w-7 h-7 text-amber-400" />
                        </div>
                      )}
                      <div>
                        <h3 className="font-bold text-lg">
                          {eligibilityResult.eligible === true
                            ? "Likely Eligible"
                            : eligibilityResult.eligible === false
                            ? "Likely Not Eligible"
                            : "Cannot Determine"}
                        </h3>
                        <ConfidenceBadge
                          level={eligibilityResult.confidence.level}
                          score={eligibilityResult.confidence.overall}
                        />
                      </div>
                    </div>
                    <p className="text-gray-300 leading-relaxed">
                      {eligibilityResult.explanation}
                    </p>
                    {eligibilityResult.waiting_period && (
                      <p className="mt-3 text-amber-300 text-sm">
                        ⏳ Waiting Period: {eligibilityResult.waiting_period}
                      </p>
                    )}
                  </div>

                  {eligibilityResult.conditions.length > 0 && (
                    <div className="glass-card p-5">
                      <h4 className="font-medium text-sm text-gray-400 mb-3">Conditions</h4>
                      <ul className="space-y-2">
                        {eligibilityResult.conditions.map((c, i) => (
                          <li key={i} className="text-gray-300 text-sm flex items-start gap-2">
                            <span className="text-blue-400 mt-0.5">•</span> {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {eligibilityResult.sources.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">
                        📎 Evidence
                      </p>
                      {eligibilityResult.sources.slice(0, 3).map((src, i) => (
                        <SourceCard key={i} source={src} />
                      ))}
                    </div>
                  )}

                  <p className="text-xs text-gray-500 italic">
                    {eligibilityResult.disclaimer}
                  </p>
                </div>
              ) : null}
            </motion.div>
          )}

          {/* ═══ EXCLUSIONS VIEW ═══ */}
          {activeView === "exclusions" && (
            <motion.div
              key="exclusions"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="max-w-3xl mx-auto"
            >
              <button
                onClick={() => setActiveView("dashboard")}
                className="text-gray-400 hover:text-white mb-6 flex items-center gap-1 text-sm"
              >
                ← Back to Dashboard
              </button>
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                <AlertTriangle className="w-7 h-7 text-amber-400" /> Policy Exclusions &
                Traps
              </h2>

              {loadingFeature === "exclusions" ? (
                <div className="glass-card p-12 text-center">
                  <Loader2 className="w-10 h-10 text-amber-400 mx-auto animate-spin mb-4" />
                  <p className="text-gray-400">Scanning for exclusions and hidden traps...</p>
                </div>
              ) : exclusionsResult ? (
                <div className="space-y-4">
                  <div className="glass-card p-4 flex items-center justify-between">
                    <span className="text-gray-300">
                      Found <strong className="text-amber-400">{exclusionsResult.total}</strong>{" "}
                      exclusions
                    </span>
                    <ConfidenceBadge
                      level={exclusionsResult.confidence.level}
                      score={exclusionsResult.confidence.overall}
                    />
                  </div>
                  {exclusionsResult.exclusions.map((exc: ExclusionItem, i: number) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="glass-card p-5"
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-lg bg-amber-900/30 flex items-center justify-center shrink-0 mt-0.5">
                          <AlertTriangle className="w-4 h-4 text-amber-400" />
                        </div>
                        <div className="flex-1">
                          <h4 className="font-bold text-base mb-1">{exc.title}</h4>
                          <p className="text-gray-300 text-sm leading-relaxed">
                            {exc.description}
                          </p>
                          {exc.risk_note && (
                            <p className="mt-2 text-amber-300/80 text-xs bg-amber-900/10 rounded-lg p-2">
                              ⚠️ {exc.risk_note}
                            </p>
                          )}
                          <div className="mt-2 flex items-center gap-3 text-xs text-gray-500">
                            {exc.section && <span>📑 {exc.section}</span>}
                            {exc.page > 0 && <span>Page {exc.page}</span>}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              ) : null}
            </motion.div>
          )}

          {/* ═══ COMPARE VIEW ═══ */}
          {activeView === "compare" && (
            <motion.div
              key="compare"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="max-w-4xl mx-auto"
            >
              <button
                onClick={() => setActiveView("dashboard")}
                className="text-gray-400 hover:text-white mb-6 flex items-center gap-1 text-sm"
              >
                ← Back to Dashboard
              </button>
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                <Scale className="w-7 h-7 text-indigo-400" /> Compare Policies
              </h2>

              {policies.length < 2 ? (
                <div className="glass-card p-12 text-center">
                  <Scale className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                  <p className="text-gray-400">Upload at least 2 policies to compare.</p>
                  <button
                    onClick={() => setActiveView("upload")}
                    className="btn-primary mt-4"
                  >
                    <Upload className="w-4 h-4" /> Upload Policy
                  </button>
                </div>
              ) : (
                <div className="glass-card p-6 text-center">
                  <p className="text-gray-400">
                    Select policies to compare from the bar above, then use the chat
                    to ask comparison questions.
                  </p>
                  <button
                    onClick={() => {
                      setActiveView("chat");
                      setInputText(
                        "Compare these policies: what are the key differences in coverage, exclusions, and premium?"
                      );
                    }}
                    className="btn-primary mt-4"
                  >
                    <Scale className="w-4 h-4" /> Start Comparison
                  </button>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* ─── Footer ──────────────────────────────────────────── */}
      <footer className="border-t border-[var(--border-color)] mt-16 py-8 text-center">
        <p className="text-gray-600 text-sm">
          PolicyLens AI · Insurance Intelligence Platform · Answers are AI-generated and should be verified with your insurance provider
        </p>
      </footer>
    </div>
  );
}
