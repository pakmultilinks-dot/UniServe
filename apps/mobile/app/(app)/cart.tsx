/**
 * UniServe — Cart stack route (legacy alias)
 *
 * The floating CartBar historically pushed to this route. It now redirects
 * to the canonical Cart tab so there is exactly one cart screen. Kept as a
 * redirect (not deleted) per the no-deletion rule; deep links to /cart keep
 * working.
 */
import React from "react";
import { Redirect } from "expo-router";

export default function CartRoute() {
  return <Redirect href="/(app)/(tabs)/cart" />;
}
