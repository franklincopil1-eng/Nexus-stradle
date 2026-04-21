import React, { useState, useEffect, useRef, ReactNode } from 'react';
import { 
  Activity, Shield, AlertTriangle, Terminal, Zap, TrendingUp, 
  TrendingDown, ChartLine, LayoutDashboard, History, BarChart3, 
  Settings, Power, XCircle, ChevronRight, Menu, X, Cpu, Globe
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface LogEntry {
  timestamp: string;
  level: 'INFO' | 'STRATEGY' | 'EXECUTION' | 'ERROR' | 'SUCCESS';
  message: string;
}

interface Order {
  ticket: string;
  symbol: string;
  type: string;
  volume: string | number;
  price_open: number;
  sl: number;
  tp: number;
  status: 'PENDING' | 'OPEN';
}

interface HistoryEntry {
  ticket: string;
  type: string;
  volume: string;
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  timeEntry: string;
  timeExit: string;
}

export default function App() {
  const [symbol, setSymbol] = useState('XAUUSD');
  const [price, setPrice] = useState(0);
  const [spread, setSpread] = useState(0);
  const [rangeHigh, setRangeHigh] = useState(0);
  const [rangeLow, setRangeLow] = useState(0);
  const [riskSettings, setRiskSettings] = useState({
    fixedLot: 0,
    slPoints: 0,
    tpPoints: 0,
    trailingStop: 0,
    lookback: 0
  });
  const [systemStatus, setSystemStatus] = useState('ENGAGED');
  const [account, setAccount] = useState({
    balance: 0,
    equity: 0,
    marginFree: 0,
    floatingPL: 0
  });
  const [brokers, setBrokers] = useState<any[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [backtestResult, setBacktestResult] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'pipeline' | 'history' | 'performance'>('pipeline');
  const [isBridgeActive, setIsBridgeActive] = useState<boolean>(false);
  const [strategyStatus, setStrategyStatus] = useState<string>('INITIALIZING');
  const [isSidebarOpen, setIsSidebarOpen] = useState(window.innerWidth > 1024);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 1024) setIsSidebarOpen(true);
      else setIsSidebarOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const [sessionStartTime] = useState(Date.now());
  const [sessionDuration, setSessionDuration] = useState('00:00:00');

  useEffect(() => {
    const timer = setInterval(() => {
      const diff = Date.now() - sessionStartTime;
      const h = Math.floor(diff / 3600000).toString().padStart(2, '0');
      const m = Math.floor((diff % 3600000) / 60000).toString().padStart(2, '0');
      const s = Math.floor((diff % 60000) / 1000).toString().padStart(2, '0');
      setSessionDuration(`${h}:${m}:${s}`);
    }, 1000);
    return () => clearInterval(timer);
  }, [sessionStartTime]);

  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchState = async () => {
      try {
        const res = await fetch('/api/state', { cache: 'no-store' });
        if (!res.ok) throw new Error('API Unavailable');
        const data = await res.json();
        
        if (isMounted && data) {
          setIsBridgeActive(!!data.bridgeActive);
          setPrice(data.price ?? 0);
          setSymbol(data.symbol || 'XAUUSD');
          setSpread(data.spread ?? 0);
          setRangeHigh(data.rangeHigh ?? 0);
          setRangeLow(data.rangeLow ?? 0);
          if (data.riskSettings) setRiskSettings(data.riskSettings);
          if (data.systemStatus) setSystemStatus(data.systemStatus);
          if (data.account) setAccount(data.account);
          setBrokers(data.brokers || []);
          setOrders(data.orders || []);
          setHistory(data.history || []);
          setLogs(data.logs || []);
          setBacktestResult(data.backtestResult || null);
          setLastUpdated(new Date().toLocaleTimeString());
          
          if (data.price > 0) {
            setStrategyStatus(data.bridgeActive ? 'ACTIVE_MONITORING' : 'BRIDGE_DISCONNECTED');
          } else {
            setStrategyStatus(data.bridgeActive ? 'AWAITING_DATA' : 'BRIDGE_DISCONNECTED');
          }
        }
      } catch (err) {
        if (isMounted) setIsBridgeActive(false);
      }
    };

    fetchState();
    const interval = setInterval(fetchState, 1500); 
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const sendCommand = async (command: string) => {
    try {
      await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
      });
    } catch (err) {
      console.error("Command failed", err);
    }
  };

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="flex h-screen bg-[#070708] text-[#e1e1e3] font-sans overflow-hidden">
      {/* Responsive Overlay */}
      <AnimatePresence>
        {!isSidebarOpen && (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsSidebarOpen(true)}
            className="fixed top-4 left-4 z-50 p-2 bg-[#1a1a1c] border border-[#333] rounded-md md:hidden"
          >
            <Menu size={20} />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Sidebar: Navigation & Controls */}
      <aside 
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-[#0d0d0f] border-r border-[#1f1f22] transform transition-transform duration-300 ease-in-out md:relative md:translate-x-0 ${
          isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Brand */}
          <div className="p-6 border-b border-[#1f1f22] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-[#22c55e]/10 rounded-lg">
                <Shield className="text-[#22c55e]" size={20} />
              </div>
              <span className="text-lg font-black tracking-tighter uppercase">Atlas-X</span>
            </div>
            <button onClick={() => setIsSidebarOpen(false)} className="md:hidden opacity-50 hover:opacity-100">
              <X size={20} />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1">
            <NavItem 
              active={activeTab === 'pipeline'} 
              icon={<LayoutDashboard size={18} />} 
              label="Pipeline" 
              onClick={() => setActiveTab('pipeline')} 
            />
            <NavItem 
              active={activeTab === 'history'} 
              icon={<History size={18} />} 
              label="Journal" 
              onClick={() => setActiveTab('history')} 
            />
            <NavItem 
              active={activeTab === 'performance'} 
              icon={<BarChart3 size={18} />} 
              label="Performance" 
              onClick={() => setActiveTab('performance')} 
            />
          </nav>

          {/* System Control Hooks */}
          <div className="p-4 border-t border-[#1f1f22] space-y-4">
            <div className="space-y-2">
              <h4 className="text-[10px] uppercase tracking-widest text-[#555] font-bold">Execution Control</h4>
              <button 
                onClick={() => sendCommand(systemStatus === 'ENGAGED' ? 'HALT' : 'RESUME')}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded text-xs font-bold transition-all border ${
                  systemStatus === 'ENGAGED' 
                    ? 'bg-[#ef4444]/5 border-[#ef4444]/20 text-[#ef4444] hover:bg-[#ef4444]/10' 
                    : 'bg-[#22c55e]/5 border-[#22c55e]/20 text-[#22c55e] hover:bg-[#22c55e]/10'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Power size={14} />
                  {systemStatus === 'ENGAGED' ? 'HALT ENGINE' : 'RESUME ENGINE'}
                </div>
                <ChevronRight size={14} />
              </button>
              <button 
                onClick={() => sendCommand('CLOSE_ALL')}
                className="w-full flex items-center gap-2 px-3 py-2.5 rounded text-xs font-bold text-[#e1e1e3] transition-all bg-[#1a1a1c] border border-[#333] hover:bg-[#252528] active:scale-95"
              >
                <XCircle size={14} /> Panic: Close All
              </button>
            </div>

            <div className="space-y-2">
              <h4 className="text-[10px] uppercase tracking-widest text-[#555] font-bold">Status Matrix</h4>
              <div className="p-3 bg-[#131315] rounded border border-[#1f1f22] space-y-2">
                <StatusItem 
                  label="Bridge Link" 
                  active={isBridgeActive} 
                  status={isBridgeActive ? 'ONLINE' : 'OFFLINE'} 
                />
                <StatusItem 
                  label="Engine Core" 
                  active={strategyStatus === 'ACTIVE_MONITORING'} 
                  status={strategyStatus} 
                />
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Operational Bar */}
        <header className="h-16 border-b border-[#1f1f22] bg-[#0d0d0f] flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-4">
              <div className="flex flex-col">
                <span className="text-[10px] uppercase text-[#555] tracking-widest font-bold">Live Asset</span>
                <span className="text-sm font-black tracking-tight">{symbol}</span>
              </div>
              <div className="h-8 w-px bg-[#1f1f22]" />
              <div className="flex flex-col">
                <span className="text-[10px] uppercase text-[#555] tracking-widest font-bold">Execution Price</span>
                <motion.span 
                  key={price}
                  initial={{ color: '#fff' }}
                  animate={{ color: price > 0 ? '#22c55e' : '#fff' }}
                  className="text-lg font-mono font-bold"
                >
                  {price.toFixed(2)}
                </motion.span>
              </div>
            </div>
          </div>

          <div className="hidden lg:flex items-center gap-10">
            <MetricSmall label="Session Time" value={sessionDuration} />
            <MetricSmall label="Spread" value={`${spread} pts`} />
            <MetricSmall label="Session PL" value={`$${account.floatingPL.toFixed(2)}`} highlight={account.floatingPL >= 0} />
            <MetricSmall label="Last Sync" value={lastUpdated || '--'} />
          </div>
        </header>

        {/* Dashboard Grid */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Executive Overview */}
          <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card title="Equity Stability">
              <div className="flex items-end justify-between">
                <div className="text-2xl font-mono font-bold">${account.equity.toLocaleString()}</div>
                <div className="text-[10px] text-[#22c55e] font-mono">+0.00%</div>
              </div>
              <div className="mt-2 text-[10px] text-[#555] uppercase tracking-wider">Free Margin: ${account.marginFree.toLocaleString()}</div>
            </Card>
            <Card title="Portfolio Balance">
              <div className="text-2xl font-mono font-bold">${account.balance.toLocaleString()}</div>
              <div className="mt-2 text-[10px] text-[#555] uppercase tracking-wider">Base Currency: USD</div>
            </Card>
            <Card title="Range Boundary">
              <div className="flex items-center justify-between font-mono text-sm">
                <div className="flex flex-col">
                  <span className="text-[9px] text-[#555]">HIGH</span>
                  <span className="text-[#22c55e]">{rangeHigh.toFixed(2)}</span>
                </div>
                <ChevronRight size={14} className="text-[#22c55e]" />
                <div className="flex flex-col text-right">
                  <span className="text-[9px] text-[#555]">LOW</span>
                  <span className="text-[#ef4444]">{rangeLow.toFixed(2)}</span>
                </div>
              </div>
            </Card>
            <Card title="Risk Profile">
              <div className="grid grid-cols-2 gap-2 text-[10px] font-mono leading-tight">
                <div>LOTS: <span className="text-white">{riskSettings.fixedLot}</span></div>
                <div>SL: <span className="text-white">{riskSettings.slPoints}</span></div>
                <div>TP: <span className="text-white">{riskSettings.tpPoints}</span></div>
                <div>TS: <span className="text-white">{riskSettings.trailingStop}</span></div>
              </div>
            </Card>
          </section>

          {/* Active Data Panel */}
          <section className="flex-1 bg-[#0d0d0f] border border-[#1f1f22] rounded-lg overflow-hidden flex flex-col min-h-[400px]">
            <div className="px-5 py-3 border-b border-[#1f1f22] bg-[#131315] flex items-center justify-between">
              <h3 className="text-[11px] uppercase tracking-[3px] font-black text-[#888]">
                {activeTab === 'pipeline' ? 'Trade Pipeline' : activeTab === 'history' ? 'Execution Journal' : 'Performance Analytics'}
              </h3>
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => setActiveTab('pipeline')}
                  className={`p-1.5 rounded hover:bg-[#1a1a1c] transition-colors ${activeTab === 'pipeline' ? 'text-white' : 'text-[#444]'}`}
                >
                  <LayoutDashboard size={16} />
                </button>
                <button 
                  onClick={() => setActiveTab('history')}
                  className={`p-1.5 rounded hover:bg-[#1a1a1c] transition-colors ${activeTab === 'history' ? 'text-white' : 'text-[#444]'}`}
                >
                  <History size={16} />
                </button>
                <button 
                  onClick={() => setActiveTab('performance')}
                  className={`p-1.5 rounded hover:bg-[#1a1a1c] transition-colors ${activeTab === 'performance' ? 'text-white' : 'text-[#444]'}`}
                >
                  <BarChart3 size={16} />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-auto">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeTab}
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                  transition={{ duration: 0.2 }}
                  className="h-full"
                >
                  {activeTab === 'pipeline' && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left font-mono">
                        <thead className="bg-[#070708] border-b border-[#1f1f22]">
                          <tr className="text-[9px] uppercase text-[#555] tracking-widest">
                            <th className="px-6 py-3">TICKET</th>
                            <th className="px-6 py-3">CONTRACT</th>
                            <th className="px-6 py-3">TYPE</th>
                            <th className="px-6 py-3">SIZE</th>
                            <th className="px-6 py-3">PRICE</th>
                            <th className="px-6 py-3">STATUS</th>
                          </tr>
                        </thead>
                        <tbody className="text-xs divide-y divide-[#1f1f22]">
                          {orders.map((o) => (
                            <tr key={o.ticket} className="hover:bg-white/[0.02] transition-colors group">
                              <td className="px-6 py-4 text-[#777]">{o.ticket}</td>
                              <td className="px-6 py-4 font-bold">{o.symbol}</td>
                              <td className="px-6 py-4">
                                <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                                  o.type.includes('BUY') ? 'bg-[#22c55e]/10 text-[#22c55e]' : 'bg-[#ef4444]/10 text-[#ef4444]'
                                }`}>
                                  {o.type}
                                </span>
                              </td>
                              <td className="px-6 py-4">{o.volume}</td>
                              <td className="px-6 py-4">{o.price_open}</td>
                              <td className="px-6 py-4">
                                <div className="flex items-center gap-2">
                                  <div className={`w-1.5 h-1.5 rounded-full ${o.status === 'OPEN' ? 'bg-[#22c55e] animate-pulse' : 'bg-[#eab308]'}`} />
                                  {o.status}
                                </div>
                              </td>
                            </tr>
                          ))}
                          {orders.length === 0 && (
                            <tr>
                              <td colSpan={6} className="px-6 py-20 text-center text-[#444] text-[10px] uppercase font-bold tracking-[4px]">
                                No Active Deployments
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {activeTab === 'history' && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left font-mono">
                        <thead className="bg-[#070708] border-b border-[#1f1f22]">
                          <tr className="text-[9px] uppercase text-[#555] tracking-widest">
                            <th className="px-6 py-3">TICKET</th>
                            <th className="px-6 py-3">ACTION</th>
                            <th className="px-6 py-3">ENTRY</th>
                            <th className="px-6 py-3">EXIT</th>
                            <th className="px-6 py-3">NET P/L</th>
                            <th className="px-6 py-3">SESSION</th>
                          </tr>
                        </thead>
                        <tbody className="text-xs divide-y divide-[#1f1f22]">
                          {history.map((h) => (
                            <tr key={h.ticket} className="hover:bg-white/[0.02]">
                              <td className="px-6 py-4 text-[#777]">{h.ticket}</td>
                              <td className="px-6 py-4 font-bold">{h.type}</td>
                              <td className="px-6 py-4">{h.entryPrice.toFixed(2)}</td>
                              <td className="px-6 py-4">{h.exitPrice.toFixed(2)}</td>
                              <td className={`px-6 py-4 font-black ${h.pnl >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]'}`}>
                                {h.pnl >= 0 ? '+' : ''}{h.pnl.toFixed(2)}
                              </td>
                              <td className="px-6 py-4 text-[#555]">{h.timeExit}</td>
                            </tr>
                          ))}
                          {history.length === 0 && (
                            <tr>
                              <td colSpan={6} className="px-6 py-20 text-center text-[#444] text-[10px] uppercase font-bold tracking-[4px]">
                                Journal is Empty
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {activeTab === 'performance' && (
                    <div className="p-8 h-full flex flex-col gap-8">
                       <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        <MetricCard label="Win Rate" value={`${backtestResult?.win_rate || 0}%`} color="#22c55e" />
                        <MetricCard label="PF Ratio" value={backtestResult?.avg_rr || 0} />
                        <MetricCard label="Trades" value={backtestResult?.total_trades || 0} />
                        <MetricCard label="Net (Sim)" value={`$${backtestResult?.total_pnl?.toFixed(2) || '0.00'}`} highlight={backtestResult?.total_pnl >= 0} />
                      </div>
                      <div className="flex-1 min-h-[300px] border border-[#1f1f22] rounded bg-black/40 p-6">
                        <h4 className="text-[10px] uppercase tracking-[2px] font-bold text-[#555] mb-4 flex items-center gap-2">
                          <ChartLine size={12} /> Simulated Equity Curve
                        </h4>
                        {backtestResult ? (
                          <ResponsiveContainer width="100%" height="90%">
                            <LineChart data={backtestResult.equity_curve.map((val: number, i: number) => ({ i, val }))}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#1f1f22" vertical={false} />
                              <XAxis dataKey="i" hide />
                              <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{fill: '#444', fontSize: 10}} />
                              <Tooltip contentStyle={{backgroundColor: '#0d0d0f', border: '1px solid #333'}} />
                              <Line type="stepAfter" dataKey="val" stroke="#22c55e" strokeWidth={2} dot={false} />
                            </LineChart>
                          </ResponsiveContainer>
                        ) : (
                          <div className="h-full flex flex-col items-center justify-center opacity-30">
                            <ChartLine size={48} className="mb-4" />
                            <span className="text-xs font-bold uppercase tracking-widest tracking-widest">No Meta-Data Available</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          </section>
        </div>

        {/* Responsive Footer Log Terminal */}
        <footer className="h-[220px] shrink-0 border-t border-[#1f1f22] bg-[#070708] flex flex-col font-mono">
          <div className="px-4 py-1.5 bg-[#0d0d0f] border-b border-[#1f1f22] flex items-center justify-between">
            <div className="flex items-center gap-2 text-[10px] font-black uppercase text-[#555] tracking-[2px]">
              <Terminal size={10} /> Atlas-X System Terminal Output
            </div>
            <div className="flex gap-4">
              <span className="text-[9px] text-[#22c55e]/60 font-bold tracking-widest">LIVE_LINK:ESTABLISHED</span>
              <span className="text-[9px] text-[#444] font-bold tracking-widest uppercase">Buffer: {logs.length}/100</span>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 text-[10.5px] leading-[1.4] scrollbar-hide">
            {logs.map((log, idx) => (
              <div key={idx} className="mb-0.5 grid grid-cols-[110px_90px_1fr] hover:bg-white/[0.03] transition-colors">
                <span className="text-[#333]">[{log.timestamp}]</span>
                <span className={`font-bold ${
                  log.level === 'INFO' ? 'text-[#3b82f6]/70' : 
                  log.level === 'STRATEGY' ? 'text-[#eab308]/70' : 
                  log.level === 'SUCCESS' ? 'text-[#22c55e]/70' :
                  log.level === 'ERROR' ? 'text-[#ef4444]/70' :
                  'text-[#22c55e]/70'
                }`}>
                  {log.level.padEnd(9)}
                </span>
                <span className="text-[#a1a1aa] selection:bg-[#22c55e] selection:text-black">{log.message}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </footer>
      </main>
    </div>
  );
}

// Sub-components for clean terminal architecture
function NavItem({ active, icon, label, onClick }: { active: boolean, icon: React.ReactNode, label: string, onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2 text-sm font-medium rounded transition-all group ${
        active 
          ? 'bg-[#1a1a1c] text-[#22c55e] border border-white/5' 
          : 'text-[#666] hover:text-[#bbb] hover:bg-white/[0.02]'
      }`}
    >
      <span className={`${active ? 'text-[#22c55e]' : 'text-[#444] group-hover:text-[#666]'}`}>{icon}</span>
      {label}
      {active && <motion.div layoutId="nav-active" className="ml-auto w-1.5 h-1.5 bg-[#22c55e] rounded-full" />}
    </button>
  );
}

function StatusItem({ label, active, status }: { label: string, active: boolean, status: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[10px] text-[#555] font-bold">{label}</span>
      <div className="flex items-center gap-1.5">
        <div className={`w-1 h-1 rounded-full ${active ? 'bg-[#22c55e]' : 'bg-[#ef4444]'}`} />
        <span className={`text-[10px] font-mono font-bold ${active ? 'text-[#22c55e]' : 'text-[#ef4444]'}`}>{status}</span>
      </div>
    </div>
  );
}

function MetricSmall({ label, value, highlight }: { label: string, value: string | number, highlight?: boolean }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase text-[#555] tracking-widest font-bold">{label}</span>
      <span className={`text-xs font-mono font-bold ${highlight ? 'text-[#22c55e]' : 'text-white'}`}>
        {value}
      </span>
    </div>
  );
}

function Card({ title, children }: { title: string, children: React.ReactNode }) {
  return (
    <div className="p-4 bg-[#0d0d0f] border border-[#1f1f22] rounded-lg relative overflow-hidden group">
      <div className="absolute top-0 left-0 w-1 h-full bg-[#22c55e]/0 group-hover:bg-[#22c55e]/100 transition-all duration-500" />
      <h4 className="text-[10px] uppercase tracking-widest text-[#555] font-bold mb-3">{title}</h4>
      {children}
    </div>
  );
}

function MetricCard({ label, value, color, highlight }: { label: string, value: string | number, color?: string, highlight?: boolean }) {
  return (
    <div className="p-4 bg-black/20 border border-[#1f1f22] rounded flex flex-col gap-1">
      <span className="text-[9px] uppercase tracking-widest text-[#444] font-bold">{label}</span>
      <span className="text-lg font-mono font-black" style={{ color: color || (highlight !== undefined ? (highlight ? '#22c55e' : '#ef4444') : '#fff') }}>
        {value}
      </span>
    </div>
  );
}
