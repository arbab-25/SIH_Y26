import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  message: string | null;
}

/** Custom full-page error screen — replaces blank-page crashes (custom error page). */
export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error?.message || null };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('CODE MAZE crashed:', error, info.componentStack);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.hash = '';
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center p-6 font-sans">
          <div className="max-w-lg w-full bg-white rounded-2xl border border-slate-200 shadow-xl overflow-hidden">
            <div className="bg-[#12355B] p-6 text-white flex items-center gap-3">
              <div className="h-11 w-11 rounded-xl bg-rose-500/90 flex items-center justify-center shrink-0">
                <AlertTriangle size={24} />
              </div>
              <div>
                <h1 className="text-lg font-bold">CODE MAZE</h1>
                <p className="text-xs text-cyan-200">Legal Metrology Compliance System</p>
              </div>
            </div>

            <div className="p-8 text-center space-y-4">
              <div className="mx-auto h-16 w-16 rounded-full bg-rose-50 border border-rose-200 flex items-center justify-center">
                <AlertTriangle size={30} className="text-rose-500" />
              </div>
              <h2 className="text-xl font-extrabold text-[#12355B]">
                Something went wrong
              </h2>
              <p className="text-sm text-slate-600 max-w-sm mx-auto">
                The application hit an unexpected error and could not continue.
                Your saved scans and reports are safe on the server. Try reloading,
                or return to the scan workspace.
              </p>

              {this.state.message && (
                <p className="text-[11px] text-slate-400 font-mono bg-slate-50 border border-slate-100 rounded-lg p-2.5 max-w-sm mx-auto break-words">
                  {this.state.message}
                </p>
              )}

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                <button
                  onClick={this.handleReload}
                  className="flex items-center gap-2 px-5 py-2.5 bg-[#12355B] hover:bg-[#0F2C4C] text-white text-sm font-bold rounded-xl shadow transition-all min-h-[44px]"
                >
                  <RefreshCw size={16} />
                  Reload Application
                </button>
                <button
                  onClick={this.handleGoHome}
                  className="flex items-center gap-2 px-5 py-2.5 bg-white hover:bg-slate-50 text-[#12355B] border border-slate-300 text-sm font-bold rounded-xl transition-all min-h-[44px]"
                >
                  <Home size={16} />
                  Go to Scanner
                </button>
              </div>
            </div>

            <div className="bg-slate-50 border-t border-slate-100 px-6 py-3 text-center text-[11px] text-slate-400">
              If this keeps happening, contact the system administrator.
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
