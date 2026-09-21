/**
 * UniServe — Home Page
 *
 * This page will be developed in Phase 2+ when authentication
 * and role-based routing are implemented.
 */
export default function HomePage() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
      }}
    >
      <h1 style={{ fontSize: "2.5rem", fontWeight: "bold" }}>UniServe</h1>
      <p style={{ fontSize: "1.25rem", color: "#666", marginTop: "0.5rem" }}>
        University Cafeteria Platform
      </p>
      <p style={{ fontSize: "1rem", color: "#999", marginTop: "1rem" }}>
        Web dashboard coming in future phases
      </p>
    </main>
  );
}
