import React, { useState, useEffect, useMemo } from 'react';
import {
  ShieldCheck,
  ArrowLeft,
  Download,
  Search,
  Filter,
  Calendar,
  RefreshCw,
  Eye,
  X,
  Copy,
  Check,
  AlertTriangle,
  Bot,
  UserCheck,
  Server,
  Activity,
  Layers,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export interface AuditRecord {
  id: string;
  timestamp_ist: string;
  timestamp_utc: string;
  event_type: string;
  actor: string;
  source: string;
  zone: string;
  details: string;
  voice_command?: string;
  response?: string;
  metadata?: Record<string, any>;
}

export interface AuditLogsPageProps {
  sessionToken: string;
  superadminUser: string;
  trustScore: number;
  onBackToMultiview: () => void;
  backendUrl?: string;
}

export const AuditLogsPage: React.FC<AuditLogsPageProps> = ({
  sessionToken,
  superadminUser,
  trustScore,
  onBackToMultiview,
  backendUrl = 'http://127.0.0.1:8000',
}) => {
  const getTodayDateStr = () => {
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  // Filter States
  const [startDate, setStartDate] = useState<string>(getTodayDateStr());
  const [endDate, setEndDate] = useState<string>(getTodayDateStr());
  const [selectedEventType, setSelectedEventType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [availableTypes, setAvailableTypes] = useState<string[]>([]);

  // Records & Pagination
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 25;

  // Metadata Inspector Modal State
  const [selectedRecordForModal, setSelectedRecordForModal] = useState<AuditRecord | null>(null);
  const [copiedPayload, setCopiedPayload] = useState<boolean>(false);

  // Export State
  const [isExporting, setIsExporting] = useState<boolean>(false);

  // Fetch Audit Records
  const fetchRecords = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      if (selectedEventType && selectedEventType !== 'ALL') params.append('event_type', selectedEventType);
      if (searchQuery.trim()) params.append('search', searchQuery.trim());
      params.append('limit', '250');

      const res = await fetch(`${backendUrl}/api/audit-logs/records?${params.toString()}`, {
        headers: {
          'X-Fortress-Session-Token': sessionToken,
          'Authorization': `Bearer ${sessionToken}`,
        },
      });

      if (!res.ok) {
        if (res.status === 401) {
          throw new Error('SuperAdmin Fortress session expired. Please re-authenticate.');
        }
        throw new Error(`Server returned status HTTP ${res.status}`);
      }

      const data = await res.json();
      setRecords(data.records || []);
      setTotalCount(data.total_count || (data.records ? data.records.length : 0));
      if (Array.isArray(data.available_dates)) setAvailableDates(data.available_dates);
      if (Array.isArray(data.available_event_types)) setAvailableTypes(data.available_event_types);
      setCurrentPage(1);
    } catch (err: any) {
      console.error('Failed to load audit records:', err);
      setErrorMsg(err.message || 'Error loading audit logs.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRecords();
  }, [startDate, endDate, selectedEventType]);

  // Client-Side Pagination of fetched records
  const paginatedRecords = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return records.slice(start, start + pageSize);
  }, [records, currentPage, pageSize]);

  const totalPages = Math.max(1, Math.ceil(records.length / pageSize));

  // Trigger Filtered CSV Export
  const handleExportCSV = async () => {
    setIsExporting(true);
    try {
      // Export either using the date endpoint or building client-side CSV from filtered data
      let csvContent = '';
      const exportUrl = `${backendUrl}/api/audit-logs/export?date=${encodeURIComponent(startDate || getTodayDateStr())}`;
      const res = await fetch(exportUrl);
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit_telemetry_${startDate || getTodayDateStr()}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        // Fallback: Client-side CSV generation
        const headers = ['Timestamp (IST)', 'Event Type', 'Actor', 'Source', 'Zone', 'Details', 'Audit ID'];
        const rows = records.map((r) => [
          `"${r.timestamp_ist}"`,
          `"${r.event_type}"`,
          `"${r.actor}"`,
          `"${r.source}"`,
          `"${r.zone}"`,
          `"${(r.details || '').replace(/"/g, '""')}"`,
          `"${r.id}"`,
        ]);
        csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit_telemetry_${startDate}_to_${endDate}.csv`;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (err) {
      console.error('Export CSV error:', err);
    } finally {
      setIsExporting(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedPayload(true);
    setTimeout(() => setCopiedPayload(false), 2000);
  };

  // Helper for Event Type Badges
  const renderEventBadge = (type: string) => {
    const t = type.toUpperCase();
    if (t.includes('CRITICAL') || t.includes('HAZARD') || t.includes('FALL') || t.includes('BLOCKED')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-red-500/15 text-red-400 border border-red-500/30">
          {type}
        </span>
      );
    }
    if (t.includes('MISMATCH') || t.includes('WARN') || t.includes('TAILGATING')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
          {type}
        </span>
      );
    }
    if (t.includes('AI_VOICE') || t.includes('AGENT')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
          {type}
        </span>
      );
    }
    if (t.includes('FORTRESS') || t.includes('AUTH') || t.includes('AUTHORIZED')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          {type}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-mono text-slate-300 bg-slate-800 border border-slate-700">
        {type}
      </span>
    );
  };

  return (
    <div className="flex-1 flex flex-col bg-[#020617] text-slate-100 font-sans">
      {/* =====================================================================
          TOP NAVIGATION & AUDIT CONTROLS HEADER
          ===================================================================== */}
      <header className="border-b border-[#1e293b] bg-[#020617]/95 backdrop-blur-md sticky top-0 z-40 px-4 sm:px-6 py-3">
        <div className="max-w-[1920px] mx-auto flex flex-wrap items-center justify-between gap-4">
          {/* Left: Brand & Return Navigation */}
          <div className="flex items-center gap-3">
            <button
              onClick={onBackToMultiview}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition-all text-xs font-mono font-semibold group"
              title="Return to 9-Camera Operational Multiview"
            >
              <ArrowLeft className="w-4 h-4 text-emerald-400 group-hover:-translate-x-0.5 transition-transform" />
              <span>Back to Multiview</span>
            </button>

            <div className="h-5 w-[1px] bg-slate-800 hidden sm:block" />

            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h1 className="text-sm font-bold tracking-wider uppercase font-mono text-slate-100 flex items-center gap-2">
                  <span>Fortress Audit Telemetry Dashboard</span>
                  <span className="px-2 py-0.2 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                    ZERO-TRUST VERIFIED
                  </span>
                </h1>
                <p className="text-[11px] text-slate-400 font-mono">
                  Immutable chronological audit log, operator actions & AI voice query trail
                </p>
              </div>
            </div>
          </div>

          {/* Right: SuperAdmin Context & Export Button */}
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono">
              <span className="text-slate-500">SuperAdmin:</span>
              <span className="text-amber-300 font-semibold">{superadminUser}</span>
              <span className="text-slate-600">|</span>
              <span className="text-emerald-400 font-semibold">Trust: {trustScore}/100</span>
            </div>

            <button
              onClick={handleExportCSV}
              disabled={isExporting || records.length === 0}
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-slate-950 font-semibold text-xs uppercase tracking-wider font-mono transition-all shadow-lg shadow-emerald-950/40"
              title="Export displayed audit logs to CSV"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{isExporting ? 'Exporting...' : 'Export CSV'}</span>
            </button>
          </div>
        </div>
      </header>

      {/* =====================================================================
          FILTER & CONTROLS TOOLBAR
          ===================================================================== */}
      <section className="bg-slate-950/70 border-b border-slate-800/80 px-4 sm:px-6 py-3.5">
        <div className="max-w-[1920px] mx-auto flex flex-wrap items-center justify-between gap-4">
          {/* Filter Inputs Group */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Start Date */}
            <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-300">
              <Calendar className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-slate-500 text-[10px]">From:</span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="bg-transparent text-slate-200 text-xs font-mono focus:outline-none"
              />
            </div>

            {/* End Date */}
            <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-300">
              <Calendar className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-slate-500 text-[10px]">To:</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="bg-transparent text-slate-200 text-xs font-mono focus:outline-none"
              />
            </div>

            {/* Event Type Filter */}
            <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-300">
              <Filter className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-slate-500 text-[10px]">Type:</span>
              <select
                value={selectedEventType}
                onChange={(e) => setSelectedEventType(e.target.value)}
                className="bg-transparent text-slate-200 text-xs font-mono focus:outline-none cursor-pointer"
              >
                <option value="ALL" className="bg-slate-900 text-slate-200">All Event Types</option>
                {availableTypes.map((t) => (
                  <option key={t} value={t} className="bg-slate-900 text-slate-200">
                    {t}
                  </option>
                ))}
              </select>
            </div>

            {/* Keyword Search Box */}
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs font-mono w-64 sm:w-80">
              <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <input
                type="text"
                placeholder="Search actor, node, details, ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchRecords()}
                className="bg-transparent text-slate-200 placeholder:text-slate-500 focus:outline-none w-full text-xs font-mono"
              />
              {searchQuery && (
                <button onClick={() => setSearchQuery('')} className="text-slate-400 hover:text-white">
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            <button
              onClick={fetchRecords}
              disabled={isLoading}
              className="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white transition-colors"
              title="Refresh Audit Records"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-emerald-400' : ''}`} />
            </button>
          </div>

          {/* Records Counter */}
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span className="text-slate-500">Total Telemetry:</span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-cyan-300 font-bold">
              {totalCount} Logs
            </span>
          </div>
        </div>

        {/* Quick Dates Pills */}
        {availableDates.length > 0 && (
          <div className="max-w-[1920px] mx-auto mt-2.5 pt-2 border-t border-slate-800/60 flex items-center gap-2 overflow-x-auto text-[11px] font-mono text-slate-400">
            <span className="text-slate-500 whitespace-nowrap">Partitioned Dates:</span>
            {availableDates.slice(0, 6).map((d) => (
              <button
                key={d}
                onClick={() => {
                  setStartDate(d);
                  setEndDate(d);
                }}
                className={`px-2 py-0.5 rounded border transition-colors ${
                  startDate === d && endDate === d
                    ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300 font-semibold'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* =====================================================================
          MAIN TABLE VIEW
          ===================================================================== */}
      <main className="flex-1 max-w-[1920px] w-full mx-auto p-4 sm:p-6 overflow-x-auto">
        {errorMsg && (
          <div className="mb-4 p-3 rounded-xl bg-red-950/40 border border-red-500/40 flex items-center gap-2 text-xs font-mono text-red-300">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/60 shadow-xl">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/80 text-[11px] text-slate-400 uppercase tracking-wider">
                <th className="py-3 px-4 w-48">Timestamp (IST)</th>
                <th className="py-3 px-4 w-56">Event Type</th>
                <th className="py-3 px-4 w-44">Actor / System</th>
                <th className="py-3 px-4 w-44">Source Node</th>
                <th className="py-3 px-4">Details & AI Telemetry</th>
                <th className="py-3 px-4 text-right w-28">Metadata</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500 font-mono">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <RefreshCw className="w-5 h-5 animate-spin text-emerald-400" />
                      <span>Streaming encrypted audit records from black box storage...</span>
                    </div>
                  </td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500 font-mono">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Layers className="w-6 h-6 text-slate-600" />
                      <span className="text-slate-400 font-semibold">No audit logs found matching criteria</span>
                      <span className="text-slate-600 text-[11px]">Adjust date range, event type filter or search tokens</span>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedRecords.map((rec) => (
                  <tr
                    key={rec.id}
                    className="hover:bg-slate-900/50 transition-colors group"
                  >
                    {/* Timestamp */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="font-semibold text-slate-200">{rec.timestamp_ist}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{rec.timestamp_utc}</div>
                    </td>

                    {/* Event Type */}
                    <td className="py-3 px-4">
                      {renderEventBadge(rec.event_type)}
                    </td>

                    {/* Actor */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-1.5 text-slate-300">
                        {rec.actor.includes('VOICE') || rec.actor.includes('IRIS') ? (
                          <Bot className="w-3.5 h-3.5 text-cyan-400" />
                        ) : rec.actor.includes('superadmin') || rec.actor.includes('admin') ? (
                          <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                        ) : (
                          <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
                        )}
                        <span className="font-semibold truncate max-w-[150px]" title={rec.actor}>
                          {rec.actor}
                        </span>
                      </div>
                    </td>

                    {/* Source / Camera Node */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-1.5 text-slate-300">
                        <Server className="w-3.5 h-3.5 text-slate-500" />
                        <span className="text-cyan-400 font-bold">{rec.source}</span>
                      </div>
                      <div className="text-[10px] text-slate-500 truncate max-w-[140px]" title={rec.zone}>
                        {rec.zone}
                      </div>
                    </td>

                    {/* Details & Telemetry */}
                    <td className="py-3 px-4">
                      <div className="text-slate-200 line-clamp-2 leading-relaxed">
                        {rec.details}
                      </div>
                      {rec.voice_command && (
                        <div className="mt-1 text-[11px] text-cyan-300 font-mono bg-cyan-950/20 px-2 py-0.5 rounded border border-cyan-800/30 inline-block">
                          <span className="text-cyan-500 font-bold">Voice: </span>"{rec.voice_command}"
                        </div>
                      )}
                    </td>

                    {/* Metadata Button */}
                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <button
                        onClick={() => setSelectedRecordForModal(rec)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white transition-colors text-[11px]"
                        title="Inspect full JSON telemetry payload"
                      >
                        <Eye className="w-3 h-3 text-cyan-400" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {/* Pagination Footer */}
          {records.length > pageSize && (
            <div className="px-4 py-3 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between text-xs font-mono text-slate-400">
              <div>
                Showing {(currentPage - 1) * pageSize + 1} to{' '}
                {Math.min(currentPage * pageSize, records.length)} of {records.length} records
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="p-1 rounded bg-slate-900 border border-slate-800 disabled:opacity-40 hover:bg-slate-800 text-slate-300"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="px-2">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="p-1 rounded bg-slate-900 border border-slate-800 disabled:opacity-40 hover:bg-slate-800 text-slate-300"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* =====================================================================
          PAYLOAD INSPECTOR MODAL
          ===================================================================== */}
      {selectedRecordForModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl max-w-2xl w-full overflow-hidden text-slate-100 flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/80">
              <div className="flex items-center gap-2.5">
                <Activity className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-bold font-mono tracking-wider uppercase">
                  Audit Telemetry Payload ({selectedRecordForModal.id})
                </h3>
              </div>
              <button
                onClick={() => setSelectedRecordForModal(null)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 font-mono text-xs">
              <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-slate-950 border border-slate-800">
                <div>
                  <span className="text-slate-500 block text-[10px]">Event Type:</span>
                  <span className="text-slate-200 font-bold">{selectedRecordForModal.event_type}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Actor:</span>
                  <span className="text-slate-200 font-bold">{selectedRecordForModal.actor}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Source Node:</span>
                  <span className="text-cyan-400 font-bold">{selectedRecordForModal.source}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Zone:</span>
                  <span className="text-slate-300">{selectedRecordForModal.zone}</span>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-slate-400 text-[11px] uppercase tracking-wider">
                    Full JSON Payload:
                  </span>
                  <button
                    onClick={() =>
                      copyToClipboard(JSON.stringify(selectedRecordForModal, null, 2))
                    }
                    className="flex items-center gap-1 text-[11px] text-cyan-400 hover:text-cyan-300"
                  >
                    {copiedPayload ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedPayload ? 'Copied!' : 'Copy JSON'}</span>
                  </button>
                </div>
                <pre className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 text-emerald-400 text-[11px] overflow-x-auto max-h-72">
                  {JSON.stringify(selectedRecordForModal, null, 2)}
                </pre>
              </div>
            </div>

            <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-end">
              <button
                onClick={() => setSelectedRecordForModal(null)}
                className="px-4 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs transition-colors"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AuditLogsPage;
