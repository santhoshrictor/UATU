import React, { useState, useEffect } from 'react';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Key,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  X,
  Bug,
  Calendar,
  QrCode,
  Smartphone,
  Copy,
  Check,
  Clock,
} from 'lucide-react';
import { Button } from './ui/button';

export interface FortressAuditModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetDate?: string;
  backendUrl?: string;
  onAuthorized?: (sessionToken: string, username: string, trustScore: number, targetDate: string) => void;
}

type FortressStep = 'AUTHENTICATE' | 'PAIR_QR' | 'RESULT';

interface TrustBreakdownItem {
  factor: string;
  status: 'PASS' | 'FAIL' | 'WARN' | 'BREACH';
  delta: number;
  detail: string;
}

interface TotpSetupData {
  username: string;
  secret: string;
  provisioning_uri: string;
  qr_code_data_url: string;
  issuer: string;
  configured: boolean;
  current_demo_code?: string;
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

  const [step, setStep] = useState<FortressStep>('AUTHENTICATE');
  const [username, setUsername] = useState<string>('superadmin@uatu.security');
  const [password, setPassword] = useState<string>('SuperAdmin@2026!');
  const [totpCode, setOtpCode] = useState<string>('');
  const [selectedDate, setSelectedDate] = useState<string>(targetDate || getTodayDateStr());
  const [exportFormat, setExportFormat] = useState<'csv' | 'jsonl'>('csv');
  const [simulateHacker, setSimulateHacker] = useState<boolean>(false);
  const [authorizedToken, setAuthorizedToken] = useState<string>('');

  // TOTP QR Pairing State
  const [qrData, setQrData] = useState<TotpSetupData | null>(null);
  const [isLoadingQr, setIsLoadingQr] = useState<boolean>(false);
  const [copiedSecret, setCopiedSecret] = useState<boolean>(false);
  const [demoCodeHint, setDemoCodeHint] = useState<string>('');

  // 30-Second Countdown timer for TOTP indicator
  const [secondsRemaining, setSecondsRemaining] = useState<number>(30);

  // Status & Telemetry
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [trustScore, setTrustScore] = useState<number | null>(null);
  const [trustBreakdown, setTrustBreakdown] = useState<TrustBreakdownItem[]>([]);
  const [isSuccess, setIsSuccess] = useState<boolean>(false);

