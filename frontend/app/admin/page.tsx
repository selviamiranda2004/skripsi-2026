"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";

import Sidebar from "@/components/Sidebar";
import DashboardAdminPage from "@/components/DashboardAdminPage";
import AdminMentionsPage from "@/components/AdminMentionsPage";
import SentimentPage from "@/components/AdminSentimentSection";
import SvmTrainingPage from "@/components/SvmTrainingPage";
import AutoRefreshIndicator from "@/components/AutoRefreshIndicator";
import { useAutoRefreshNews } from "@/hooks/useAutoRefreshNews";
import { Pencil, Trash2, X } from "lucide-react";

interface User {
  username: string;
  email: string;
  role: string;
}

function EditUserModal({
  user,
  token,
  onClose,
  onSuccess,
}: {
  user: User;
  token: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form, setForm] = useState({
    username: user.username,
    email: user.email || "",
    role: user.role,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    setError("");
    if (!form.username) { setError("Username tidak boleh kosong"); return; }
    setLoading(true);

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "/api"}/auth/users/${user.username}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            username: form.username,
            email: form.email,
            role: form.role,
          }),
        }
      );

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white border border-border rounded-xl p-6 w-full max-w-sm shadow-xl">

        <div className="flex justify-between items-center mb-5">
          <h3 className="font-semibold text-base text-black">Edit User</h3>
          <button onClick={onClose} className="text-black hover:text-black">
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-100 text-red-700 rounded text-sm">{error}</div>
        )}

        <div className="space-y-3">
          <div>
            <label className="text-xs text-black mb-1 block">Username</label>
            <input
              className="w-full p-2 border rounded text-sm text-black bg-white"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              disabled={user.username === "admin"}
            />
          </div>

          <div>
            <label className="text-xs text-black mb-1 block">Email</label>
            <input
              className="w-full p-2 border rounded text-sm text-black bg-white"
              placeholder="Email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>

          <div>
            <label className="text-xs text-black mb-1 block">Role</label>
            <select
              className="w-full p-2 border rounded text-sm text-black bg-white"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              disabled={user.username === "admin"}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            {user.username === "admin" && (
              <p className="text-xs text-black mt-1">
                Username dan role admin tidak bisa diubah
              </p>
            )}
          </div>
        </div>

        <div className="flex gap-2 mt-5">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border rounded text-sm text-black hover:bg-gray-100 transition"
          >
            Batal
          </button>
          <button
            onClick={handleSave}
            disabled={loading}
            className="flex-1 px-4 py-2 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 transition disabled:opacity-50"
          >
            {loading ? "Menyimpan..." : "Simpan"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AdminPage() {
  const { user, token, logout, isAuthenticated, loading } = useAuth();
  const router = useRouter();

  const [activePage, setActivePage] = useState("dashboard");
  const [users, setUsers] = useState<User[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [editingUser, setEditingUser] = useState<User | null>(null);

  const [newUser, setNewUser] = useState({
    username: "",
    email: "",
    password: "",
    role: "user",
  });

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const autoRefresh = useAutoRefreshNews({ intervalSec: 3600 });

  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) { router.push("/login"); return; }
    if (user?.role !== "admin") router.push("/");
  }, [user, loading, isAuthenticated, router]);

  useEffect(() => {
    if (token && user?.role === "admin") fetchUsers();
  }, [token, user]);

  const fetchUsers = async () => {
    try {
      setUsersLoading(true);
      const res = await fetch("${process.env.NEXT_PUBLIC_API_URL || "/api"}/auth/users", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to fetch users");
      const data = await res.json();
      setUsers(data.users);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUsersLoading(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setSuccess("");
    if (!newUser.username || !newUser.password) {
      setError("Username dan password harus diisi");
      return;
    }
    try {
      const res = await fetch("${process.env.NEXT_PUBLIC_API_URL || "/api"}/auth/create-user", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(newUser),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Gagal membuat user");
      }
      setSuccess(`User ${newUser.username} berhasil dibuat`);
      setNewUser({ username: "", email: "", password: "", role: "user" });
      fetchUsers();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteUser = async (username: string) => {
    if (!confirm(`Hapus user ${username}?`)) return;
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "/api"}/auth/users/${username}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Gagal menghapus user");
      }
      setSuccess(`User ${username} berhasil dihapus`);
      fetchUsers();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleLogout = () => { logout(); router.push("/login"); };

  const getPageTitle = () => {
    switch (activePage) {
      case "dashboard": return "Dashboard";
      case "users": return "Manage Users";
      case "mentions": return "Mentions";
      case "sentiment": return "Sentiment Analysis";
      case "svm-train": return "Train SVM";
      default: return "Dashboard";
    }
  };

  const renderPage = () => {
    switch (activePage) {
      case "dashboard":
        return <DashboardAdminPage />;

      case "users":
        return (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* CREATE USER */}
            <div className="bg-white border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold mb-4 text-black">Buat User Baru</h2>

              {error && (
                <div className="mb-4 p-3 bg-red-100 text-red-700 rounded text-sm">{error}</div>
              )}
              {success && (
                <div className="mb-4 p-3 bg-green-100 text-green-700 rounded text-sm">{success}</div>
              )}

              <form onSubmit={handleCreateUser} className="space-y-3">
                <input
                  className="w-full p-2 border rounded text-sm text-black bg-white"
                  placeholder="Username"
                  value={newUser.username}
                  onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                />
                <input
                  className="w-full p-2 border rounded text-sm text-black bg-white"
                  placeholder="Email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                />
                <input
                  type="password"
                  className="w-full p-2 border rounded text-sm text-black bg-white"
                  placeholder="Password"
                  value={newUser.password}
                  onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                />
                <select
                  className="w-full p-2 border rounded text-sm bg-white text-black focus:outline-none focus:ring-2 focus:ring-primary/50"
                  value={newUser.role}
                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                >
                  <option value="user" className="bg-white text-black">User</option>
                  <option value="admin" className="bg-white text-black">Admin</option>
                </select>
                <button className="w-full bg-blue-500 text-white p-2 rounded text-sm hover:bg-blue-600 transition">
                  Buat User
                </button>
              </form>
            </div>

            {/* USER LIST */}
            <div className="bg-white border border-border rounded-lg p-6">
              <h2 className="text-lg font-semibold mb-4 text-black">
                Daftar User ({users.length})
              </h2>

              {usersLoading ? (
                <p className="text-sm text-black">Loading...</p>
              ) : (
                <div className="space-y-2">
                  {users.map((u) => (
                    <div
                      key={u.username}
                      className="flex justify-between items-center p-3 border rounded-lg"
                    >
                      <div className="min-w-0">
                        <p className="font-medium text-sm text-black">{u.username}</p>
                        <p className="text-xs text-black truncate">
                          {u.email || "—"}
                        </p>
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium mt-1 inline-block ${
                            u.role === "admin"
                              ? "bg-blue-100 text-blue-700"
                              : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {u.role}
                        </span>
                      </div>

                      <div className="flex gap-2 ml-2 shrink-0">
                        <button
                          onClick={() => setEditingUser(u)}
                          className="w-8 h-8 flex items-center justify-center rounded-lg border text-gray-400 hover:text-blue-500 hover:border-blue-400 transition"
                          title="Edit user"
                        >
                          <Pencil size={14} />
                        </button>

                        {u.username !== "admin" && (
                          <button
                            onClick={() => handleDeleteUser(u.username)}
                            className="w-8 h-8 flex items-center justify-center rounded-lg border text-gray-400 hover:text-red-500 hover:border-red-400 transition"
                            title="Hapus user"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );

      case "mentions":
        return <AdminMentionsPage />;

      case "sentiment":
        return <SentimentPage />;

      case "svm-train":
        return <SvmTrainingPage />;

      default:
        return <DashboardAdminPage />;
    }
  };

  if (loading || !isAuthenticated || user?.role !== "admin") return null;

  return (
    <div className="min-h-screen bg-white">
      <Sidebar activePage={activePage} onPageChange={setActivePage} role="admin" />

      {editingUser && token && (
        <EditUserModal
          user={editingUser}
          token={token}
          onClose={() => setEditingUser(null)}
          onSuccess={() => {
            setSuccess(`User ${editingUser.username} berhasil diupdate`);
            fetchUsers();
          }}
        />
      )}

      <main className="lg:ml-64 min-h-screen">
        <header className="sticky top-0 z-20 bg-white backdrop-blur-md border-b border-border px-6 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-xl font-semibold text-black">{getPageTitle()}</h1>
            <div className="flex gap-4 items-center">
              <AutoRefreshIndicator state={autoRefresh} />
              <span className="text-sm text-black">
                {user?.username} ({user?.role})
              </span>
              <button
                onClick={handleLogout}
                className="bg-red-500 text-white px-3 py-1 rounded text-sm"
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        <div className="p-6">{renderPage()}</div>
      </main>
    </div>
  );
}