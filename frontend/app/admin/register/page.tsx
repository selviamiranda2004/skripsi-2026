"use client";

import { useState } from "react";

export default function RegisterPage() {
  const [form, setForm] = useState({
    email: "",
    username: "",
    phone: "",
    password: "",
    role: "user",
  });

  // 🔥 HANDLE INPUT
  const handleChange = (e: any) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

  // 🔥 SUBMIT
  const handleSubmit = () => {
    const { email, username, phone, password, role } = form;

    // VALIDASI
    if (!email || !username || !phone || !password) {
      alert("Semua field wajib diisi!");
      return;
    }

    // ambil data lama
    const existingUsers = JSON.parse(localStorage.getItem("users") || "[]");

    // cek username unik
    const isExist = existingUsers.find(
      (user: any) => user.username === username
    );

    if (isExist) {
      alert("Username sudah digunakan!");
      return;
    }

    // 🔥 BUAT USER BARU
    const newUser = {
      id: Date.now(),
      email,
      username,
      phone,
      password,
      role,
    };

    // 🔥 SIMPAN KE LOCALSTORAGE
    localStorage.setItem(
      "users",
      JSON.stringify([...existingUsers, newUser])
    );

    alert("User berhasil ditambahkan 🎉");

    // reset form (opsional)
    setForm({
      email: "",
      username: "",
      phone: "",
      password: "",
      role: "user",
    });

    // redirect
    window.location.href = "/admin";
  };

  return (
    <div className="flex justify-center items-center min-h-screen bg-background">
      <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow w-96">
        <h1 className="text-xl font-bold mb-4 text-center">
          Register User
        </h1>

        {/* EMAIL */}
        <input
          type="email"
          name="email"
          placeholder="Email"
          className="w-full mb-3 p-2 border rounded dark:bg-gray-700"
          value={form.email}
          onChange={handleChange}
        />

        {/* USERNAME */}
        <input
          type="text"
          name="username"
          placeholder="Username"
          className="w-full mb-3 p-2 border rounded dark:bg-gray-700"
          value={form.username}
          onChange={handleChange}
        />

        {/* PHONE */}
        <input
          type="text"
          name="phone"
          placeholder="Nomor Telepon"
          className="w-full mb-3 p-2 border rounded dark:bg-gray-700"
          value={form.phone}
          onChange={handleChange}
        />

        {/* PASSWORD */}
        <input
          type="password"
          name="password"
          placeholder="Password"
          className="w-full mb-3 p-2 border rounded dark:bg-gray-700"
          value={form.password}
          onChange={handleChange}
        />

        {/* ROLE */}
        <select
          name="role"
          className="w-full mb-4 p-2 border rounded dark:bg-gray-700"
          value={form.role}
          onChange={handleChange}
        >
          <option value="user">User</option>
          <option value="admin">Admin</option>
        </select>

        {/* BUTTON SIMPAN */}
        <button
          onClick={handleSubmit}
          className="w-full bg-blue-500 text-white py-2 rounded mb-2 hover:bg-blue-600"
        >
          Simpan
        </button>

        {/* BUTTON BATAL */}
        <button
          onClick={() => (window.location.href = "/admin")}
          className="w-full bg-gray-400 text-white py-2 rounded hover:bg-gray-500"
        >
          Batal
        </button>
      </div>
    </div>
  );
}

