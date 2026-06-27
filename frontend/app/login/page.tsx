"use client";

import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";

export default function LoginPage() {
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const { login } = useAuth();
  const router = useRouter();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    try {
      setLoading(true);
      const res = await login(form.username, form.password);
      const role = (res?.role || "").toLowerCase();

      if (role === "admin") {
        router.push("/admin");
      } else {
        router.push("/");
      }
    } catch (err: any) {
      setError(err.message || "Login gagal");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl p-8 border border-sky-100 ring-1 ring-sky-50">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-black">Welcome Back</h1>
          <p className="text-gray-500 text-sm">Login untuk melanjutkan</p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 text-sm text-red-600 bg-red-50 p-2 rounded-lg text-center border border-red-200">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-sm text-gray-700">Username</label>
            <input
              name="username"
              placeholder="Masukkan username"
              className="w-full mt-1 px-3 py-2 bg-sky-50/50 border border-sky-200 text-black placeholder-gray-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-400 focus:border-sky-400"
              onChange={handleChange}
            />
          </div>

          <div className="relative">
            <label className="text-sm text-gray-700">Password</label>
            <input
              name="password"
              type={showPassword ? "text" : "password"}
              placeholder="Masukkan password"
              className="w-full mt-1 px-3 py-2 bg-sky-50/50 border border-sky-200 text-black placeholder-gray-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-400 focus:border-sky-400"
              onChange={handleChange}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-9 text-sky-400 hover:text-sky-500"
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>

          {/* Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-sky-400 text-white py-2 rounded-lg hover:bg-sky-500 transition disabled:opacity-70 shadow-md shadow-sky-200"
          >
            {loading ? (
              <>
                <Loader2 className="animate-spin" size={18} /> Loading...
              </>
            ) : (
              "Login"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}