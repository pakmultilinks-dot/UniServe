/**
 * UniServe — Landing Page
 *
 * Public front door for LGU students and faculty. Static-export safe.
 * Focused only on ordering food: browse, order, pick up. No admin or
 * staff tooling is mentioned here; that lives behind login.
 */

"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

function Nav() {
  const [open, setOpen] = useState(false);
  const { isAuthenticated } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border-light)] bg-[var(--bg-primary)]/85 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-3">
          <img
            src="/lgu-logo.jpg"
            alt="Lahore Garrison University logo"
            className="h-10 w-10 rounded-full border border-[var(--border-default)] object-cover"
          />
          <span className="leading-tight">
            <span className="block text-base font-extrabold tracking-tight text-[var(--text-primary)]">
              UniServe
            </span>
            <span className="block text-[11px] font-medium text-[var(--text-muted)]">
              Lahore Garrison University
            </span>
          </span>
        </Link>

        <div className="hidden items-center gap-7 md:flex">
          <a href="#cafeterias" className="text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-brand-700">
            Cafeterias
          </a>
          <a href="#how" className="text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-brand-700">
            How it works
          </a>
        </div>

        <div className="hidden md:block">
          {isAuthenticated ? (
            <Link
              href="/dashboard"
              className="rounded-full bg-brand-700 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-800"
            >
              Open app
            </Link>
          ) : (
            <Link
              href="/login"
              className="rounded-full bg-brand-700 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-800"
            >
              Sign in
            </Link>
          )}
        </div>

        <button
          className="rounded-lg p-2 text-[var(--text-primary)] md:hidden"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </nav>

      {open && (
        <div className="border-t border-[var(--border-light)] px-4 py-3 md:hidden">
          <a href="#cafeterias" className="block py-2 text-sm font-medium text-[var(--text-secondary)]" onClick={() => setOpen(false)}>
            Cafeterias
          </a>
          <a href="#how" className="block py-2 text-sm font-medium text-[var(--text-secondary)]" onClick={() => setOpen(false)}>
            How it works
          </a>
          <Link
            href={isAuthenticated ? "/dashboard" : "/login"}
            className="mt-2 block rounded-full bg-brand-700 px-5 py-2.5 text-center text-sm font-semibold text-white"
            onClick={() => setOpen(false)}
          >
            {isAuthenticated ? "Open app" : "Sign in"}
          </Link>
        </div>
      )}
    </header>
  );
}

function Hero() {
  const { isAuthenticated } = useAuth();

  return (
    <section className="mx-auto max-w-6xl px-4 pb-16 pt-14 sm:px-6 sm:pt-20">
      <div className="grid items-center gap-10 md:grid-cols-2">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-brand-800">
            Lahore Garrison University &middot; Campus Dining
          </p>
          <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight text-[var(--text-primary)] sm:text-5xl">
            Skip the line.<br />
            Your cafeteria,<br />
            in your pocket.
          </h1>
          <p className="mt-5 max-w-md text-base leading-relaxed text-[var(--text-secondary)]">
            Order ahead from the Student and Faculty cafeterias, get notified
            when your food is ready, and pick it up without waiting.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                className="rounded-full bg-brand-700 px-7 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-800"
              >
                Open app
              </Link>
            ) : (
              <>
                <Link
                  href="/register"
                  className="rounded-full bg-brand-700 px-7 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-800"
                >
                  Get started
                </Link>
                <Link
                  href="/login"
                  className="rounded-full border border-[var(--border-default)] px-7 py-3 text-sm font-semibold text-[var(--text-primary)] transition-colors hover:border-brand-400"
                >
                  Sign in
                </Link>
              </>
            )}
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--border-default)] bg-[var(--bg-secondary)] p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img src="/lgu-logo.jpg" alt="" aria-hidden="true" className="h-11 w-11 rounded-full object-cover" />
              <div>
                <p className="text-sm font-bold text-[var(--text-primary)]">Student Cafeteria</p>
                <p className="text-xs text-[var(--text-muted)]">Order #LGU-1031 &middot; Today</p>
              </div>
            </div>
            <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800">
              Preparing
            </span>
          </div>

          <div className="mt-5 space-y-3">
            {[
              ["Chicken Biryani", "Student Cafeteria", "Rs 250.00"],
              ["Karak Chai (Large)", "Chai & Qahwa", "Rs 120.00"],
              ["Chicken Tikka Roll", "Desi Snacks", "Rs 180.00"],
            ].map(([name, cat, price]) => (
              <div key={name} className="flex items-center justify-between border-b border-[var(--border-light)] pb-3 last:border-0">
                <div>
                  <p className="text-sm font-semibold text-[var(--text-primary)]">{name}</p>
                  <p className="text-xs text-[var(--text-muted)]">{cat}</p>
                </div>
                <p className="text-sm font-bold text-[var(--text-primary)]">{price}</p>
              </div>
            ))}
          </div>

          <div className="mt-5 flex items-center justify-between text-xs text-[var(--text-muted)]">
            <span>Ordered</span>
            <span className="font-semibold text-brand-700">Preparing</span>
            <span>Ready</span>
            <span>Picked up</span>
          </div>
          <p className="mt-4 text-center text-sm text-[var(--text-secondary)]">
            Ready in about <strong>10 minutes</strong>. We will notify you.
          </p>
        </div>
      </div>
    </section>
  );
}

