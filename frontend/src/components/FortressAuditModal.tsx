import React, { useState } from 'react';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Lock,
  Key,
  Fingerprint,
  Globe,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  X,
  Bug,
  Terminal,
  Calendar,
} from 'lucide-react';

export interface FortressAuditModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetDate?: string;
  backendUrl?: string;
  onAuthorized?: (sessionToken: string, username: string, trustScore: number, targetDate: string) => void;
}

type FortressStep = 'CREDENTIALS' | 'OTP' | 'RESULT';

interface TrustBreakdownItem {
  factor: string;
  status: 'PASS' | 'FAIL' | 'WARN' | 'BREACH';
  delta: number;
  detail: string;
}

export const FortressAuditModal: React.FC<FortressAuditModalProps> = ({
  isOpen,
  onClose,
  targetDate,
  backendUrl = 'http://127.0.0.1:8000',
  onAuthorized,
}) => {
  const getTodayDateStr = () => {
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const [step, setStep] = useState<FortressStep>('CREDENTIALS');
  const [username, setUsername] = useState<string>('superadmin@uatu.security');
  const [password, setPassword] = useState<string>('SuperAdmin@2026!');
  const [, setTicket] = useState<string>('');
  const [sessionId, setSessionId] = useState<string>('');
  const [otpCode, setOtpCode] = useState<string>('');
  const [demoOtpHint, setDemoOtpHint] = useState<string>('');
  const [maskedOtp, setMaskedOtp] = useState<string>('');
  const [boundSubnet, setBoundSubnet] = useState<string>('');
  const [exportFormat, setExportFormat] = useState<'csv' | 'jsonl'>('csv');
  const [selectedDate, setSelectedDate] = useState<string>(targetDate || getTodayDateStr());
  const [simulateHacker, setSimulateHacker] = useState<boolean>(false);
  const [authorizedToken, setAuthorizedToken] = useState<string>('');

  // Status & Telemetry
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [trustScore, setTrustScore] = useState<number | null>(null);
  const [trustBreakdown, setTrustBreakdown] = useState<TrustBreakdownItem[]>([]);
  const [isSuccess, setIsSuccess] = useState<boolean>(false);

  if (!isOpen) return null;

  // Step 1: Verify SuperAdmin Credentials
  const handleVerifyCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`${backendUrl}/api/fortress/verify-credentials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'SuperAdmin authentication failed.');
      }

      setTicket(data.ticket);
      // Automatically request OTP for the verified ticket
      await requestOtp(data.ticket);
      setStep('OTP');
    } catch (err: any) {
      setErrorMsg(err.message || 'Credential verification failed.');
    } finally {
      setIsLoading(false);
    }
  };

  // Helper: Request Contextual Fortress OTP
  const requestOtp = async (authTicket: string) => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';
      const res = await fetch(`${backendUrl}/api/fortress/request-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticket: authTicket,
          timezone: tz,
          user_agent: navigator.userAgent,
          accept_language: navigator.language || 'en-US',
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to dispatch Fortress OTP.');
      }

      setSessionId(data.session_id);
      setDemoOtpHint(data.demo_otp_hint || '');
      setMaskedOtp(data.masked_otp || '');
      setBoundSubnet(data.bound_subnet || '127.0.0.1');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to dispatch Fortress OTP.');
    } finally {
      setIsLoading(false);
    }
  };

  // Step 2: Verify OTP and Authorize / Export
  const handleVerifyAndExport = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';

      if (onAuthorized) {
        // Direct Dashboard Authorization Flow
        const endpoint = `${backendUrl}/api/fortress/verify-otp?simulate_hacker=${simulateHacker}`;
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            otp_code: otpCode.trim(),
            timezone: tz,
            user_agent: navigator.userAgent,
            accept_language: navigator.language || 'en-US',
            simulate_hacker: simulateHacker,
          }),
        });

        if (!res.ok) {
          const errorData = await res.json().catch(() => null);
          const detail = errorData?.error?.message || errorData?.detail || errorData || {};
          const score = typeof detail.trust_score === 'number' ? detail.trust_score : (errorData?.trust_score ?? 35);
          const breakdown = Array.isArray(detail.breakdown) ? detail.breakdown : (errorData?.breakdown ?? []);
          setTrustScore(score);
          setTrustBreakdown(breakdown);
          setIsSuccess(false);
          setStep('RESULT');
          throw new Error(detail.message || errorData?.message || 'Zero-Trust security block triggered.');
        }

        const data = await res.json();
        const finalScore = data.trust_score ?? 95;
        const finalToken = data.session_token;
        setAuthorizedToken(finalToken);
        setTrustScore(finalScore);
        setTrustBreakdown(data.breakdown || []);
        setIsSuccess(true);
        setStep('RESULT');
      } else {
        // Direct Download Flow
        const endpoint = `${backendUrl}/api/fortress/verify-and-export?simulate_hacker=${simulateHacker}`;
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            otp_code: otpCode.trim(),
            date: selectedDate,
            format: exportFormat,
            timezone: tz,
            user_agent: navigator.userAgent,
            accept_language: navigator.language || 'en-US',
            simulate_hacker: simulateHacker,
          }),
        });

        if (!res.ok) {
          const errorData = await res.json().catch(() => null);
          const detail = errorData?.error?.message || errorData?.detail || errorData || {};
          const score = typeof detail.trust_score === 'number' ? detail.trust_score : (errorData?.trust_score ?? 35);
          const breakdown = Array.isArray(detail.breakdown) ? detail.breakdown : (errorData?.breakdown ?? []);
          setTrustScore(score);
          setTrustBreakdown(breakdown);
          setIsSuccess(false);
          setStep('RESULT');
          throw new Error(detail.message || errorData?.message || 'Zero-Trust security block triggered.');
        }

        const scoreHeader = res.headers.get('X-Fortress-Trust-Score');
        const tokenHeader = res.headers.get('X-Fortress-Session-Token');
        const finalScore = scoreHeader ? parseInt(scoreHeader, 10) : 95;
        if (tokenHeader) setAuthorizedToken(tokenHeader);
        setTrustScore(finalScore);
        setTrustBreakdown([
          { factor: 'Network Subnet Consistency', status: 'PASS', delta: 0, detail: `Bound subnet verified (${boundSubnet})` },
          { factor: 'Device Cryptographic Fingerprint', status: 'PASS', delta: 0, detail: 'SHA-256 fingerprint verified' },
          { factor: 'Contextual OTP Authenticity', status: 'PASS', delta: 0, detail: 'Valid cryptographic token consumed' },
        ]);
        setIsSuccess(true);
        setStep('RESULT');

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = exportFormat === 'jsonl' ? `uatu_runtime_audit_${selectedDate}.jsonl` : `audit_log_${selectedDate}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Fortress export failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setStep('CREDENTIALS');
    setOtpCode('');
    setErrorMsg(null);
    setTrustScore(null);
    setTrustBreakdown([]);
    setIsSuccess(false);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700/90 rounded-2xl shadow-2xl max-w-xl w-full overflow-hidden text-slate-100 flex flex-col animate-in fade-in zoom-in-95 duration-150">
        {/* Header with Fortress Branding */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/80">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold tracking-wider uppercase font-mono text-slate-100">
                  Fortress Zero-Trust Security Gateway
                </h2>
                <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  AIR-GAPPED
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Cryptographic OTP & Contextual Device Fingerprint Authentication
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close Fortress Gateway"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Step Indicator */}
        <div className="grid grid-cols-3 border-b border-slate-800 text-center font-mono text-xs">
          <div
            className={`py-2 px-3 flex items-center justify-center gap-1.5 border-r border-slate-800 transition-colors ${
              step === 'CREDENTIALS'
                ? 'bg-amber-500/10 text-amber-400 font-semibold border-b-2 border-b-amber-400'
                : 'text-slate-500 bg-slate-950/40'
            }`}
          >
            <Lock className="w-3.5 h-3.5" />
            <span>1. SuperAdmin</span>
          </div>
          <div
            className={`py-2 px-3 flex items-center justify-center gap-1.5 border-r border-slate-800 transition-colors ${
              step === 'OTP'
                ? 'bg-amber-500/10 text-amber-400 font-semibold border-b-2 border-b-amber-400'
                : 'text-slate-500 bg-slate-950/40'
            }`}
          >
            <Key className="w-3.5 h-3.5" />
            <span>2. Bound OTP</span>
          </div>
          <div
            className={`py-2 px-3 flex items-center justify-center gap-1.5 transition-colors ${
              step === 'RESULT'
                ? isSuccess
                  ? 'bg-emerald-500/10 text-emerald-400 font-semibold border-b-2 border-b-emerald-400'
                  : 'bg-red-500/10 text-red-400 font-semibold border-b-2 border-b-red-400'
                : 'text-slate-500 bg-slate-950/40'
            }`}
          >
            <Fingerprint className="w-3.5 h-3.5" />
            <span>3. Zero-Trust Audit</span>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6">
          {/* STEP 1: SuperAdmin Credentials */}
          {step === 'CREDENTIALS' && (
            <form onSubmit={handleVerifyCredentials} className="space-y-4">
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 flex items-start gap-3">
                <Terminal className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div className="text-xs text-slate-300 font-mono leading-relaxed">
                  Exporting raw audit logs requires authorized SuperAdmin privilege. Enter credentials to request a cryptographic OTP bound to this workstation.
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">
                  SuperAdmin Username / Email
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="superadmin@uatu.security"
                  required
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-amber-400"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">
                  Master Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••••••"
                  required
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-amber-400"
                />
              </div>

              <div className="text-[11px] font-mono text-slate-500 flex items-center justify-between px-1">
                <span>Default: <code className="text-amber-400/80">superadmin@uatu.security</code></span>
                <span>Pass: <code className="text-amber-400/80">SuperAdmin@2026!</code></span>
              </div>

              {errorMsg && (
                <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/40 flex items-center gap-2 text-xs font-mono text-red-300">
                  <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 active:bg-amber-600 disabled:opacity-50 text-slate-950 font-semibold text-xs uppercase tracking-wider font-mono transition-all shadow-lg shadow-amber-950/40 mt-4"
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
                <span>{isLoading ? 'Verifying Credentials...' : 'Authenticate & Request OTP'}</span>
              </button>
            </form>
          )}

          {/* STEP 2: Contextual Fortress OTP Entry */}
          {step === 'OTP' && (
            <form onSubmit={handleVerifyAndExport} className="space-y-4">
              {/* Workstation & Network Binding Info */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 text-[11px] font-mono text-slate-400">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-slate-500">
                    <Globe className="w-3.5 h-3.5 text-cyan-400" /> Bound Subnet:
                  </span>
                  <span className="text-cyan-300 font-semibold">{boundSubnet}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-slate-500">
                    <Fingerprint className="w-3.5 h-3.5 text-emerald-400" /> Device Fingerprint:
                  </span>
                  <span className="text-emerald-300 font-semibold">SHA-256 Validated</span>
                </div>
                {maskedOtp && (
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-slate-500">
                      <Key className="w-3.5 h-3.5 text-amber-400" /> Token Dispatched:
                    </span>
                    <span className="text-amber-300 font-mono font-semibold">{maskedOtp}</span>
                  </div>
                )}
                {demoOtpHint && (
                  <div className="flex items-center justify-between pt-1 border-t border-slate-800/80">
                    <span className="text-amber-400 font-semibold">Demo Workstation OTP:</span>
                    <button
                      type="button"
                      onClick={() => setOtpCode(demoOtpHint)}
                      className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30 text-xs font-bold transition-all"
                      title="Click to auto-fill for demo"
                    >
                      {demoOtpHint} (Auto-Fill)
                    </button>
                  </div>
                )}
              </div>

              {/* OTP Input */}
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">
                  Enter 6-Digit Cryptographic OTP
                </label>
                <input
                  type="text"
                  maxLength={6}
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="e.g. 849201"
                  required
                  autoFocus
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-center text-lg tracking-[0.3em] font-mono text-amber-400 font-bold focus:outline-none focus:border-amber-400"
                />
              </div>

              {/* Target Audit Date & Format Selection */}
              <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-mono text-slate-300 font-semibold flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Target Audit Date for Telemetry:</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => setSelectedDate(getTodayDateStr())}
                    className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300 underline"
                  >
                    Today
                  </button>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <input
                    type="date"
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    max={getTodayDateStr()}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-400"
                  />
                  <select
                    value={exportFormat}
                    onChange={(e) => setExportFormat(e.target.value as 'csv' | 'jsonl')}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-400"
                  >
                    <option value="csv">Default Export: CSV</option>
                    <option value="jsonl">Raw Telemetry: JSONL</option>
                  </select>
                </div>
              </div>

              {/* Hackathon Demo Mode: Simulate Hacker Attack Switch */}
              <div className="p-3 rounded-xl bg-red-950/20 border border-red-500/30 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-lg bg-red-500/10 text-red-400">
                    <Bug className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-xs font-mono font-semibold text-red-300 block">
                      Simulate Phishing / MITM Attack (Demo)
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">
                      Artificially triggers Zero-Trust device & subnet breach
                    </span>
                  </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={simulateHacker}
                    onChange={(e) => setSimulateHacker(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-red-600"></div>
                </label>
              </div>

              {errorMsg && (
                <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/40 flex items-center gap-2 text-xs font-mono text-red-300">
                  <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleReset}
                  className="px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs transition-colors"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={isLoading || otpCode.length !== 6}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 active:bg-amber-600 disabled:opacity-50 text-slate-950 font-semibold text-xs uppercase tracking-wider font-mono transition-all shadow-lg shadow-amber-950/40"
                >
                  {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                  <span>{isLoading ? 'Verifying Zero-Trust...' : (onAuthorized ? 'Verify OTP & Open Dashboard' : 'Verify OTP & Export')}</span>
                </button>
              </div>
            </form>
          )}

          {/* STEP 3: Verification Result & Zero-Trust Trust Score Breakdown */}
          {step === 'RESULT' && (
            <div className="space-y-5">
              {/* Score Display Card */}
              <div
                className={`p-5 rounded-xl border flex flex-col items-center justify-center text-center space-y-2 ${
                  isSuccess
                    ? 'bg-emerald-950/30 border-emerald-500/50 text-emerald-300'
                    : 'bg-red-950/30 border-red-500/50 text-red-300'
                }`}
              >
                {isSuccess ? (
                  <CheckCircle2 className="w-10 h-10 text-emerald-400 animate-in zoom-in-50 duration-200" />
                ) : (
                  <ShieldAlert className="w-10 h-10 text-red-400 animate-in zoom-in-50 duration-200" />
                )}

                <div>
                  <div className="text-2xl font-bold font-mono tracking-tight">
                    TRUST SCORE: {trustScore ?? 0} / 100
                  </div>
                  <div className="text-xs font-mono uppercase tracking-wider font-semibold mt-1">
                    {isSuccess
                      ? 'ZERO-TRUST STATUS: PASSED (THRESHOLD >= 80)'
                      : 'ZERO-TRUST BREACH DETECTED: ACCESS QUARANTINED'}
                  </div>
                </div>

                <p className="text-xs text-slate-400 font-mono max-w-md pt-1">
                  {isSuccess
                    ? (onAuthorized 
                        ? 'Workstation cryptographically verified. Secure SuperAdmin session generated for Audit Logs Dashboard.' 
                        : `Workstation cryptographically verified. ${exportFormat.toUpperCase()} audit log exported successfully.`)
                    : 'Untrusted device / proxy detected. Rogue session quarantined; incident recorded in immutable black box audit logs.'}
                </p>
              </div>

              {/* Factor Breakdown */}
              <div className="space-y-2">
                <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
                  Zero-Trust Contextual Breakdown:
                </div>
                <div className="space-y-1.5">
                  {trustBreakdown.map((item, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 flex items-center justify-between text-xs font-mono"
                    >
                      <div>
                        <span className="text-slate-200 font-semibold">{item.factor}</span>
                        <span className="block text-[11px] text-slate-500">{item.detail}</span>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          item.status === 'PASS'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : 'bg-red-500/20 text-red-400 border border-red-500/30'
                        }`}
                      >
                        {item.delta === 0 ? 'PASS (0 pts)' : `${item.delta} pts`}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Target Audit Date Selection / Confirmation */}
              {isSuccess && (
                <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between gap-3 text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-cyan-400 shrink-0" />
                    <div>
                      <span className="text-slate-400 block text-[10px] uppercase tracking-wider">Target Audit Date:</span>
                      <span className="text-slate-200 font-semibold">{selectedDate}</span>
                    </div>
                  </div>
                  <input
                    type="date"
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    max={getTodayDateStr()}
                    className="bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-400"
                  />
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                {isSuccess && onAuthorized && authorizedToken ? (
                  <>
                    <button
                      type="button"
                      onClick={() => {
                        onAuthorized(authorizedToken, username, trustScore ?? 95, selectedDate);
                        onClose();
                      }}
                      className="flex-1 px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 active:bg-emerald-600 text-slate-950 font-bold font-mono text-xs uppercase tracking-wider transition-all shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-2"
                    >
                      <ShieldCheck className="w-4 h-4" />
                      Open Audit Logs Dashboard →
                    </button>
                    <button
                      type="button"
                      onClick={onClose}
                      className="px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs transition-colors"
                    >
                      Close
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={handleReset}
                      className="flex-1 px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-mono text-xs transition-colors"
                    >
                      Run Another Verification
                    </button>
                    <button
                      type="button"
                      onClick={onClose}
                      className="px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold font-mono text-xs transition-colors"
                    >
                      Close Gateway
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-[11px] font-mono text-slate-500">
          <span>Security Protocol: NIST 800-207 Zero Trust Architecture</span>
          <span>Target Gate: &gt;= 80 pts</span>
        </div>
      </div>
    </div>
  );
};

export default FortressAuditModal;