  // Synchronize 30-second rolling code timer
  useEffect(() => {
    const updateCountdown = () => {
      const sec = Math.floor(Date.now() / 1000) % 30;
      setSecondsRemaining(30 - sec);
    };
    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, []);

  // Fetch QR Code Setup when entering PAIR_QR step
  const loadQrSetup = async (forceReset: boolean = false) => {
    setIsLoadingQr(true);
    setErrorMsg(null);
    try {
      const endpoint = forceReset ? `${backendUrl}/api/totp/reset` : `${backendUrl}/api/totp/setup`;
      const res = await fetch(`${endpoint}?username=${encodeURIComponent(username)}`, {
        method: forceReset ? 'POST' : 'GET',
      });
      if (!res.ok) {
        throw new Error('Failed to retrieve TOTP provisioning setup.');
      }
      const data: TotpSetupData = await res.json();
      setQrData(data);
      if (data.current_demo_code) {
        setDemoCodeHint(data.current_demo_code);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Could not load Google Authenticator QR Code.');
    } finally {
      setIsLoadingQr(false);
    }
  };

  const handleOpenPairing = () => {
    setStep('PAIR_QR');
    loadQrSetup(false);
  };

  const handleCopySecret = () => {
    if (qrData?.secret) {
      navigator.clipboard.writeText(qrData.secret);
      setCopiedSecret(true);
      setTimeout(() => setCopiedSecret(false), 2500);
    }
  };

  // Submit TOTP and Zero-Trust Verification
  const handleVerifyTOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';
      const endpoint = `${backendUrl}/api/totp/verify?simulate_hacker=${simulateHacker}`;

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          password,
          totp_code: totpCode.trim(),
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
      const finalScore = data.trust_score ?? 100;
      const finalToken = data.session_token;
      setAuthorizedToken(finalToken);
      setTrustScore(finalScore);
      setTrustBreakdown(data.breakdown || []);
      setIsSuccess(true);
      setStep('RESULT');
    } catch (err: any) {
      setErrorMsg(err.message || 'TOTP verification failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setStep('AUTHENTICATE');
    setOtpCode('');
    setErrorMsg(null);
    setTrustScore(null);
    setTrustBreakdown([]);
    setIsSuccess(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700/90 rounded-2xl shadow-2xl max-w-xl w-full overflow-hidden text-slate-100 flex flex-col animate-in fade-in zoom-in-95 duration-150">
        {/* Header with Fortress & Google Authenticator Branding */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/80">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold tracking-wider uppercase font-mono text-slate-100">
                  Fortress Zero-Trust Gateway
                </h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  TOTP 30s
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                Google Authenticator RFC 6238 &amp; Device Binding Verification
              </p>
            </div>
          </div>
          <Button
            onClick={onClose}
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-slate-400 hover:text-white"
            title="Cancel & Close"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto max-h-[80vh]">
          {/* ===================================================================
              VIEW 1: STANDARD AUTHENTICATION VIEW (PASSWORD + 6-DIGIT TOTP)
              =================================================================== */}
          {step === 'AUTHENTICATE' && (
            <form onSubmit={handleVerifyTOTP} className="space-y-4">
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-semibold text-slate-200 flex items-center gap-1.5">
                    <Key className="w-4 h-4 text-amber-400" />
                    <span>SuperAdmin Credentials</span>
                  </span>
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
                    SUPERADMIN
                  </span>
                </div>

                <div className="space-y-2 pt-1">
                  <div>
                    <label className="block text-[11px] font-mono text-slate-400 mb-1">
                      Username / Email:
                    </label>
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono text-slate-400 mb-1">
                      Master Password:
                    </label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
                    />
                  </div>
                </div>
              </div>

              {/* Google Authenticator 6-Digit Rolling Code */}
              <div className="p-4 rounded-xl bg-slate-950 border border-amber-500/30 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Smartphone className="w-4 h-4 text-cyan-400" />
                    <label className="text-xs font-mono font-semibold text-slate-200">
                      Google Authenticator Code
                    </label>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400">
                    <Clock className="w-3.5 h-3.5 text-amber-400 animate-spin" />
                    <span>Refresh: <strong className="text-amber-300 font-mono">{secondsRemaining}s</strong></span>
                  </div>
                </div>

                <div className="relative">
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    placeholder="000 000"
                    value={totpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                    required
                    autoFocus
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 text-center text-xl tracking-[0.4em] font-mono text-amber-400 font-bold focus:outline-none focus:border-amber-400 shadow-inner"
                  />
                </div>

                {/* QR Pairing Option Link */}
                <div className="flex items-center justify-between pt-1 text-[11px] font-mono">
                  <button
                    type="button"
                    onClick={handleOpenPairing}
                    className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1.5 hover:underline"
                  >
                    <QrCode className="w-3.5 h-3.5" />
                    <span>First time? Pair Authenticator App (QR Code)</span>
                  </button>

                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const res = await fetch(`${backendUrl}/api/totp/setup?username=${encodeURIComponent(username)}`);
                        const d = await res.json();
                        if (d.current_demo_code) {
                          setOtpCode(d.current_demo_code);
                        }
                      } catch {}
                    }}
                    className="text-slate-500 hover:text-slate-300 text-[10px]"
                    title="Fill current demo rolling code"
                  >
                    Demo Auto-Fill
                  </button>
                </div>
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
                      Artificially triggers Zero-Trust device &amp; subnet breach
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
                <Button
                  type="button"
                  onClick={onClose}
                  variant="secondary"
                  className="px-4 py-2.5 h-10 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs border border-slate-700"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isLoading || totpCode.length !== 6}
                  className="flex-1 flex items-center justify-center gap-2 h-10 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold text-xs uppercase tracking-wider font-mono shadow-lg shadow-amber-950/40"
                >
                  {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                  <span>{isLoading ? 'Verifying Zero-Trust...' : 'Verify TOTP & Unlock Dashboard'}</span>
                </Button>
              </div>
            </form>
          )}

          {/* ===================================================================
              VIEW 2: FIRST-TIME PAIRING VIEW (GOOGLE AUTHENTICATOR QR CODE)
              =================================================================== */}
          {step === 'PAIR_QR' && (
            <div className="space-y-4">
              <div className="text-center space-y-1">
                <h3 className="text-sm font-bold font-mono text-slate-100 uppercase tracking-wide flex items-center justify-center gap-2">
                  <QrCode className="w-4 h-4 text-cyan-400" />
                  <span>Pair Authenticator Device</span>
                </h3>
                <p className="text-xs text-slate-400 font-mono">
                  Scan this QR code with Google Authenticator, Authy, or Microsoft Authenticator.
                </p>
              </div>

              {isLoadingQr ? (
                <div className="p-12 flex flex-col items-center justify-center gap-3 bg-slate-950 rounded-xl border border-slate-800">
                  <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
                  <span className="text-xs font-mono text-slate-400">Generating cryptographic QR code...</span>
                </div>
              ) : qrData ? (
                <div className="space-y-4">
                  {/* High-Contrast QR Code Viewport */}
                  <div className="p-4 bg-white rounded-xl flex items-center justify-center max-w-[240px] mx-auto shadow-2xl">
                    <img
                      src={qrData.qr_code_data_url}
                      alt="Google Authenticator QR Code"
                      className="w-full h-auto object-contain rounded"
                    />
                  </div>

                  {/* Manual Base32 Key */}
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                      <span>Manual Entry Secret Key:</span>
                      <button
                        type="button"
                        onClick={handleCopySecret}
                        className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 text-[10px]"
                      >
                        {copiedSecret ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                        <span>{copiedSecret ? 'Copied!' : 'Copy Key'}</span>
                      </button>
                    </div>
                    <div className="bg-slate-900 border border-slate-800 rounded p-2 text-center font-mono text-amber-300 text-xs tracking-wider select-all break-all">
                      {qrData.secret}
                    </div>
                  </div>

                  {/* Immediate 6-Digit Code Test */}
                  <div className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 space-y-2">
                    <label className="block text-xs font-mono text-slate-300">
                      Enter 6-digit rolling code displayed on your app:
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        maxLength={6}
                        placeholder="000000"
                        value={totpCode}
                        onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                        className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-center text-lg font-mono tracking-widest text-amber-400 focus:outline-none focus:border-cyan-400 font-bold"
                      />
                      {demoCodeHint && (
                        <button
                          type="button"
                          onClick={() => setOtpCode(demoCodeHint)}
                          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono rounded-lg border border-slate-700 whitespace-nowrap"
                        >
                          Use Demo Code ({demoCodeHint})
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ) : null}

              <div className="flex items-center gap-3 pt-2">
                <Button
                  type="button"
                  onClick={() => setStep('AUTHENTICATE')}
                  variant="secondary"
                  className="flex-1 px-4 py-2.5 h-10 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs border border-slate-700"
                >
                  ← Back to Authenticator Sign-in
                </Button>
                <Button
                  type="button"
                  onClick={async (e) => {
                    await handleVerifyTOTP(e);
                  }}
                  disabled={totpCode.length !== 6 || isLoading}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 h-10 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-xs uppercase tracking-wider font-mono"
                >
                  {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                  <span>Verify Code &amp; Launch</span>
                </Button>
              </div>
            </div>
          )}

          {/* ===================================================================
              VIEW 3: VERIFICATION RESULT & TRUST SCORE BREAKDOWN
              =================================================================== */}
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
                    ? 'Google Authenticator TOTP & hardware context verified. Secure SuperAdmin session generated for Audit Logs Dashboard.'
                    : 'Untrusted device / proxy or invalid TOTP token. Rogue session quarantined; incident recorded in immutable black box audit logs.'}
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
                    <Button
                      type="button"
                      onClick={() => {
                        onAuthorized(authorizedToken, username, trustScore ?? 95, selectedDate);
                        onClose();
                      }}
                      className="flex-1 px-5 py-2.5 h-10 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold font-mono text-xs uppercase tracking-wider shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-2"
                    >
                      <ShieldCheck className="w-4 h-4" />
                      Open Audit Logs Dashboard →
                    </Button>
                    <Button
                      type="button"
                      onClick={onClose}
                      variant="secondary"
                      className="px-4 py-2.5 h-10 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs border border-slate-700"
                    >
                      Close
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      type="button"
                      onClick={handleReset}
                      variant="secondary"
                      className="flex-1 px-4 py-2.5 h-10 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-mono text-xs border border-slate-700"
                    >
                      Run Another Verification
                    </Button>
                    <Button
                      type="button"
                      onClick={onClose}
                      className="px-5 py-2.5 h-10 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold font-mono text-xs"
                    >
                      Close Gateway
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-[11px] font-mono text-slate-500">
          <span>Security Protocol: NIST 800-207 Zero Trust + RFC 6238 TOTP</span>
          <span>Target Gate: &gt;= 80 pts</span>
        </div>
      </div>
    </div>
  );
};

export default FortressAuditModal;