function Cafeterias() {
  return (
    <section id="cafeterias" className="border-t border-[var(--border-light)] bg-[var(--bg-secondary)]">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-700">Cafeterias</p>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
            Two cafeterias, one app
          </h2>
        </div>

        <div className="mt-10 grid gap-6 md:grid-cols-2">
          <div className="rounded-3xl border border-[var(--border-default)] bg-[var(--bg-primary)] p-8">
            <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
              Open to students &amp; faculty
            </p>
            <h3 className="mt-2 text-xl font-bold text-[var(--text-primary)]">Student Cafeteria</h3>
            <p className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">
              Desi favorites, snacks, chai, and cold drinks at student-friendly
              prices. Order ahead between lectures and skip the queue.
            </p>
          </div>
          <div className="rounded-3xl border border-[var(--border-default)] bg-[var(--bg-primary)] p-8">
            <p className="text-xs font-semibold uppercase tracking-wider text-brand-700">
              Faculty only
            </p>
            <h3 className="mt-2 text-xl font-bold text-[var(--text-primary)]">Faculty Cafeteria</h3>
            <p className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">
              A quieter space with a curated menu for faculty members, with
              the same order-ahead convenience.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    {
      n: "1",
      title: "Browse the menu",
      text: "Pick your cafeteria and see today's menu with real prices.",
    },
    {
      n: "2",
      title: "Place your order",
      text: "Add items to your cart, choose pickup time, and pay by cash or online.",
    },
    {
      n: "3",
      title: "Track & pick up",
      text: "Watch your order go from Ordered to Ready. Show your pickup code and enjoy.",
    },
  ];

  return (
    <section id="how" className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <div className="mx-auto max-w-2xl text-center">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-700">How it works</p>
        <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
          From craving to pickup in three steps
        </h2>
      </div>

      <div className="mt-10 grid gap-6 md:grid-cols-3">
        {steps.map((s) => (
          <div key={s.n} className="rounded-3xl border border-[var(--border-default)] bg-[var(--bg-primary)] p-8">
            <p className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-700 text-sm font-bold text-white">
              {s.n}
            </p>
            <h3 className="mt-4 text-lg font-bold text-[var(--text-primary)]">{s.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">{s.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Cta() {
  return (
    <section className="bg-brand-900">
      <div className="mx-auto max-w-6xl px-4 py-16 text-center sm:px-6">
        <img src="/lgu-logo.jpg" alt="LGU logo" className="mx-auto h-16 w-16 rounded-full border-2 border-white/30 object-cover" />
        <h2 className="mt-6 text-3xl font-extrabold tracking-tight text-white">
          Hungry? Your next meal is minutes away.
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-brand-100">
          Join Lahore Garrison University&apos;s campus dining platform and never
          wait in a cafeteria line again.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Link
            href="/register"
            className="rounded-full bg-white px-7 py-3 text-sm font-semibold text-brand-900 transition-colors hover:bg-brand-50"
          >
            Create account
          </Link>
          <Link
            href="/login"
            className="rounded-full border border-white/40 px-7 py-3 text-sm font-semibold text-white transition-colors hover:border-white"
          >
            Sign in
          </Link>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-[var(--border-light)]">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row sm:px-6">
        <div className="flex items-center gap-3">
          <img src="/lgu-logo.jpg" alt="LGU logo" className="h-9 w-9 rounded-full object-cover" />
          <div className="leading-tight">
            <p className="text-sm font-bold text-[var(--text-primary)]">UniServe</p>
            <p className="text-xs text-[var(--text-muted)]">Lahore Garrison University</p>
          </div>
        </div>
        <p className="text-xs text-[var(--text-muted)]">
          Campus dining, simplified.
        </p>
      </div>
    </footer>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <Nav />
      <main>
        <Hero />
        <Cafeterias />
        <HowItWorks />
        <Cta />
      </main>
      <Footer />
    </div>
  );
}
