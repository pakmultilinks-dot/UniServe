/**
 * UniServe — Forgot Password Page
 *
 * Placeholder for password reset flow.
 * Will be implemented in a future phase.
 */
"use client";

import React, { useState } from "react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="w-full max-w-md p-8 bg-white rounded-lg shadow-md">
      <h1 className="text-2xl font-bold text-center mb-6">Reset Password</h1>

      {submitted ? (
        <p className="text-green-700 text-center">
          If an account exists with that email, a reset code has been sent.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <p className="text-gray-600 text-sm text-center">
            Enter your university email to receive a password reset code.
          </p>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="your.name@lgu.edu.pk"
          />
          <button
            type="submit"
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Send Reset Code
          </button>
        </form>
      )}
    </div>
  );
}
