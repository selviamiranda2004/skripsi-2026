"use client";

import { useState, useEffect } from "react";
import { Trash2, Pencil, Eye, EyeOff } from "lucide-react";

interface User {
  id: number;
  username: string;
  email?: string;
  phone?: string;
  password: string;
  role: string;
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [showPassword, setShowPassword] = useState<number | null>(null);

  // 🔥 LOAD DATA
  useEffect(() => {
    const storedUsers = JSON.parse(localStorage.getItem("users") || "[]");
    setUsers(storedUsers);
  }, []);

  // 🔥 DELETE
  const handleDelete = (id: number) => {
    if (!confirm("Yakin mau hapus user?")) return;

    const updatedUsers = users.filter((user) => user.id !== id);
    setUsers(updatedUsers);
    localStorage.setItem("users", JSON.stringify(updatedUsers));
  };

  // 🔥 UPDATE USER
  const handleUpdate = () => {
    if (!editingUser) return;

    const updatedUsers = users.map((user) =>
      user.id === editingUser.id ? editingUser : user
    );

    setUsers(updatedUsers);
    localStorage.setItem("users", JSON.stringify(updatedUsers));
    setEditingUser(null);
  };

  return (
    <div>
      {/* HEADER */}
      <div className="flex justify-between items-center mb-6">
      <h1 className="text-2xl font-bold text-black">User Management</h1>

        <button
          onClick={() => (window.location.href = "/admin/register")}
         className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
        >
          + Tambah User
        </button>
      </div>

      {/* 🔥 FORM EDIT */}
      {editingUser && (
        <div className="mb-6 p-4 border rounded-xl bg-gray-50">
           <h2 className="font-bold mb-3 text-black">Edit User</h2>

          <input
            type="text"
            value={editingUser.username}
            onChange={(e) =>
              setEditingUser({ ...editingUser, username: e.target.value })
            }
           className="block w-full mb-2 p-2 border rounded text-black bg-white"
            placeholder="Username"
          />

          <input
            type="text"
            value={editingUser.email || ""}
            onChange={(e) =>
              setEditingUser({ ...editingUser, email: e.target.value })
            }
            className="block w-full mb-2 p-2 border rounded text-black bg-white"
            placeholder="Email"
          />

          <input
            type="text"
            value={editingUser.phone || ""}
            onChange={(e) =>
              setEditingUser({ ...editingUser, phone: e.target.value })
            }
            className="block w-full mb-2 p-2 border rounded text-black bg-white"
            placeholder="Phone"
          />

          <input
            type="text"
            value={editingUser.password}
            onChange={(e) =>
              setEditingUser({ ...editingUser, password: e.target.value })
            }
            className="block w-full mb-2 p-2 border rounded text-black bg-white"
            placeholder="Password"
          />

          <select
            value={editingUser.role}
            onChange={(e) =>
              setEditingUser({ ...editingUser, role: e.target.value })
            }
           className="block w-full mb-3 p-2 border rounded text-black bg-white"
          >
            <option value="admin">Admin</option>
            <option value="user">User</option>
          </select>

          <div className="flex gap-2">
            <button
              onClick={handleUpdate}
              className="px-4 py-2 bg-green-500 text-white rounded"
            >
              Simpan
            </button>

            <button
              onClick={() => setEditingUser(null)}
              className="px-4 py-2 bg-gray-400 text-white rounded"
            >
              Batal
            </button>
          </div>
        </div>
      )}

      {/* LIST USER */}
     <div className="bg-white rounded-xl shadow overflow-hidden">
        {users.length === 0 && (
        <p className="p-4 text-center text-black">
            Belum ada user
          </p>
        )}

        {users.map((user) => (
          <div
            key={user.id}
              className="flex justify-between items-center p-4 border-b hover:bg-gray-50"
          >
            <div>
          <p className="font-semibold text-black">{user.username}</p>

              {user.email && (
                <p className="text-sm text-black">{user.email}</p>
              )}
              {user.phone && (
                <p className="text-sm text-black">{user.phone}</p>
              )}

              {/* 🔥 PASSWORD */}
             <p className="text-sm text-black flex items-center gap-2">
                Password:{" "}
                {showPassword === user.id
                  ? user.password
                  : "••••••"}
                <button
                  onClick={() =>
                    setShowPassword(
                      showPassword === user.id ? null : user.id
                    )
                  }
                  className="text-blue-500"
                >
                  {showPassword === user.id ? (
                    <EyeOff size={16} />
                  ) : (
                    <Eye size={16} />
                  )}
                </button>
              </p>

              <span className="text-xs text-blue-500">
                {user.role}
              </span>
            </div>

            <div className="flex gap-3">
              {/* EDIT */}
              <button
                onClick={() => setEditingUser(user)}
                className="flex items-center gap-1 text-yellow-500 hover:text-yellow-600"
              >
                <Pencil size={16} />
                Edit
              </button>

              {/* DELETE */}
              <button
                onClick={() => handleDelete(user.id)}
                className="flex items-center gap-1 text-red-500 hover:text-red-600"
              >
                <Trash2 size={16} />
                Hapus
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}