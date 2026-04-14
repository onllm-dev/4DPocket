import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserPlus, Loader2, AlertCircle, Eye, EyeOff } from "lucide-react";
import { useRegister, useLogin } from "@/hooks/use-auth";

function DoraemonLogo() {
  return (
    <img
      src="/icons/icon-512.png"
      alt="4DPocket"
      className="relative w-24 h-24 mx-auto mb-4 rounded-2xl"
    />
  );
}

export default function Register() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const register = useRegister();
  const login = useLogin();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    try {
      await register.mutateAsync({
        username,
        email,
        password,
        display_name: displayName || undefined,
      });
      // Auto-login after registration
      await login.mutateAsync({ identifier: email, password });
      navigate("/");
    } catch (err: unknown) {
      const isConflict = err instanceof Error && err.message.includes("409");
      if (isConflict) {
        setError("Email or username already registered");
      } else {
        setError(err instanceof Error ? err.message : "Registration failed");
      }
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
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Choose a username"
              required
              autoFocus
              minLength={3}
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-[#F0F9FF] dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-[#0096C7] focus:border-transparent transition-all"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-[#F0F9FF] dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-[#0096C7] focus:border-transparent transition-all"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              Display Name <span className="text-gray-400">(optional)</span>
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your display name"
              className="w-full px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-[#F0F9FF] dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-[#0096C7] focus:border-transparent transition-all"
            />
          </div>

          <div>
            <label htmlFor="register-password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              Password
            </label>
            <div className="relative">
              <input
                id="register-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
                required
                minLength={6}
                className="w-full px-4 py-2.5 pr-11 rounded-xl border border-gray-200 dark:border-gray-700 bg-[#F0F9FF] dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-[#0096C7] focus:border-transparent transition-all"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer p-1"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {(error || register.isError) && (
            <div className="flex items-center gap-2 text-red-500 text-sm bg-red-50 dark:bg-red-950/30 px-3 py-2 rounded-xl">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error || "Registration failed. Please try again."}
            </div>
          )}

          <button
            type="submit"
            disabled={register.isPending || login.isPending}
            className="w-full py-2.5 bg-[#0096C7] text-white rounded-xl font-medium hover:bg-[#0077A8] active:scale-[0.98] transition-all duration-200 disabled:opacity-50 cursor-pointer flex items-center justify-center gap-2"
          >
            {register.isPending || login.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <UserPlus className="w-4 h-4" />
            )}
            {register.isPending ? "Creating account..." : login.isPending ? "Signing in..." : "Create account"}
          </button>

          <p className="text-center text-sm text-gray-500 dark:text-gray-400">
            Already have an account?{" "}
            <Link
              to="/login"
              className="text-[#0096C7] hover:text-[#0077A8] dark:text-sky-400 font-medium cursor-pointer"
            >
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
