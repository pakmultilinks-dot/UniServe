/**
 * UniServe — Email Verification Page
 *
 * Placeholder for email verification via OTP.
 * Full OTP flow will be implemented in a future phase.
 */
"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const userId = searchParams.get("userId");

  return (
    <div className="w-full max-w-md p-8 bg-white rounded-lg shadow-md">
      <h1 className="text-2xl font-bold text-center mb-6">
        Verify Your Email
      </h1>
      <p className="text-gray-600 text-center mb-4">
        A verification code has been sent to your university email.
      </p>
      {userId && (
        <p className="text-sm text-gray-500 text-center mb-4">
          User ID: {userId}
        </p>
      )}
      <p className="text-sm text-gray-400 text-center">
        OTP verification will be implemented in a future phase.
      </p>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="text-gray-500">Loading…</div>}>
      <VerifyEmailContent />
    </Suspense>
  );
}
