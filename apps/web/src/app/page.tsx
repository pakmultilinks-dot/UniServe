/**
 * UniServe — Landing Page
 *
 * Public front door of the product. Static-export safe: pure client
 * component, no `redirect()` (which breaks `output: "export"` builds).
 * Visual language follows the warm cream / bronze / gold identity used
 * across the app, adapted for a university cafeteria product.
 */

"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

/* ---------- small building blocks ---------- */

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-brand-800 dark:border-brand-900 dark:bg-brand-900/30 dark:text-brand-200">
      {children}
    </span>
  );
}

function SectionHeading({
  eyebrow,
  title,
  sub,
}: {
  eyebrow: string;
  title: string;
  sub?: string;
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-700 dark:text-brand-400">
        {eyebrow}
      </p>
      <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-4xl">
        {title}
      </h2>
      {sub && (
        <p className="mt-4 text-base leading-relaxed text-[var(--text-secondary)]">
          {sub}
        </p>
      )}
    </div>
  );
}

/* ---------- page sections ---------- */

function Nav() {
  const [open, setOpen] = useState(false);
  const { isAuthenticated } = useAuth();

  const links = [
    { href: "#cafeterias", label: "Cafeterias" },
    { href: "#menu", label: "Menu" },
    { href: "#how", label: "How it works" },
    
  ];

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
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-brand-700 dark:hover:text-brand-300"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="hidden items-center gap-3 md:flex">
          {isAuthenticated ? (
            <Link
              href="/dashboard"
              className="rounded-full bg-brand-700 px-5 py-2.5 text-sm font-semibold text-white shadow-card transition-colors hover:bg-brand-800"
            >
              Go to dashboard
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-full px-4 py-2.5 text-sm font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-secondary)]"
              >
                Sign in
              </Link>
              <Link
                href="/register"
                className="rounded-full bg-brand-700 px-5 py-2.5 text-sm font-semibold text-white shadow-card transition-colors hover:bg-brand-800"
              >
                Get started
              </Link>
            </>
          )}
        </div>

        <button
          type="button"
          aria-label="Toggle menu"
          onClick={() => setOpen((v) => !v)}
          className="rounded-lg p-2 text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] md:hidden"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {open ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </nav>

      {open && (
        <div className="border-t border-[var(--border-light)] bg-[var(--bg-primary)] px-4 py-3 md:hidden">
          <div className="flex flex-col gap-1">
            {links.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]"
              >
                {l.label}
              </a>
            ))}
            <div className="mt-2 flex gap-2 border-t border-[var(--border-light)] pt-3">
              {isAuthenticated ? (
                <Link
                  href="/dashboard"
                  className="flex-1 rounded-full bg-brand-700 px-4 py-2.5 text-center text-sm font-semibold text-white"
                >
                  Go to dashboard
                </Link>
              ) : (
                <>
                  <Link
                    href="/login"
                    className="flex-1 rounded-full border border-[var(--border-default)] px-4 py-2.5 text-center text-sm font-semibold text-[var(--text-primary)]"
                  >
                    Sign in
                  </Link>
                  <Link
                    href="/register"
                    className="flex-1 rounded-full bg-brand-700 px-4 py-2.5 text-center text-sm font-semibold text-white"
                  >
                    Get started
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
}

function Hero() {
  const { isAuthenticated } = useAuth();

  return (
    <section className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 right-0 h-96 w-96 rounded-full bg-brand-200/40 blur-3xl dark:bg-brand-900/20"
      />
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 pb-16 pt-14 sm:px-6 lg:grid-cols-2 lg:pt-20">
        <div className="animate-fade-in">
          <Badge>
            <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />
            Lahore Garrison University &middot; Campus Dining
          </Badge>
          <h1 className="mt-5 text-4xl font-extrabold leading-[1.08] tracking-tight text-[var(--text-primary)] sm:text-5xl lg:text-[3.4rem]">
            Skip the line.
            <br />
            Your cafeteria,
            <br />
            <span className="text-brand-700 dark:text-brand-400">in your pocket.</span>
          </h1>
          <p className="mt-5 max-w-lg text-lg leading-relaxed text-[var(--text-secondary)]">
            Order ahead from the Student and Faculty cafeterias, track your
            order live, and pick it up the moment it is ready. Built for LGU
            students, faculty, and cafeteria teams.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                className="rounded-full bg-brand-700 px-7 py-3.5 text-sm font-semibold text-white shadow-card transition-all hover:bg-brand-800 hover:shadow-card-hover"
              >
                Go to dashboard
              </Link>
            ) : (
              <>
                <Link
                  href="/register"
                  className="rounded-full bg-brand-700 px-7 py-3.5 text-sm font-semibold text-white shadow-card transition-all hover:bg-brand-800 hover:shadow-card-hover"
                >
                  Create free account
                </Link>
                <Link
                  href="/login"
                  className="rounded-full border border-[var(--border-default)] bg-[var(--bg-primary)] px-7 py-3.5 text-sm font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-secondary)]"
                >
                  Sign in
                </Link>
              </>
            )}
          </div>
          <div className="mt-8 flex items-center gap-4">
            <div className="flex" aria-label="Rated 4.9 out of 5">
              {[1, 2, 3, 4, 5].map((s) => (
                <svg key={s} className="h-5 w-5 text-gold-500" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10 1.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L10 14.9 4.7 17.6l1-5.8L1.5 7.7l5.9-.9L10 1.5z" />
                </svg>
              ))}
            </div>
            <p className="text-sm text-[var(--text-muted)]">
              <span className="font-semibold text-[var(--text-primary)]">4.9/5</span> from
              campus food lovers
            </p>
          </div>
        </div>

        {/* Hero visual: order card echoing live tracking */}
        <div className="relative mx-auto w-full max-w-md animate-fade-in lg:max-w-none">
          <div className="rounded-[2rem] border border-[var(--border-default)] bg-[var(--bg-primary)] p-6 shadow-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <img
                  src="/lgu-logo.jpg"
                  alt="LGU logo"
                  className="h-11 w-11 rounded-full border border-[var(--border-default)] object-cover"
                />
                <div>
                  <p className="text-sm font-bold text-[var(--text-primary)]">Student Cafeteria</p>
                  <p className="text-xs text-[var(--text-muted)]">Order #LGU-1031 &middot; Today</p>
                </div>
              </div>
              <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800 dark:bg-green-900/30 dark:text-green-300">
                Preparing
              </span>
            </div>

            <div className="mt-5 space-y-3">
              {[
                { name: "Chicken Biryani", detail: "Student Cafeteria", price: "Rs 250.00" },
                { name: "Karak Chai (Large)", detail: "Chai & Qahwa", price: "Rs 120.00" },
                { name: "Chicken Tikka Roll", detail: "Desi Snacks", price: "Rs 180.00" },
              ].map((item) => (
                <div
                  key={item.name}
                  className="flex items-center justify-between rounded-xl bg-[var(--bg-secondary)] px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-semibold text-[var(--text-primary)]">{item.name}</p>
                    <p className="text-xs text-[var(--text-muted)]">{item.detail}</p>
                  </div>
                  <p className="text-sm font-bold text-[var(--text-primary)]">{item.price}</p>
                </div>
              ))}
            </div>

            {/* tracker */}
            <div className="mt-6">
              <div className="flex items-center">
                {["Ordered", "Preparing", "Ready", "Picked up"].map((step, i) => (
                  <div key={step} className="flex flex-1 items-center last:flex-none">
                    <div className="flex flex-col items-center gap-1.5">
                      <span
                        className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
                          i < 2
                            ? "bg-brand-700 text-white"
                            : "bg-[var(--bg-tertiary)] text-[var(--text-muted)]"
                        }`}
                      >
                        {i < 2 ? (
                          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M16.7 5.3a1 1 0 010 1.4l-8 8a1 1 0 01-1.4 0l-4-4a1 1 0 111.4-1.4L8 12.6l7.3-7.3a1 1 0 011.4 0z" clipRule="evenodd" />
                          </svg>
                        ) : (
                          i + 1
                        )}
                      </span>
                      <span className="text-[10px] font-medium text-[var(--text-muted)]">{step}</span>
                    </div>
                    {i < 3 && (
                      <div className={`mx-1 mb-5 h-0.5 flex-1 rounded ${i < 1 ? "bg-brand-600" : "bg-[var(--border-default)]"}`} />
                    )}
                  </div>
                ))}
              </div>
              <p className="mt-3 text-center text-sm text-[var(--text-muted)]">
                Ready in about <span className="font-semibold text-[var(--text-primary)]">10 minutes</span>.
                We will notify you.
              </p>
            </div>
          </div>

          {/* floating cards */}
          <div className="absolute -left-4 top-8 hidden rounded-2xl border border-[var(--border-default)] bg-[var(--bg-primary)] px-4 py-3 shadow-card sm:block">
            <p className="text-xs font-medium text-[var(--text-muted)]">Today&apos;s special</p>
            <p className="text-sm font-bold text-[var(--text-primary)]">Chicken Biryani</p>
          </div>
          <div className="absolute -right-3 bottom-10 hidden rounded-2xl border border-[var(--border-default)] bg-[var(--bg-primary)] px-4 py-3 shadow-card sm:block">
            <p className="text-sm font-bold text-[var(--text-primary)]">Rs 250.00</p>
            <p className="text-xs font-medium text-green-700 dark:text-green-400">In stock</p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Stats() {
  const stats = [
    { value: "2", label: "Campus cafeterias" },
    { value: "50+", label: "Dishes on the menu" },
    { value: "Live", label: "Order tracking" },
    { value: "10 min", label: "Average pickup time" },
  ];
  return (
    <section className="border-y border-[var(--border-light)] bg-[var(--bg-secondary)]">
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-4 py-10 sm:px-6 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="text-center">
            <p className="text-3xl font-extrabold tracking-tight text-brand-800 dark:text-brand-300">
              {s.value}
            </p>
            <p className="mt-1 text-sm font-medium text-[var(--text-muted)]">{s.label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Cafeterias() {
  const cards = [
    {
      name: "Student Cafeteria",
      tag: "Open to students & faculty",
      desc: "The everyday hub: desi favorites, snacks, chai, and cold drinks at student-friendly prices. Order ahead between lectures.",
      points: ["Order ahead, skip the queue", "Live preparation updates", "Cash and online payment"],
    },
    {
      name: "Faculty Cafeteria",
      tag: "Faculty only",
      desc: "A quieter space with a curated menu for faculty members, with the same order-ahead convenience.",
      points: ["Faculty-exclusive menu", "Reserved pickup counter", "Monthly billing statements"],
    },
  ];
  return (
    <section id="cafeterias" className="scroll-mt-20">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <SectionHeading
          eyebrow="Cafeterias"
          title="Two cafeterias, one app"
          sub="Each cafeteria runs its own menu, hours, and pickup counter. UniServe keeps them separate and simple."
        />
        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {cards.map((c) => (
            <div
              key={c.name}
              className="rounded-[1.75rem] border border-[var(--border-default)] bg-[var(--bg-primary)] p-8 shadow-card transition-shadow hover:shadow-card-hover"
            >
              <span className="inline-block rounded-full bg-brand-100 px-3 py-1 text-xs font-semibold text-brand-800 dark:bg-brand-900/40 dark:text-brand-200">
                {c.tag}
              </span>
              <h3 className="mt-4 text-2xl font-extrabold tracking-tight text-[var(--text-primary)]">
                {c.name}
              </h3>
              <p className="mt-3 leading-relaxed text-[var(--text-secondary)]">{c.desc}</p>
              <ul className="mt-6 space-y-2.5">
                {c.points.map((p) => (
                  <li key={p} className="flex items-start gap-2.5 text-sm text-[var(--text-secondary)]">
                    <svg className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand-700 dark:text-brand-400" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M16.7 5.3a1 1 0 010 1.4l-8 8a1 1 0 01-1.4 0l-4-4a1 1 0 111.4-1.4L8 12.6l7.3-7.3a1 1 0 011.4 0z" clipRule="evenodd" />
                    </svg>
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function MenuPreview() {
  const cats = [
    { name: "Main Courses", urdu: "مین کورسز", icon: "M4 12h16a1 1 0 001-1V7a1 1 0 00-1-1H4a1 1 0 00-1 1v4a1 1 0 001 1zm2 2h12a4 4 0 01-4 4h-4a4 4 0 01-4-4z" },
    { name: "Desi & Curries", urdu: "دیسی کھانے", icon: "M12 3c-4.97 0-9 3.58-9 8 0 2.52 1.34 4.9 3.5 6.35.35.24.5.68.35 1.07L6 20h12l-.85-1.58c-.15-.39 0-.83.35-1.07C19.66 15.9 21 13.52 21 11c0-4.42-4.03-8-9-8z" },
    { name: "Chai & Qahwa", urdu: "چائے", icon: "M6 3h9l-2 7H8L6 3zm-2 9h12v2a5 5 0 01-5 5h-2a5 5 0 01-5-5v-2zm14 1h2a1 1 0 011 1v1a4 4 0 01-4 4h-1" },
    { name: "Snacks", urdu: "نمکو", icon: "M7 4h10l3 5-3 5H7l-3-5 3-5zm0 10h10v3a2 2 0 01-2 2H9a2 2 0 01-2-2v-3z" },
    { name: "Cold Drinks", urdu: "ٹھنڈے مشروبات", icon: "M8 3h8l-1 18H9L8 3zm2 4h4" },
    { name: "Hot Drinks", urdu: "گرم مشروبات", icon: "M7 3h8v6a4 4 0 01-4 4h-4V3zm-2 5H3v1a4 4 0 004 4h1M7 17h6" },
  ];
  return (
    <section id="menu" className="scroll-mt-20 bg-[var(--bg-secondary)]">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <SectionHeading
          eyebrow="Menu"
          title="Real campus food, organized"
          sub="From karak chai to biryani, every cafeteria publishes its menu daily. Here is a taste of the categories."
        />
        <div className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {cats.map((c) => (
            <div
              key={c.name}
              className="group rounded-2xl border border-[var(--border-default)] bg-[var(--bg-primary)] p-5 text-center shadow-card transition-all hover:-translate-y-1 hover:shadow-card-hover"
            >
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-100 text-brand-800 transition-colors group-hover:bg-brand-700 group-hover:text-white dark:bg-brand-900/40 dark:text-brand-200">
                <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
                  <path strokeLinecap="round" strokeLinejoin="round" d={c.icon} />
                </svg>
              </div>
              <p className="mt-3 text-sm font-bold text-[var(--text-primary)]">{c.name}</p>
              <p className="mt-0.5 text-xs text-[var(--text-muted)]">{c.urdu}</p>
            </div>
          ))}
        </div>
        <p className="mt-8 text-center text-sm text-[var(--text-muted)]">
          Menus change daily.{" "}
          <Link href="/register" className="font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-400">
            Create an account
          </Link>{" "}
          to see today&apos;s full menu.
        </p>
      </div>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    {
      n: "1",
      title: "Browse the menu",
      desc: "Open the UniServe mobile app, pick your cafeteria, and browse today's published menu with real prices and photos.",
    },
    {
      n: "2",
      title: "Place your order",
      desc: "Add items to your cart, choose pickup now or schedule it, and pay by cash or online. It takes under a minute.",
    },
    {
      n: "3",
      title: "Track & pick up",
      desc: "Watch your order go from Ordered to Preparing to Ready. Get notified, show your pickup code, and enjoy.",
    },
  ];
  return (
    <section id="how" className="scroll-mt-20">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <SectionHeading
          eyebrow="How it works"
          title="From craving to pickup in three steps"
        />
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {steps.map((s) => (
            <div
              key={s.n}
              className="relative rounded-[1.75rem] border border-[var(--border-default)] bg-[var(--bg-primary)] p-8 shadow-card"
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-700 text-xl font-extrabold text-white">
                {s.n}
              </span>
              <h3 className="mt-5 text-xl font-extrabold tracking-tight text-[var(--text-primary)]">
                {s.title}
              </h3>
              <p className="mt-3 leading-relaxed text-[var(--text-secondary)]">{s.desc}</p>
            </div>
          ))}
        </div>

        {/* live tracker strip */}
        <div className="mx-auto mt-12 max-w-3xl rounded-[1.75rem] border border-[var(--border-default)] bg-[var(--bg-primary)] p-6 shadow-card sm:p-8">
          <div className="flex items-center justify-between">
            <p className="text-lg font-extrabold text-[var(--text-primary)]">Live order tracking</p>
            <span className="rounded-full bg-brand-100 px-3 py-1 text-xs font-semibold text-brand-800 dark:bg-brand-900/40 dark:text-brand-200">
              Order #LGU-1031
            </span>
          </div>
          <div className="mt-6 flex items-center">
            {["Ordered", "Preparing", "Ready", "Picked up"].map((step, i) => (
              <div key={step} className="flex flex-1 items-center last:flex-none">
                <div className="flex flex-col items-center gap-2">
                  <span
                    className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold ${
                      i < 2
                        ? "bg-brand-700 text-white"
                        : "border-2 border-[var(--border-default)] text-[var(--text-muted)]"
                    }`}
                  >
                    {i < 2 ? (
                      <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M16.7 5.3a1 1 0 010 1.4l-8 8a1 1 0 01-1.4 0l-4-4a1 1 0 111.4-1.4L8 12.6l7.3-7.3a1 1 0 011.4 0z" clipRule="evenodd" />
                      </svg>
                    ) : (
                      i + 1
                    )}
                  </span>
                  <span className="text-xs font-medium text-[var(--text-secondary)]">{step}</span>
                </div>
                {i < 3 && (
                  <div className={`mx-2 mb-7 h-1 flex-1 rounded-full ${i < 1 ? "bg-brand-600" : "bg-[var(--border-default)]"}`} />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Roles() {
  const roles = [
    {
      title: "Students",
      desc: "Order ahead between classes, pay your way, and grab your food without standing in line.",
    },
    {
      title: "Faculty",
      desc: "Exclusive faculty cafeteria access plus everything students get, with monthly statements.",
    },

  ];
  return (
    <section id="roles" className="scroll-mt-20 bg-[var(--bg-secondary)]">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <SectionHeading
          eyebrow="Who it serves"
          title="Built for students and faculty"
        />
        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          {roles.map((r) => (
            <div
              key={r.title}
              className="rounded-[1.75rem] border border-[var(--border-default)] bg-[var(--bg-primary)] p-6 shadow-card transition-shadow hover:shadow-card-hover"
            >
              <h3 className="text-lg font-extrabold tracking-tight text-[var(--text-primary)]">
                {r.title}
              </h3>
              <p className="mt-2.5 text-sm leading-relaxed text-[var(--text-secondary)]">{r.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CtaBand() {
  const { isAuthenticated } = useAuth();
  return (
    <section>
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="relative overflow-hidden rounded-[2rem] bg-brand-800 px-6 py-14 text-center shadow-card sm:px-12">
          <div
            aria-hidden
            className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-brand-600/50 blur-3xl"
          />
          <img
            src="/lgu-logo.jpg"
            alt=""
            aria-hidden
            className="mx-auto h-16 w-16 rounded-full border-2 border-white/30 object-cover"
          />
          <h2 className="mx-auto mt-6 max-w-xl text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Hungry? Your next meal is minutes away.
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-brand-100">
            Join Lahore Garrison University&apos;s campus dining platform and
            never wait in a cafeteria line again.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                className="rounded-full bg-white px-7 py-3.5 text-sm font-bold text-brand-900 transition-transform hover:scale-[1.02]"
              >
                Go to dashboard
              </Link>
            ) : (
              <>
                <Link
                  href="/register"
                  className="rounded-full bg-white px-7 py-3.5 text-sm font-bold text-brand-900 transition-transform hover:scale-[1.02]"
                >
                  Create free account
                </Link>
                <Link
                  href="/login"
                  className="rounded-full border border-white/40 px-7 py-3.5 text-sm font-semibold text-white transition-colors hover:bg-white/10"
                >
                  Sign in
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-[var(--border-light)]">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-4 py-10 sm:px-6 md:flex-row">
        <div className="flex items-center gap-3">
          <img
            src="/lgu-logo.jpg"
            alt="Lahore Garrison University logo"
            className="h-9 w-9 rounded-full border border-[var(--border-default)] object-cover"
          />
          <div className="leading-tight">
            <p className="text-sm font-extrabold text-[var(--text-primary)]">UniServe</p>
            <p className="text-xs text-[var(--text-muted)]">Lahore Garrison University</p>
          </div>
        </div>
        <div className="flex flex-wrap justify-center gap-6 text-sm font-medium text-[var(--text-secondary)]">
          <Link href="/login" className="hover:text-brand-700 dark:hover:text-brand-300">Sign in</Link>
          <Link href="/register" className="hover:text-brand-700 dark:hover:text-brand-300">Create account</Link>
          <a href="#cafeterias" className="hover:text-brand-700 dark:hover:text-brand-300">Cafeterias</a>
          <a href="#how" className="hover:text-brand-700 dark:hover:text-brand-300">How it works</a>
        </div>
        <p className="text-xs text-[var(--text-muted)]">
          &copy; {new Date().getFullYear()} Lahore Garrison University. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

/* ---------- page ---------- */

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <Nav />
      <main>
        <Hero />
        <Stats />
        <Cafeterias />
        <MenuPreview />
        <HowItWorks />
        <Roles />
        <CtaBand />
      </main>
      <Footer />
    </div>
  );
}
