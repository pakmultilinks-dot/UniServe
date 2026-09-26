/**
 * UniServe — Home Page
 *
 * Redirects to /dashboard (which handles auth checks).
 * If the user is not authenticated, the dashboard middleware
 * will redirect to /login.
 */
import { redirect } from "next/navigation";

export default function HomePage() {
  redirect("/dashboard");
}
