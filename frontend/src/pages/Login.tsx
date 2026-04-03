import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogIn, Loader2, AlertCircle } from "lucide-react";
import { useLogin } from "@/hooks/use-auth";

function DoraemonLogo() {
  return (
    <div className="relative w-24 h-24 mx-auto mb-4 animate-pocket-open">
      <svg viewBox="0 0 512 512" className="w-full h-full drop-shadow-lg">
        <circle cx="256" cy="256" r="240" fill="#0096C7"/>
        <ellipse cx="256" cy="280" rx="175" ry="165" fill="white"/>
        <ellipse cx="222" cy="190" rx="32" ry="36" fill="white" stroke="#0C1222" strokeWidth="3"/>
        <ellipse cx="290" cy="190" rx="32" ry="36" fill="white" stroke="#0C1222" strokeWidth="3"/>
        <circle cx="232" cy="195" r="12" fill="#0C1222"/>
        <circle cx="280" cy="195" r="12" fill="#0C1222"/>
        <circle cx="236" cy="189" r="4" fill="white"/>
        <circle cx="284" cy="189" r="4" fill="white"/>
        <circle cx="256" cy="228" r="16" fill="#EF4444"/>
        <line x1="256" y1="244" x2="256" y2="300" stroke="#0C1222" strokeWidth="3"/>
        <path d="M176 280 Q216 340 256 300 Q296 340 336 280" fill="none" stroke="#0C1222" strokeWidth="3" strokeLinecap="round"/>
        <line x1="90" y1="230" x2="190" y2="248" stroke="#0C1222" strokeWidth="2.5"/>
        <line x1="85" y1="260" x2="188" y2="265" stroke="#0C1222" strokeWidth="2.5"/>
        <line x1="90" y1="290" x2="190" y2="282" stroke="#0C1222" strokeWidth="2.5"/>
        <line x1="422" y1="230" x2="322" y2="248" stroke="#0C1222" strokeWidth="2.5"/>
        <line x1="427" y1="260" x2="324" y2="265" stroke="#0C1222" strokeWidth="2.5"/>
        <line x1="422" y1="290" x2="322" y2="282" stroke="#0C1222" strokeWidth="2.5"/>
        <rect x="140" y="390" width="232" height="24" rx="12" fill="#EF4444"/>
        <circle cx="256" cy="414" r="18" fill="#FCD34D" stroke="#D97706" strokeWidth="2"/>
      </svg>
    </div>
  );
}

export default function Login() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();
  const login = useLogin();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login.mutateAsync({ identifier, password });
      navigate("/");
    } catch {
      // Error handled by mutation state
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F0F9FF] dark:bg-[#0C1222] p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <DoraemonLogo />
          <div className="flex items-center justify-center gap-2 mb-2">
            <span className="text-3xl font-bold text-[#0096C7]">4D</span>
            <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">Pocket</span>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 italic">
            Reach into your pocket and pull out exactly what you need.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white dark:bg-gray-900 rounded-2xl border border-sky-100 dark:border-gray-800 shadow-sm p-6 space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              Email or Username
            </label>
            <input
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="you@example.com or username"
              required
              autoFocus
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-[#F0F9FF] dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-[#0096C7] focus:border-transparent transition-all"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-[#F0F9FF] dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-[#0096C7] focus:border-transparent transition-all"
            />
          </div>

          {login.isError && (
            <div className="flex items-center gap-2 text-red-500 text-sm bg-red-50 dark:bg-red-950/30 px-3 py-2 rounded-xl">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              Invalid credentials
            </div>
          )}

          <button
            type="submit"
            disabled={login.isPending}
            className="w-full py-2.5 bg-[#0096C7] text-white rounded-xl font-medium hover:bg-[#0077A8] active:scale-[0.98] transition-all duration-200 disabled:opacity-50 cursor-pointer flex items-center justify-center gap-2"
          >
            {login.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <LogIn className="w-4 h-4" />
            )}
            {login.isPending ? "Signing in..." : "Sign in"}
          </button>

          <p className="text-center text-sm text-gray-500 dark:text-gray-400">
            Don't have an account?{" "}
            <Link
              to="/register"
              className="text-[#0096C7] hover:text-[#0077A8] dark:text-sky-400 font-medium cursor-pointer"
            >
              Create one
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
